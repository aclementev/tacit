"""Merge out/ops_*.json into one matrix (out/ops_matrix.txt)."""
import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "out"
sys.path.insert(0, str(Path(__file__).parent))
res: dict[str, dict[str, str]] = {}
for p in sorted(OUT.glob("ops_*.json")):
    mode = p.stem.split("_")[1]
    for b, r in json.loads(p.read_text()).items():
        res[f"{mode}:{b}"] = r
order = ["nw:polars-eager", "nw:polars-lazy", "nw:duckdb", "nw:duckdb-conn", "nw:pyspark", "nw:pyspark-connect",
         "nw:sqlframe-duckdb", "nw:sqlframe-postgres", "nw:ibis-duckdb", "nw:ibis-postgres",
         "ibis:ibis-duckdb", "ibis:ibis-polars", "ibis:ibis-postgres", "ibis:ibis-pyspark"]
cols = [c for c in order if c in res]
names = list(next(iter(res.values())).keys())
def code(v: str) -> str:
    if v.startswith("OK"): return "ok"
    if v.startswith("DIFF"): return "DIFF"
    if v.startswith("n/a"): return "-"
    if v.startswith("UNSUP"): return "unsup"
    return "err"
lines = ["case".ljust(28) + " ".join(c.split(":")[0][:2] + ":" + c.split(":")[1][:11].ljust(11) for c in cols)]
for n in names:
    lines.append(n.ljust(28) + " ".join(code(res[c].get(n, "?")).ljust(14) for c in cols))
lines.append("")
for c in cols:
    vals = [code(v) for v in res[c].values()]
    lines.append(f"{c:24s} ok {vals.count('ok'):2d}  DIFF {vals.count('DIFF'):2d}  unsup {vals.count('unsup'):2d}  err {vals.count('err'):2d}  n/a {vals.count('-'):2d}  of {len(vals)}")
txt = "\n".join(lines)
(OUT / "ops_matrix.txt").write_text(txt + "\n")
print(txt)
