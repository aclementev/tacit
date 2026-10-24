"""What the plain ibis + pandera version reports for the same bad CSV (for comparison with out/session.txt)."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "examples"))
import ibis  # noqa: E402
import pandera.errors as pe  # noqa: E402

import e2e_plain as P  # noqa: E402

con = ibis.duckdb.connect()
bad = HERE / "examples" / "sources" / "orders_bad.csv"
print(">>> OrderEvents.validate(read(con, 'orders_bad.csv'))")
try:
    P.OrderEvents.validate(P.read(con, bad))
except pe.SchemaError as e:
    print(f"{type(e).__name__}: {e}")
print("\n>>> OrderEvents.validate(read(con, 'orders_bad.csv'), lazy=True)")
try:
    P.OrderEvents.validate(P.read(con, bad), lazy=True)
except pe.SchemaErrors as e:
    print(f"{type(e).__name__}: {e}")
print("\n>>> # coerce by hand (pandera's ibis backend ignores coerce=True): amount.try_cast('float64')")
fixed = con.read_csv(bad).mutate(amount=ibis._.amount.try_cast("float64"))
fixed = fixed.cast({c: "timestamp" for c, d in fixed.schema().items() if d.is_timestamp()})
try:
    P.OrderEvents.validate(fixed, lazy=True)
except pe.SchemaErrors as e:
    print(f"{type(e).__name__}: {e}")
