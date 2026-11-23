#!/usr/bin/env python3
"""
Cleaning pipeline: RAW zone -> CLEANED zone of the hotel data lake.

For every source and every date it:
  * standardises dates (dd/mm/yyyy -> yyyy-mm-dd) and room numbers (412 -> 0412)
  * maps department name variants to one standard name (FnB, F and B -> F&B)
  * removes exact duplicate records (POS and Wi-Fi)
  * fills a missing value when it can be worked out from the same row (ERP entry_type)
  * moves rows that cannot be fixed (a key field missing or invalid) to the rejected folder
  * logs rows read / written / rejected / duplicates removed for each source and date (NFR6)

Raw files are never changed (FR2): this script only reads them.

Output:
  /datalake/cleaned/<source>/<date>/<source>_<date>.<csv|json>
  /datalake/cleaned/_rejected/<source>/<date>/<source>_<date>_rejected.<csv|json>
  /datalake/cleaned/_logs/cleaning_<run time>.csv

Usage (inside the nodemanager container, started by clean.sh on the host):
  python3 clean.py                  clean every date found in the raw zone
  python3 clean.py --date 20261015  clean one day (what the nightly run does)

Written for Python 3.5 (the version in the Hadoop container): no f-strings.
"""
import argparse
import csv
import io
import json
import os
import shutil
import subprocess
import sys
import time
from collections import OrderedDict
from datetime import datetime

LAKE = "/datalake"
WORK = "/tmp/clean_work"

# ---------------------------------------------------------------- reference data

# Department name variants seen across ERP, HR and procurement -> standard name
DEPARTMENT_MAP = {
    "f&b": "F&B", "food and beverage": "F&B", "f and b": "F&B", "fnb": "F&B",
    "housekeeping": "Housekeeping", "hk": "Housekeeping", "house keeping": "Housekeeping",
    "front office": "Front Office", "front desk": "Front Office", "fo": "Front Office",
    "engineering": "Engineering", "eng": "Engineering", "maintenance": "Engineering",
    "spa & wellness": "Spa & Wellness", "spa": "Spa & Wellness", "spa and wellness": "Spa & Wellness",
    "sales & marketing": "Sales & Marketing", "sales and marketing": "Sales & Marketing",
    "s&m": "Sales & Marketing",
    "rooms": "Rooms", "rooms division": "Rooms",
    "kitchen": "Kitchen", "banquets": "Banquets", "recreation": "Recreation",
    "security": "Security", "concierge": "Concierge", "it": "IT",
    "finance": "Finance", "administration": "Administration",
}

DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"]


class Reject(Exception):
    """Raised when a row cannot be fixed. The message is the reason."""


# ---------------------------------------------------------------- field rules

def blank(v):
    return v is None or str(v).strip() == ""


def required(row, field):
    v = row.get(field)
    if blank(v):
        raise Reject("missing " + field)
    return str(v).strip()


def optional(row, field):
    v = row.get(field)
    return "" if blank(v) else str(v).strip()


