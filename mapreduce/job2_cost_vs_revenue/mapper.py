#!/usr/bin/env python3
"""
Job 2 mapper: purchasing cost against revenue, per department.

Input : /datalake/curated/department_daily   (one CSV row per department per day)
Output: department <TAB> days <TAB> po_count <TAB> purchase_cost <TAB> erp_revenue
              <TAB> erp_cost <TAB> pos_revenue <TAB> staff_on_shift <TAB> staff_days
Every row is also sent to the key "All departments" for the hotel-wide total.
pos_revenue is only filled for F&B (restaurant, bar and room service checks).
"""
import csv
import io
import sys

COUNTS = {}   # Hadoop counters, reported once at the end (shown in the job summary)

def count(name):
    COUNTS[name] = COUNTS.get(name, 0) + 1

def f(v):
    return float(v) if v not in ("", None) else 0.0

stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace")
for row in csv.reader(stdin):
    if not row or row[0] == "date":
        continue
    if len(row) != 11 or not row[1]:
        count("Job2 rows skipped - bad format")
        continue
    (date, dept, po_count, purchase_cost, erp_revenue, erp_cost,
     staff_on_shift, staff_hours, pos_revenue, occupied, occ_pct) = row
    try:
        values = [1, f(po_count), f(purchase_cost), f(erp_revenue), f(erp_cost),
                  f(pos_revenue), f(staff_on_shift), 1 if staff_on_shift else 0]
    except ValueError:
        count("Job2 rows skipped - bad number")
        continue
    count("Job2 department-days read")
    text = "\t".join("%.2f" % v for v in values)
    print(dept + "\t" + text)
    print("All departments\t" + text)

for name in sorted(COUNTS):
    sys.stderr.write("reporter:counter:Hotel data lake,%s,%d\n" % (name, COUNTS[name]))
