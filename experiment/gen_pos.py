"""Generate synthetic POS checks (CSV) for the real-time timing experiment.

Usage: python gen_pos.py --rows 1500 --out data/pos_1500.csv [--seed 1] [--start "2026-10-14 06:00"]

The hotel does ~1,500 POS checks a day (stakeholder answer), so:
  10 rows      ~ the last 10 minutes of sales
  1,500 rows   ~ 1 day
  45,000 rows  ~ 30 days
  547,500 rows ~ 1 year
Column names are a stand-in; swap for #8's generator output if you prefer.
"""
import argparse, csv, os, random
from datetime import datetime, timedelta

OUTLETS = ["All-Day Dining", "Lobby Lounge", "Pool Bar", "Room Service", "Specialty Restaurant"]
PAYMENTS = ["card", "cash", "room_charge"]

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--rows", type=int, required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--start", default="2026-10-14 06:00")
    a = p.parse_args()
    rnd = random.Random(a.seed)
    t = datetime.strptime(a.start, "%Y-%m-%d %H:%M")
    step = timedelta(seconds=86400 / 1500)  # ~1,500 checks per day
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["check_id", "outlet", "room_number", "check_time", "amount_aed", "payment_method"])
        for i in range(a.rows):
            outlet = rnd.choice(OUTLETS)
            pay = rnd.choice(PAYMENTS)
            room = f"{rnd.randint(1, 25)}{rnd.randint(1, 30):02d}" if pay == "room_charge" else ""
            w.writerow([f"C{a.seed:02d}{i:08d}", outlet, room,
                        (t + step * i).strftime("%Y-%m-%d %H:%M:%S"),
                        f"{rnd.uniform(25, 900):.2f}", pay])

if __name__ == "__main__":
    main()