def fix_date(value, field):
    v = str(value).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(v, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    raise Reject("bad date in " + field + ": " + v)


def fix_datetime(value, field):
    v = str(value).strip().replace(" ", "T")
    try:
        return datetime.strptime(v, "%Y-%m-%dT%H:%M:%S").strftime("%Y-%m-%dT%H:%M:%S")
    except ValueError:
        raise Reject("bad datetime in " + field + ": " + v)


def fix_room(value):
    v = str(value).strip()
    if not v.isdigit() or len(v) > 4:
        raise Reject("bad room_number: " + v)
    return v.zfill(4)


def fix_department(value, stats):
    v = str(value).strip()
    std = DEPARTMENT_MAP.get(v.lower())
    if std is None:
        stats["unmapped_departments"] += 1
        return v
    if std != v:
        stats["departments_renamed"] += 1
    return std


def fix_number(value, field, integer=False):
    v = str(value).strip()
    try:
        n = int(v) if integer else float(v)
    except ValueError:
        raise Reject("bad number in " + field + ": " + v)
    if n < 0:
        raise Reject("negative " + field + ": " + v)
    return str(n) if integer else "%.2f" % n


# ---------------------------------------------------------------- one function per source
# Each takes the raw row (dict), the date folder it came from and the stats counter,
# and returns the cleaned row as an OrderedDict (column order = output column order).

def clean_pms(r, day, stats):
    out = OrderedDict()
    out["snapshot_date"] = day          # PMS files are a daily list of current reservations
    out["reservation_id"] = required(r, "reservation_id")
    out["guest_id"] = optional(r, "guest_id")
    out["room_number"] = fix_room(required(r, "room_number"))
    out["room_type"] = optional(r, "room_type")
    out["check_in_date"] = fix_date(required(r, "check_in_date"), "check_in_date")
    out["check_out_date"] = fix_date(required(r, "check_out_date"), "check_out_date")
    if out["check_out_date"] < out["check_in_date"]:
        raise Reject("check_out_date before check_in_date")
    rate = optional(r, "rate_per_night")
    out["rate_per_night"] = fix_number(rate, "rate_per_night") if rate else ""
    out["booking_channel"] = optional(r, "booking_channel")
    out["status"] = required(r, "status")
    return out


def clean_pos(r, day, stats):
    out = OrderedDict()
    out["check_id"] = required(r, "check_id")
    dt = fix_datetime(required(r, "datetime"), "datetime")
    out["date"] = dt[:10]
    out["datetime"] = dt
    out["outlet"] = optional(r, "outlet")
    out["total_amount"] = fix_number(required(r, "total_amount"), "total_amount")
    out["payment_method"] = optional(r, "payment_method")
    room = optional(r, "room_number")   # blank is normal: walk-in guest paying by card or cash
    out["room_number"] = fix_room(room) if room else ""
    covers = optional(r, "covers")
    out["covers"] = fix_number(covers, "covers", integer=True) if covers else ""
    return out


def clean_procurement(r, day, stats):
    out = OrderedDict()
    out["po_id"] = required(r, "po_id")
    out["supplier_id"] = optional(r, "supplier_id")
    out["department"] = fix_department(required(r, "department"), stats)
    out["item_category"] = optional(r, "item_category")
    out["quantity"] = fix_number(required(r, "quantity"), "quantity", integer=True)
    out["unit_cost"] = fix_number(required(r, "unit_cost"), "unit_cost")
    out["order_date"] = fix_date(required(r, "order_date"), "order_date")
    rec = optional(r, "received_date")  # blank is normal: order not received yet
    out["received_date"] = fix_date(rec, "received_date") if rec else ""
    return out


def clean_erp(r, day, stats):
    out = OrderedDict()
    out["entry_id"] = required(r, "entry_id")
    out["date"] = fix_date(required(r, "date"), "date")
    code = optional(r, "account_code")
    out["account_code"] = code
    out["department"] = fix_department(required(r, "department"), stats)
    out["amount"] = fix_number(required(r, "amount"), "amount")
    etype = optional(r, "entry_type")
    if not etype:
        # Fill from the account code: 4xxx accounts are revenue (Credit), the rest are costs (Debit)
        if not code:
            raise Reject("missing entry_type and account_code")
        etype = "Credit" if code.startswith("4") else "Debit"
        stats["values_filled"] += 1
    out["entry_type"] = etype
    return out


def clean_hr(r, day, stats):
    out = OrderedDict()
    out["date"] = fix_date(required(r, "date"), "date")
    out["department"] = fix_department(required(r, "department"), stats)
    staff = optional(r, "staff_on_shift")
    out["staff_on_shift"] = fix_number(staff, "staff_on_shift", integer=True) if staff else ""
    hours = optional(r, "total_hours")
    out["total_hours"] = fix_number(hours, "total_hours") if hours else ""
    return out


def clean_wifi(r, day, stats):
    out = OrderedDict()
    out["session_id"] = required(r, "session_id")
    out["device_id"] = optional(r, "device_id")
    out["room_number"] = fix_room(required(r, "room_number"))
    login = fix_datetime(required(r, "login_time"), "login_time")
    out["date"] = login[:10]
    out["login_time"] = login
    logout = optional(r, "logout_time")
    out["logout_time"] = fix_datetime(logout, "logout_time") if logout else None
    mb = optional(r, "data_used_mb")
    out["data_used_mb"] = float(fix_number(mb, "data_used_mb")) if mb else None
    return out


def clean_reviews(r, day, stats):
    out = OrderedDict()
    out["review_id"] = required(r, "review_id")
    out["reservation_id"] = required(r, "reservation_id")
    out["review_date"] = fix_date(required(r, "review_date"), "review_date")
    score = int(fix_number(required(r, "score"), "score", integer=True))
    if score > 10:
        raise Reject("score out of range: %d" % score)
    out["score"] = score
    out["review_text"] = optional(r, "review_text")
    return out


# source -> (cleaning function, file format, remove exact duplicates?)
SOURCES = OrderedDict([
    ("pms", (clean_pms, "csv", False)),       # same reservation on many days is NOT a duplicate
    ("pos", (clean_pos, "csv", True)),
    ("procurement", (clean_procurement, "csv", False)),
    ("erp", (clean_erp, "csv", False)),
    ("hr", (clean_hr, "csv", False)),
    ("wifi", (clean_wifi, "json", True)),     # session_id alone is not unique, so whole record
    ("reviews", (clean_reviews, "json", False)),
])

STAT_KEYS = ["rows_read", "rows_written", "rows_rejected", "duplicates_removed",
             "values_filled", "departments_renamed", "unmapped_departments"]


# ---------------------------------------------------------------- reading and writing files

def read_rows(path, fmt):
    """Yields (raw text of the record, dict) for each record in a raw file."""
    with io.open(path, encoding="utf-8", newline="") as f:
        if fmt == "csv":
            reader = csv.reader(f)
            header = next(reader, None)
            if header is None:
                return
            for fields in reader:
                if not any(x.strip() for x in fields):
                    continue
                yield fields, dict(zip(header, fields))
        else:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield line, json.loads(line)
                except ValueError:
                    yield line, None


def clean_day(source, day, raw_dir, out_dir, rej_dir):
    func, fmt, dedup = SOURCES[source]
    stats = OrderedDict((k, 0) for k in STAT_KEYS)
    good, bad, seen = [], [], set()

    for name in sorted(os.listdir(raw_dir)):
        if not name.endswith("." + fmt):
            continue
        for raw, rec in read_rows(os.path.join(raw_dir, name), fmt):
            stats["rows_read"] += 1
            try:
                if rec is None:
                    raise Reject("not valid JSON")
                row = func(rec, day, stats)
            except Reject as e:
                stats["rows_rejected"] += 1
                bad.append((raw, str(e)))
                continue
            if dedup:
                key = json.dumps(row, sort_keys=True)
                if key in seen:
                    stats["duplicates_removed"] += 1
                    continue
                seen.add(key)
            good.append(row)
            stats["rows_written"] += 1

    os.makedirs(out_dir)
    os.makedirs(rej_dir)
    base = "%s_%s" % (source, day)
    out_path = os.path.join(out_dir, base + "." + fmt)
    rej_path = os.path.join(rej_dir, base + "_rejected." + fmt)

    with io.open(out_path, "w", encoding="utf-8", newline="") as f:
        if fmt == "csv":
            w = csv.writer(f, lineterminator="\n")
            if good:
                w.writerow(list(good[0].keys()))
            for row in good:
                w.writerow(list(row.values()))
        else:
            for row in good:
                f.write(json.dumps(row) + "\n")

    # The rejected file is always written (even when empty) so a re-run replaces the old one
    with io.open(rej_path, "w", encoding="utf-8", newline="") as f:
        if fmt == "csv":
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["reject_reason", "original_row"])
            for raw, reason in bad:
                w.writerow([reason, ",".join(raw)])
        else:
            for raw, reason in bad:
                f.write(json.dumps(OrderedDict([("reject_reason", reason), ("original", raw)])) + "\n")
    return stats


