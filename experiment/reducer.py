#!/usr/bin/env python3
# Hadoop Streaming reducer: checks and revenue per outlet (input is sorted by key).
import sys
cur, n, total = None, 0, 0.0
for line in sys.stdin:
    key, val = line.rstrip("\n").split("\t", 1)
    if key != cur:
        if cur is not None:
            print(f"{cur}\t{n}\t{total:.2f}")
        cur, n, total = key, 0, 0.0
    n += 1
    total += float(val)
if cur is not None:
    print(f"{cur}\t{n}\t{total:.2f}")
