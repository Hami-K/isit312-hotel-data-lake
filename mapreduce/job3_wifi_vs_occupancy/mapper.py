#!/usr/bin/env python3
"""
Job 3 mapper: guest Wi-Fi usage against occupancy, per day.

Input : /datalake/curated/guest_stay_summary   (one CSV row per occupied room per night)
Output: date <TAB> occupied_rooms <TAB> wifi_sessions <TAB> wifi_mb <TAB> rooms_using_wifi
Each row is one occupied room, so occupied_rooms = 1 per record.
"""
import csv
import io
import sys

COUNTS = {}   # Hadoop counters, reported once at the end (shown in the job summary)

def count(name):
    COUNTS[name] = COUNTS.get(name, 0) + 1

stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace")
for row in csv.reader(stdin):
    if not row or row[0] == "date":
        continue
    if len(row) != 12 or not row[0]:
        count("Job3 rows skipped - bad format")
        continue
    date, sessions, mb = row[0], row[10], row[11]
    try:
        sessions, mb = int(sessions or 0), float(mb or 0)
    except ValueError:
        count("Job3 rows skipped - bad number")
        continue
    count("Job3 room-nights read")
    print("%s\t1\t%d\t%.1f\t%d" % (date, sessions, mb, 1 if sessions > 0 else 0))

for name in sorted(COUNTS):
    sys.stderr.write("reporter:counter:Hotel data lake,%s,%d\n" % (name, COUNTS[name]))
