#!/usr/bin/env python3
"""
Job 3 reducer: one line per day with occupancy and Wi-Fi usage side by side.

Output (final): date, weekday, occupied_rooms, occupancy_pct, wifi_sessions, wifi_gb,
                mb_per_occupied_room, sessions_per_occupied_room, pct_rooms_using_wifi
Run with --combine to act as the combiner (outputs partial sums in the input layout).
"""
import sys
from datetime import datetime

COMBINE = "--combine" in sys.argv
TOTAL_ROOMS = 750

def emit(key, t):
    rooms, sessions, mb, using = t
    if COMBINE:
        print("%s\t%d\t%d\t%.1f\t%d" % (key, rooms, sessions, mb, using))
        return
    weekday = datetime.strptime(key, "%Y-%m-%d").strftime("%a")
    print("\t".join([key, weekday, "%d" % rooms, "%.1f" % (100.0 * rooms / TOTAL_ROOMS),
                     "%d" % sessions, "%.2f" % (mb / 1024.0), "%.1f" % (mb / rooms),
                     "%.2f" % (sessions / rooms), "%.1f" % (100.0 * using / rooms)]))

current, totals = None, None
for line in sys.stdin:
    parts = line.rstrip("\n").split("\t")
    if len(parts) != 5:
        continue
    key, nums = parts[0], [float(x) for x in parts[1:]]
    if key != current:
        if current is not None:
            emit(current, totals)
        current, totals = key, [0.0] * 4
    totals = [a + b for a, b in zip(totals, nums)]
if current is not None:
    emit(current, totals)
