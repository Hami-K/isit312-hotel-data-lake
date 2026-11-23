#!/usr/bin/env python3
"""
Job 1, stage A reducer (also used as the combiner): adds up every night of one stay.

Input : stay_key <TAB> room_type <TAB> channel <TAB> nights <TAB> room_revenue <TAB> pos_checks
              <TAB> pos_spend <TAB> wifi_mb          (sorted by stay_key by Hadoop)
Output: the same layout, one line per stay.

Because the output has the same layout as the input, this script is safe to run as a
combiner: Hadoop may run it on part of a stay's nights on the map side, and running it
again on those partial totals still gives the right answer.
"""
import sys

def emit(key, room_type, channel, t):
    print("\t".join([key, room_type, channel,
                     "%d" % t[0], "%.2f" % t[1], "%d" % t[2], "%.2f" % t[3], "%.1f" % t[4]]))

current, room_type, channel, totals = None, None, None, None
for line in sys.stdin:
    parts = line.rstrip("\n").split("\t")
    if len(parts) != 8:
        continue
    key = parts[0]
    nums = [float(x) for x in parts[3:]]
    if key != current:
        if current is not None:
            emit(current, room_type, channel, totals)
        current, room_type, channel, totals = key, parts[1], parts[2], [0.0] * 5
    totals = [a + b for a, b in zip(totals, nums)]
if current is not None:
    emit(current, room_type, channel, totals)
