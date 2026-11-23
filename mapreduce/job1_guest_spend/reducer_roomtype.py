#!/usr/bin/env python3
"""
Job 1, stage B reducer: average guest spend PER STAY for each room type.

Input : room_type <TAB> stays <TAB> nights <TAB> room_revenue <TAB> pos_spend <TAB> stays_with_spend
Output (final): room_type, stays, avg_nights, avg_room_revenue_per_stay,
                avg_fnb_spend_per_stay, avg_total_spend_per_stay, fnb_share_pct,
                pct_stays_with_fnb_spend
Run with --combine to act as the combiner: it then outputs partial sums in the input
layout instead of averages (averages cannot be combined, sums can).
"""
import sys

COMBINE = "--combine" in sys.argv

def emit(key, t):
    stays, nights, room_rev, fnb, with_fnb = t
    if COMBINE:
        print("\t".join([key, "%d" % stays, "%d" % nights, "%.2f" % room_rev,
                         "%.2f" % fnb, "%d" % with_fnb]))
        return
    total = room_rev + fnb
    print("\t".join([key, "%d" % stays,
                     "%.2f" % (nights / stays),
                     "%.2f" % (room_rev / stays),
                     "%.2f" % (fnb / stays),
                     "%.2f" % (total / stays),
                     "%.1f" % (100.0 * fnb / total if total else 0),
                     "%.1f" % (100.0 * with_fnb / stays)]))

current, totals = None, None
for line in sys.stdin:
    parts = line.rstrip("\n").split("\t")
    if len(parts) != 6:
        continue
    key, nums = parts[0], [float(x) for x in parts[1:]]
    if key != current:
        if current is not None:
            emit(current, totals)
        current, totals = key, [0.0] * 5
    totals = [a + b for a, b in zip(totals, nums)]
if current is not None:
    emit(current, totals)
