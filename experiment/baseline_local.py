"""Same calculation as the MapReduce job (checks + revenue per outlet), in plain Python.
Prints the elapsed time in seconds. Used as the 'what if no job overhead' baseline.
Usage: python baseline_local.py data/pos_1500.csv
"""
import sys, time
t0 = time.perf_counter()
agg = {}
with open(sys.argv[1]) as f:
    next(f)
    for line in f:
        p = line.rstrip("\n").split(",")
        n, s = agg.get(p[1], (0, 0.0))
        agg[p[1]] = (n + 1, s + float(p[4]))
elapsed = time.perf_counter() - t0
print(f"{elapsed:.4f}")
