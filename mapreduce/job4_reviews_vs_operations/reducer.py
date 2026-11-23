#!/usr/bin/env python3
"""
Job 4 reducer: average score and share of complaints per room type and per theme.

Output (final): group, name, reviews, avg_score, pct_low_scores, avg_nights,
                negative_mentions, pct_negative   (the last two only for themes)
Run with --combine to act as the combiner (outputs partial sums in the input layout).
"""
import sys

COMBINE = "--combine" in sys.argv

def emit(key, t):
    n, score, low, nights, neg = t
    if COMBINE:
        print("%s\t%d\t%d\t%d\t%d\t%d" % (key, n, score, low, nights, neg))
        return
    group, name = key.split("|", 1)
    is_theme = group == "Theme"
    print("\t".join([group, name, "%d" % n, "%.2f" % (score / n), "%.1f" % (100.0 * low / n),
                     "%.2f" % (nights / n),
                     "%d" % neg if is_theme else "",
                     "%.1f" % (100.0 * neg / n) if is_theme else ""]))

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
