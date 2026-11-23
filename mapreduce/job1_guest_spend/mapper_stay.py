#!/usr/bin/env python3
"""
Job 1, stage A mapper: guest spend per STAY.

Input : /datalake/curated/guest_stay_summary   (one CSV row per occupied room per night)
Output: stay_key <TAB> room_type <TAB> booking_channel <TAB> nights <TAB> room_revenue
                 <TAB> pos_checks <TAB> pos_spend <TAB> wifi_mb

Each night of a stay becomes one record with nights = 1, keyed on stay_key, so the
reducer can add up the whole stay. stay_key is the hashed reservation id from curation,
so no guest identity is used here.

Python 3.5 compatible (the Hadoop container's version): no f-strings.
"""
import csv
import io
import sys

COUNTS = {}   # Hadoop counters, reported once at the end (shown in the job summary)

def count(name):
    COUNTS[name] = COUNTS.get(name, 0) + 1

stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace")
for row in csv.reader(stdin):
    if not row or row[0] == "date":                 # header line of the curated file
        continue
    if len(row) != 12:
        count("Job1 rows skipped - bad format")
        continue
    (date, room, stay_key, room_type, rate, channel, ci, co,
     pos_checks, pos_spend, wifi_sessions, wifi_mb) = row
    if not stay_key or not room_type or not rate:
        count("Job1 rows skipped - missing room_type or rate")
        continue
    try:
        values = [1, float(rate), int(pos_checks or 0), float(pos_spend or 0),
                  float(wifi_mb or 0)]
    except ValueError:
        count("Job1 rows skipped - bad number")
        continue
    count("Job1 room-nights read")
    print("\t".join([stay_key, room_type, channel or "Unknown"] + [str(v) for v in values]))

for name in sorted(COUNTS):
    sys.stderr.write("reporter:counter:Hotel data lake,%s,%d\n" % (name, COUNTS[name]))
