#!/usr/bin/env python3
"""
Job 1, stage B mapper: reads the per-stay output of stage A and re-keys it by room type.

Input : stay_key <TAB> room_type <TAB> channel <TAB> nights <TAB> room_revenue <TAB> pos_checks
              <TAB> pos_spend <TAB> wifi_mb
Output: room_type <TAB> stays <TAB> nights <TAB> room_revenue <TAB> pos_spend
              <TAB> stays_with_fnb_spend
Every stay is also sent to the key "All room types", which gives the hotel-wide total.
"""
import sys

for line in sys.stdin:
    parts = line.rstrip("\n").split("\t")
    if len(parts) != 8:
        continue
    room_type = parts[1]
    nights, room_rev, pos_checks, pos_spend = (float(parts[3]), float(parts[4]),
                                               float(parts[5]), float(parts[6]))
    values = "\t".join(["1", "%d" % nights, "%.2f" % room_rev, "%.2f" % pos_spend,
                        "1" if pos_checks > 0 else "0"])
    print(room_type + "\t" + values)
    print("All room types\t" + values)
