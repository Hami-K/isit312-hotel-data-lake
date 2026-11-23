#!/usr/bin/env python3
"""
Curation pipeline: CLEANED zone -> CURATED zone of the hotel data lake.

Joins the cleaned sources on the three join keys from Section 2.2 and writes one
report-ready CSV per dataset. The MapReduce analysis jobs read these files.

  guest_stay_summary  PMS + POS + Wi-Fi on room_number + date
                      one row per occupied room per night
  review_stay_link    PMS + Reviews on reservation_id
                      one row per review, with the details of the stay it belongs to
  department_daily    Procurement + ERP + HR (+ POS, PMS) on department + date
                      one row per department per day

Privacy (NFR5): guest_id is dropped and reservation_id is replaced by stay_key, a one-way
hash. Rows for the same stay still link across the curated datasets, but they cannot be
traced back to a guest without the secret salt below.

Output:
  /datalake/curated/<dataset>/<dataset>.csv     (first line is the header)
  /datalake/curated/_logs/curation_<run time>.csv

Usage (inside the nodemanager container, started by curate.sh on the host):
  python3 curate.py

Written for Python 3.5 (the version in the Hadoop container): no f-strings.
"""
import csv
import glob
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import time
from collections import OrderedDict, defaultdict
from datetime import datetime, timedelta

LAKE = "/datalake"
WORK = "/tmp/curate_work"
SALT = os.environ.get("STAY_KEY_SALT", "isit312-hotel-datalake")  # demo default; in production set
                                                                  # STAY_KEY_SALT and keep it secret
TOTAL_ROOMS = 750
SOURCES = ["pms", "pos", "wifi", "reviews", "procurement", "erp", "hr"]


# ---------------------------------------------------------------- helpers

def hdfs(*args):
    cmd = ["hdfs", "dfs"] + list(args)
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       universal_newlines=True)
    if p.returncode != 0:
        sys.stderr.write("HDFS command failed: %s\n%s\n" % (" ".join(cmd), p.stderr))
        sys.exit(1)
    return p.stdout


def read_source(source):
    """All cleaned rows of one source, from every date folder."""
    rows = []
    for path in sorted(glob.glob(os.path.join(WORK, "cleaned", source, "*", "*"))):
        with io.open(path, encoding="utf-8", newline="") as f:
            if path.endswith(".csv"):
                rows.extend(csv.DictReader(f))
            else:
                rows.extend(json.loads(line) for line in f if line.strip())
    return rows


def stay_key(reservation_id):
    return hashlib.sha256((SALT + reservation_id).encode("utf-8")).hexdigest()[:12]


def num(v):
    return float(v) if v not in (None, "") else 0.0


def money(v):
    return "%.2f" % v


def days(first, last):
    d = datetime.strptime(first, "%Y-%m-%d")
    end = datetime.strptime(last, "%Y-%m-%d")
    while d <= end:
        yield d.strftime("%Y-%m-%d")
        d += timedelta(days=1)


def write_csv(dataset, header, rows):
    folder = os.path.join(WORK, "curated", dataset)
    os.makedirs(folder)
    path = os.path.join(folder, dataset + ".csv")
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)
    return path


# ---------------------------------------------------------------- stays from PMS

def build_stays(pms, log):
    """
    PMS files are a daily list of current reservations, so one reservation appears on
    several days. Keep the latest version of each reservation (its final status).
    """
    latest = {}
    for r in pms:
        rid = r["reservation_id"]
        if rid not in latest or r["snapshot_date"] > latest[rid]["snapshot_date"]:
            latest[rid] = r
    log["pms_rows"] = len(pms)
    log["reservations"] = len(latest)
    stays = {rid: r for rid, r in latest.items() if r["status"] not in ("Cancelled", "No show")}
    log["reservations_cancelled_or_no_show"] = len(latest) - len(stays)
    return stays


# ---------------------------------------------------------------- dataset 1

