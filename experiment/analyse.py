"""Make the result tables and the two charts (Figures 7.1 and 7.4 in the report)
from results/timings.csv and results/stream.csv.
Run from this folder:  python analyse.py   (needs: pip install matplotlib numpy)
"""
import csv
import os
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

R = "results"


def load(name):
    with open(os.path.join(R, name)) as f:
        return list(csv.DictReader(f))


# ---- Test A: median time per input size --------------------------------
timings = load("timings.csv")
sizes = sorted({int(r["rows"]) for r in timings})
median = {}
for method in ("mapreduce", "python"):
    median[method] = [statistics.median(float(r["seconds"]) for r in timings
                                        if r["method"] == method and int(r["rows"]) == n)
                      for n in sizes]

# ---- Test B: delay per batch -------------------------------------------
stream = load("stream.csv")

# ---- Tables -------------------------------------------------------------
lines = ["## Test A: time to get a result by data size (median of 3 runs)", "",
         "| Input (POS checks) | MapReduce (s) | Plain Python (s) | MapReduce / Python |",
         "|---|---|---|---|"]
for n, mr, py in zip(sizes, median["mapreduce"], median["python"]):
    lines.append(f"| {n:,} | {mr:.1f} | {py:.4f} | {mr / py:,.0f}x |")
lines += ["", "## Test B: a new batch every 10 seconds", "",
          "| Batch | Arrived (s) | Waited in queue (s) | Upload + job (s) | Result ready after arrival (s) |",
          "|---|---|---|---|---|"]
for r in stream:
    lines.append(f"| {r['batch']} | {float(r['arrival_s']):.0f} | {float(r['queue_wait_s']):.1f} | "
                 f"{float(r['job_s']):.1f} | {float(r['data_age_s']):.1f} |")
with open(os.path.join(R, "summary.md"), "w") as f:
    f.write("\n".join(lines) + "\n")
print("\n".join(lines))

# ---- Figure 7.1: Test A ---------------------------------------------------
x = np.arange(len(sizes))
w = 0.38
fig, ax = plt.subplots(figsize=(7, 4))
ax.bar(x - w / 2, median["mapreduce"], w, label="MapReduce")
ax.bar(x + w / 2, median["python"], w, label="Plain Python")
ax.set_xticks(x)
ax.set_xticklabels([f"{n:,} rows" for n in sizes])
ax.set_ylabel("Time (seconds)")
ax.set_ylim(0, max(median["mapreduce"]) * 1.25)
ax.set_title("Test A: Time to get a result by data size")
ax.legend(loc="upper left", ncol=2)
ax.grid(True, axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(os.path.join(R, "fig7.1_test_a_chart.png"), dpi=200)

# ---- Figure 7.4: Test B ---------------------------------------------------
batches = [int(r["batch"]) for r in stream]
delay = [float(r["data_age_s"]) for r in stream]
fig, ax = plt.subplots(figsize=(7, 4))
ax.plot(batches, delay, marker="o")
ax.set_xlabel("Batch number")
ax.set_ylabel("Delay until result is ready (seconds)")
ax.set_title("Test B: Delay per batch (new batch every 10 seconds)")
ax.set_xticks(batches)
ax.set_ylim(0, max(delay) * 1.1)
ax.grid(True, alpha=0.3)
fig.tight_layout()
fig.savefig(os.path.join(R, "fig7.4_test_b_chart.png"), dpi=200)
print("Charts saved in results/")
