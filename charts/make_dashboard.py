"""Reporting layer: builds 4 charts and a static HTML dashboard from the MapReduce CSVs.
Usage: python make_dashboard.py [input_dir] [output_dir]
Defaults: ./mapreduce_output  ->  ./reporting_output
"""
import sys, base64
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

IN = Path(sys.argv[1] if len(sys.argv) > 1 else "mapreduce_output")
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "reporting_output")
OUT.mkdir(parents=True, exist_ok=True)
C1, C2, C3 = "#1f4e79", "#e07b39", "#7f7f7f"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})

def save(fig, name):
    fig.tight_layout(); fig.savefig(OUT / name, dpi=150); plt.close(fig)

# 1. Guest spend per stay by room type (Job 1: PMS + POS)
d = pd.read_csv(IN / "guest_spend_by_room_type.csv")
d = d[d.room_type != "All room types"].sort_values("avg_total_spend_per_stay")
fig, ax = plt.subplots(figsize=(8, 4))
ax.barh(d.room_type, d.avg_room_revenue_per_stay, color=C1, label="Room revenue")
ax.barh(d.room_type, d.avg_fnb_spend_per_stay, left=d.avg_room_revenue_per_stay, color=C2, label="F&B spend")
for i, (t, s) in enumerate(zip(d.avg_total_spend_per_stay, d.fnb_share_pct)):
    ax.text(t + 60, i, f"{t:,.0f}  (F&B {s:.0f}%)", va="center", fontsize=9)
ax.set_xlim(0, d.avg_total_spend_per_stay.max() * 1.25)
ax.set_xlabel("Average spend per stay (AED)"); ax.set_title("Guest spend per stay by room type")
ax.legend(loc="lower right", frameon=False); save(fig, "chart1_guest_spend.png")

# 2. Purchasing cost vs ERP revenue (Job 2: procurement + ERP)
c = pd.read_csv(IN / "cost_vs_revenue.csv")
c = c[(c.department != "All departments") & (c.purchase_cost > 0)].sort_values("purchase_cost", ascending=False)
fig, ax = plt.subplots(figsize=(8, 4))
x = range(len(c)); w = 0.4
ax.bar([i - w/2 for i in x], c.purchase_cost / 1e6, w, color=C1, label="Purchasing cost")
ax.bar([i + w/2 for i in x], c.erp_revenue / 1e6, w, color=C2, label="ERP revenue")
ax.set_xticks(list(x)); ax.set_xticklabels(c.department, rotation=30, ha="right")
ax.set_ylabel("AED million"); ax.set_title("Purchasing cost vs ERP revenue by department (October)")
ax.legend(frameon=False); save(fig, "chart2_cost_vs_revenue.png")

# 3. Wi-Fi vs occupancy (Job 3: Wi-Fi + PMS)
w_ = pd.read_csv(IN / "wifi_vs_occupancy.csv", parse_dates=["date"])
r = w_.occupancy_pct.corr(w_.wifi_gb)
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4))
a1.plot(w_.date, w_.occupancy_pct, color=C1, label="Occupancy %")
a1.set_ylabel("Occupancy (%)", color=C1); a1.tick_params(axis="x", rotation=45)
b = a1.twinx(); b.spines["right"].set_visible(True)
b.plot(w_.date, w_.wifi_gb, color=C2, label="Wi-Fi GB"); b.set_ylabel("Wi-Fi data (GB/day)", color=C2)
a1.set_title("Daily occupancy and Wi-Fi data")
a2.scatter(w_.occupancy_pct, w_.wifi_gb, color=C1)
a2.set_xlabel("Occupancy (%)"); a2.set_ylabel("Wi-Fi data (GB/day)")
a2.set_title(f"Occupancy vs Wi-Fi data (r = {r:.2f})")
save(fig, "chart3_wifi_vs_occupancy.png")

# 4. Reviews vs operations (Job 4: reviews + PMS)
v = pd.read_csv(IN / "reviews_vs_operations.csv")
rt, th = v[v.group == "Room type"], v[v.group == "Theme"].sort_values("pct_negative")
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4))
a1.bar(rt.name, rt.avg_score, color=C1); a1.set_ylim(0, 10)
for i, s in enumerate(rt.avg_score): a1.text(i, s + 0.15, f"{s:.2f}", ha="center", fontsize=9)
a1.set_ylabel("Average score (out of 10)"); a1.set_title("Review score by room type")
a1.tick_params(axis="x", rotation=30)
a2.barh(th.name, th.pct_negative, color=C2)
for i, p in enumerate(th.pct_negative): a2.text(p + 1, i, f"{p:.0f}%", va="center", fontsize=9)
a2.set_xlim(0, 70); a2.set_xlabel("Negative mentions (%)"); a2.set_title("Negative mentions by theme in review text")
save(fig, "chart4_reviews_vs_operations.png")

# Static dashboard (images embedded, single file)
cards = [
 ("chart1_guest_spend.png", "1. Guest spend per stay", "PMS + POS", "room_number + date", "Job 1 (1a + 1b)", "How much does a guest spend per stay, by room type?"),
 ("chart2_cost_vs_revenue.png", "2. Purchasing cost vs revenue", "Procurement + ERP", "department + date", "Job 2", "How do purchasing costs compare with revenue in each department?"),
 ("chart3_wifi_vs_occupancy.png", "3. Wi-Fi usage vs occupancy", "Wi-Fi + PMS", "room_number + date", "Job 3", "Does Wi-Fi demand rise with occupancy?"),
 ("chart4_reviews_vs_operations.png", "4. Reviews vs operations", "Reviews + PMS", "reservation_id", "Job 4", "Which room types and hotel areas drive review scores?"),
]
html = ["<!DOCTYPE html><html><head><meta charset='utf-8'><title>Hotel Data Lake Dashboard</title><style>",
 "body{font-family:Arial,sans-serif;max-width:1100px;margin:auto;padding:20px;color:#222}",
 "h1{color:#1f4e79}.card{border:1px solid #ddd;border-radius:6px;padding:14px;margin:18px 0}",
 ".meta{color:#555;font-size:13px}img{max-width:100%}.note{font-size:12px;color:#777;margin-top:30px}",
 "</style></head><body><h1>Hotel Data Lake: Consolidated Reports</h1>",
 "<p class='meta'>Source: MapReduce output on the Curated zone, October 2026 (synthetic data).</p>"]
for img, title, srcs, key, job, q in cards:
    b64 = base64.b64encode((OUT / img).read_bytes()).decode()
    html.append(f"<div class='card'><h2>{title}</h2><p class='meta'>{q}<br>Sources: {srcs} | Join key: {key} | Produced by: {job}</p>"
                f"<img src='data:image/png;base64,{b64}' alt='{title}'></div>")
html.append("<p class='note'>All data is synthetic. Patterns reflect how the generator was written, not real hotel behaviour.</p></body></html>")
(OUT / "dashboard.html").write_text("\n".join(html), encoding="utf-8")
print("Done:", sorted(p.name for p in OUT.iterdir()), f"| Wi-Fi r = {r:.2f}")