def guest_stay_summary(stays, pos, wifi, first, last, log):
    # Which stay occupies each room on each night (nights = check_in .. check_out - 1)
    occupant = {}
    clashes = 0
    for rid in sorted(stays):
        s = stays[rid]
        ci = max(s["check_in_date"], first)
        co_last = (datetime.strptime(s["check_out_date"], "%Y-%m-%d")
                   - timedelta(days=1)).strftime("%Y-%m-%d")
        if ci > min(co_last, last):
            continue                         # no nights inside the data period
        for d in days(ci, min(co_last, last)):
            key = (s["room_number"], d)
            if key in occupant:
                clashes += 1                 # two reservations on one room-night: keep the first
                continue
            occupant[key] = rid
    log["room_nights"] = len(occupant)
    log["room_night_clashes"] = clashes

    # POS checks charged to a room, per room-night
    spend = defaultdict(lambda: [0, 0.0])
    pos_room = pos_matched = 0
    for r in pos:
        if not r["room_number"]:
            continue                         # walk-in guest: not linked to a room
        pos_room += 1
        key = (r["room_number"], r["date"])
        if key in occupant:
            pos_matched += 1
            spend[key][0] += 1
            spend[key][1] += num(r["total_amount"])
    log["pos_checks_with_room"] = pos_room
    log["pos_checks_matched_to_stay"] = pos_matched

    # Wi-Fi sessions per room-night
    usage = defaultdict(lambda: [0, 0.0])
    wifi_matched = 0
    for r in wifi:
        key = (r["room_number"], r["date"])
        if key in occupant:
            wifi_matched += 1
            usage[key][0] += 1
            usage[key][1] += num(r["data_used_mb"])
    log["wifi_sessions"] = len(wifi)
    log["wifi_sessions_matched_to_stay"] = wifi_matched

    header = ["date", "room_number", "stay_key", "room_type", "rate_per_night",
              "booking_channel", "check_in_date", "check_out_date",
              "pos_checks", "pos_spend", "wifi_sessions", "wifi_mb"]
    rows = []
    for (room, d) in sorted(occupant, key=lambda k: (k[1], k[0])):
        s = stays[occupant[(room, d)]]
        sp, us = spend.get((room, d), [0, 0.0]), usage.get((room, d), [0, 0.0])
        rows.append([d, room, stay_key(occupant[(room, d)]), s["room_type"], s["rate_per_night"],
                     s["booking_channel"], s["check_in_date"], s["check_out_date"],
                     sp[0], money(sp[1]), us[0], "%.1f" % us[1]])
    return header, rows, occupant


# ---------------------------------------------------------------- dataset 2

def review_stay_link(stays, reviews, log):
    header = ["review_id", "stay_key", "review_date", "score", "room_type", "rate_per_night",
              "nights", "booking_channel", "check_in_date", "check_out_date", "review_text"]
    rows = []
    for r in reviews:
        s = stays.get(r["reservation_id"])
        if s is None:
            continue
        nights = (datetime.strptime(s["check_out_date"], "%Y-%m-%d")
                  - datetime.strptime(s["check_in_date"], "%Y-%m-%d")).days
        text = " ".join(str(r["review_text"]).split())   # one line per record
        rows.append([r["review_id"], stay_key(r["reservation_id"]), r["review_date"], r["score"],
                     s["room_type"], s["rate_per_night"], nights, s["booking_channel"],
                     s["check_in_date"], s["check_out_date"], text])
    log["reviews"] = len(reviews)
    log["reviews_matched_to_stay"] = len(rows)
    rows.sort(key=lambda x: (x[2], x[0]))
    return header, rows


# ---------------------------------------------------------------- dataset 3