# ---------------------------------------------------------------- HDFS helpers

def hdfs(*args):
    cmd = ["hdfs", "dfs"] + list(args)
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       universal_newlines=True)
    if p.returncode != 0:
        sys.stderr.write("HDFS command failed: %s\n%s\n" % (" ".join(cmd), p.stderr))
        sys.exit(1)
    return p.stdout


def raw_dates(source):
    out = hdfs("-ls", "-C", "%s/raw/%s" % (LAKE, source))
    return sorted(os.path.basename(p) for p in out.split() if p.strip())


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Clean RAW zone data into the CLEANED zone")
    ap.add_argument("--date", default="all", help="YYYYMMDD, or 'all' (default)")
    ap.add_argument("--source", default="all", help="one source, or 'all' (default)")
    a = ap.parse_args()

    if a.date != "all":
        try:
            want = datetime.strptime(a.date, "%Y%m%d").strftime("%Y-%m-%d")
        except ValueError:
            sys.exit("--date must look like 20261015")
    sources = list(SOURCES) if a.source == "all" else [a.source]
    for s in sources:
        if s not in SOURCES:
            sys.exit("unknown source: " + s)

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    start = time.time()
    if os.path.exists(WORK):
        shutil.rmtree(WORK)
    log_rows = []

    for source in sources:
        t0 = time.time()
        dates = raw_dates(source)
        if a.date != "all":
            dates = [d for d in dates if d == want]
        if not dates:
            print("%-12s no raw data for %s" % (source, a.date))
            continue

        src_work = os.path.join(WORK, source)
        raw_local = os.path.join(src_work, "raw")
        out_local = os.path.join(src_work, "cleaned")
        rej_local = os.path.join(src_work, "rejected")
        os.makedirs(raw_local)
        os.makedirs(out_local)
        os.makedirs(rej_local)

        # 1 HDFS call to download all the dates for this source
        hdfs("-get", *(["%s/raw/%s/%s" % (LAKE, source, d) for d in dates] + [raw_local]))

        totals = OrderedDict((k, 0) for k in STAT_KEYS)
        for d in dates:
            st = clean_day(source, d, os.path.join(raw_local, d),
                           os.path.join(out_local, d), os.path.join(rej_local, d))
            for k in STAT_KEYS:
                totals[k] += st[k]
            log_rows.append([run_id, source, d] + [st[k] for k in STAT_KEYS])

        # 2 HDFS calls to upload the cleaned and rejected date folders (overwrites a re-run)
        hdfs("-put", "-f", *([os.path.join(out_local, d) for d in dates]
                             + ["%s/cleaned/%s/" % (LAKE, source)]))
        hdfs("-put", "-f", *([os.path.join(rej_local, d) for d in dates]
                             + ["%s/cleaned/_rejected/%s/" % (LAKE, source)]))

        print("%-12s %2d day(s)  read %7d  written %7d  rejected %5d  duplicates %5d  "
              "filled %4d  depts renamed %5d  (%.0fs)"
              % (source, len(dates), totals["rows_read"], totals["rows_written"],
                 totals["rows_rejected"], totals["duplicates_removed"],
                 totals["values_filled"], totals["departments_renamed"], time.time() - t0))
        if totals["unmapped_departments"]:
            print("             WARNING: %d department name(s) not in DEPARTMENT_MAP"
                  % totals["unmapped_departments"])
        if totals["rows_read"] != (totals["rows_written"] + totals["rows_rejected"]
                                   + totals["duplicates_removed"]):
            print("             WARNING: row counts do not add up")

    # Run log (NFR6): one line per source and date
    if log_rows:
        log_path = os.path.join(WORK, "cleaning_%s.csv" % run_id)
        with io.open(log_path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["run_id", "source", "date"] + STAT_KEYS)
            w.writerows(log_rows)
        hdfs("-put", "-f", log_path, "%s/cleaned/_logs/" % LAKE)
        print("Log written to %s/cleaned/_logs/cleaning_%s.csv" % (LAKE, run_id))

    shutil.rmtree(WORK)
    print("Cleaning finished in %.0f seconds" % (time.time() - start))


if __name__ == "__main__":
    main()
