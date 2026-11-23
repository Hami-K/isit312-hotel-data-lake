#!/usr/bin/env python3
"""
Job 2 reducer: totals per department and purchasing cost as a % of revenue.

Output (final): department, days, purchase_orders, purchase_cost, erp_revenue,
                purchase_pct_of_revenue, erp_cost, pos_revenue, avg_staff_on_shift
Run with --combine to act as the combiner (outputs partial sums in the input layout).
"""
import sys

COMBINE = "--combine" in sys.argv

def emit(key, t):
    days, po, cost, rev, erp_cost, pos_rev, staff, staff_days = t
    if COMBINE:
        print(key + "\t" + "\t".join("%.2f" % v for v in t))
        return
    print("\t".join([key, "%d" % days, "%d" % po, "%.2f" % cost, "%.2f" % rev,
                     "%.1f" % (100.0 * cost / rev) if rev else "",
                     "%.2f" % erp_cost, "%.2f" % pos_rev,
                     "%.1f" % (staff / staff_days) if staff_days else ""]))

current, totals = None, None
for line in sys.stdin:
    parts = line.rstrip("\n").split("\t")
    if len(parts) != 9:
        continue
    key, nums = parts[0], [float(x) for x in parts[1:]]
    if key != current:
        if current is not None:
            emit(current, totals)
        current, totals = key, [0.0] * 8
    totals = [a + b for a, b in zip(totals, nums)]
if current is not None:
    emit(current, totals)