def department_daily(procurement, erp, hr, pos, occupant, first, last, log):
    blank = lambda: OrderedDict([("po_count", 0), ("purchase_cost", 0.0), ("erp_revenue", 0.0),
                                 ("erp_cost", 0.0), ("staff_on_shift", ""), ("staff_hours", ""),
                                 ("pos_revenue", "")])
    grid = defaultdict(blank)
    in_period = lambda d: first <= d <= last

    for r in procurement:
        if in_period(r["order_date"]):
            g = grid[(r["order_date"], r["department"])]
            g["po_count"] += 1
            g["purchase_cost"] += num(r["quantity"]) * num(r["unit_cost"])
    for r in erp:
        if in_period(r["date"]):
            g = grid[(r["date"], r["department"])]
            if r["entry_type"] == "Credit":
                g["erp_revenue"] += num(r["amount"])
            else:
                g["erp_cost"] += num(r["amount"])
    for r in hr:
        if in_period(r["date"]):
            g = grid[(r["date"], r["department"])]
            g["staff_on_shift"] = r["staff_on_shift"]
            g["staff_hours"] = r["total_hours"]
    # POS outlets (restaurant, bar, room service) all belong to F&B
    pos_day = defaultdict(float)
    for r in pos:
        if in_period(r["date"]):
            pos_day[r["date"]] += num(r["total_amount"])
    for d, total in pos_day.items():
        grid[(d, "F&B")]["pos_revenue"] = total

    occupied = defaultdict(int)
    for (_room, d) in occupant:
        occupied[d] += 1

    header = ["date", "department", "po_count", "purchase_cost", "erp_revenue", "erp_cost",
              "staff_on_shift", "staff_hours", "pos_revenue", "occupied_rooms", "occupancy_pct"]
    rows = []
    for (d, dept) in sorted(grid):
        g = grid[(d, dept)]
        pos_rev = g["pos_revenue"]
        rows.append([d, dept, g["po_count"], money(g["purchase_cost"]), money(g["erp_revenue"]),
                     money(g["erp_cost"]), g["staff_on_shift"], g["staff_hours"],
                     money(pos_rev) if pos_rev != "" else "", occupied[d],
                     "%.1f" % (100.0 * occupied[d] / TOTAL_ROOMS)])
    log["department_days"] = len(rows)
    return header, rows


# ---------------------------------------------------------------- main

def main():
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    start = time.time()
    if os.path.exists(WORK):
        shutil.rmtree(WORK)
    os.makedirs(os.path.join(WORK, "cleaned"))

    # 1 HDFS call to download the cleaned zone (rejected rows and logs are not needed)
    hdfs("-get", *(["%s/cleaned/%s" % (LAKE, s) for s in SOURCES]
                   + [os.path.join(WORK, "cleaned")]))
    data = {s: read_source(s) for s in SOURCES}
    if not data["pms"]:
        sys.exit("No cleaned PMS data found. Run clean.sh first.")

    log = OrderedDict()
    snapshot_dates = sorted(set(r["snapshot_date"] for r in data["pms"]))
    first, last = snapshot_dates[0], snapshot_dates[-1]
    log["period_first_date"] = first
    log["period_last_date"] = last

    stays = build_stays(data["pms"], log)
    h1, r1, occupant = guest_stay_summary(stays, data["pos"], data["wifi"], first, last, log)
    h2, r2 = review_stay_link(stays, data["reviews"], log)
    h3, r3 = department_daily(data["procurement"], data["erp"], data["hr"], data["pos"],
                              occupant, first, last, log)

    outputs = [("guest_stay_summary", h1, r1), ("review_stay_link", h2, r2),
               ("department_daily", h3, r3)]
    for name, header, rows in outputs:
        path = write_csv(name, header, rows)
        hdfs("-put", "-f", path, "%s/curated/%s/" % (LAKE, name))
        print("%-20s %7d rows  ->  %s/curated/%s/%s.csv" % (name, len(rows), LAKE, name, name))

    print("")
    for k, v in log.items():
        print("  %-36s %s" % (k, v))

    log_path = os.path.join(WORK, "curation_%s.csv" % run_id)
    with io.open(log_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["run_id", "measure", "value"])
        for k, v in log.items():
            w.writerow([run_id, k, v])
    hdfs("-mkdir", "-p", "%s/curated/_logs" % LAKE)
    hdfs("-put", "-f", log_path, "%s/curated/_logs/" % LAKE)

    shutil.rmtree(WORK)
    print("\nLog written to %s/curated/_logs/curation_%s.csv" % (LAKE, run_id))
    print("Curation finished in %.0f seconds" % (time.time() - start))


if __name__ == "__main__":
    main()
