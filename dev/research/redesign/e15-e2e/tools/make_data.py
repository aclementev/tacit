"""Deterministic e-commerce sources for examples/e2e.py.

    uv run --frozen python e15-e2e/tools/make_data.py [N_ORDERS] [OUT_DIR]

Writes customers.csv (N/8 rows) and orders.csv (order *events*: ~20% of orders appear twice,
an earlier "shipped" event and a later final one), plus orders_bad.csv (4 broken rows) for the
runtime-error transcript. Defaults: 1,200 orders into examples/sources/.
"""

import csv
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

N = int(sys.argv[1]) if len(sys.argv) > 1 else 1200
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parent.parent / "examples" / "sources"
OUT.mkdir(parents=True, exist_ok=True)
rng = random.Random(15)
COUNTRIES = ["ES", "FR", "DE", "IT", "PT"]
n_cust = max(N // 8, 10)

with open(OUT / "customers.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["customer_id", "email", "country", "segment", "signup_date"])
    for cid in range(1, n_cust + 1):
        seg = rng.choice(["consumer", "consumer", "business", ""])
        w.writerow([cid, f"user{cid}@example.com", rng.choice(COUNTRIES), seg,
                    date(2022, 1, 1) + timedelta(days=rng.randrange(700))])


def ts(d: datetime) -> str:
    return d.strftime("%Y-%m-%d %H:%M:%S")


rows = []
for oid in range(1, N + 1):
    ordered = datetime(2024, 1, 1) + timedelta(minutes=rng.randrange(60 * 24 * 180))
    amount = round(rng.uniform(5, 400), 2)
    discount = round(amount * rng.choice([0.05, 0.1, 0.2]), 2) if rng.random() < 0.3 else ""
    status = rng.choices(["delivered", "shipped", "cancelled", "returned"], [70, 12, 10, 8])[0]
    delivered = ordered + timedelta(hours=rng.randrange(12, 24 * 6)) if status in ("delivered", "returned") else None
    base = [oid, rng.randrange(1, n_cust + 1), None, rng.choice(["web", "app"]), amount, discount, ts(ordered)]
    final_ts = (delivered or ordered + timedelta(hours=2)) + timedelta(minutes=5)
    if status == "delivered" and rng.random() < 0.25:  # an earlier event, superseded by the final one
        rows.append(base[:2] + ["shipped"] + base[3:] + ["", ts(ordered + timedelta(hours=1))])
    rows.append(base[:2] + [status] + base[3:] + [ts(delivered) if delivered else "", ts(final_ts)])
rng.shuffle(rows)
header = ["order_id", "customer_id", "status", "channel", "amount", "discount", "ordered_at", "delivered_at", "updated_at"]
with open(OUT / "orders.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(header)
    w.writerows(rows)

if OUT.name == "sources":
    bad = [list(r) for r in rows[:40]]
    bad[3][4] = "12,50"         # decimal comma: not a number
    bad[7][4] = -19.99          # negative amount
    bad[11][2] = "refunded"     # unknown status
    bad[15][6] = ""             # missing ordered_at
    with open(OUT / "orders_bad.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(bad)
print(f"wrote {OUT}: {n_cust} customers, {len(rows)} order events ({N} orders)")
