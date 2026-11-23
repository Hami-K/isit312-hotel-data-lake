#!/usr/bin/env python3
# Hadoop Streaming mapper: emit outlet <TAB> amount for each POS check.
import sys
for line in sys.stdin:
    parts = line.rstrip("\n").split(",")
    if len(parts) < 6 or parts[0] == "check_id":
        continue
    try:
        print(f"{parts[1]}\t{float(parts[4]):.2f}")
    except ValueError:
        continue
