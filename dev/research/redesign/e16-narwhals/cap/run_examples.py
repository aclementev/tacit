"""Run the narwhals ports of the three examples on every backend; compare with the ibis-duckdb reference.

usage: uv run python cap/run_examples.py [backend ...]   (E16_PG=... enables the postgres backends)
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE)]

import narwhals.stable.v2 as nw  # noqa: E402
import polars as pl  # noqa: E402

import examples_ibis as xi  # noqa: E402
import examples_nw as xn  # noqa: E402
from common import collect_polars, example_frames, ibis_con, same, to_native  # noqa: E402

BACKENDS = ["polars-eager", "polars-lazy", "duckdb", "pyspark", "pyspark-connect", "sqlframe-duckdb", "ibis-duckdb", "ibis-polars"]
if os.environ.get("E16_PG"):
    BACKENDS += ["sqlframe-postgres", "ibis-postgres"]


def reference() -> dict[str, pl.DataFrame]:
    con = ibis_con("duckdb")
    fr = example_frames()
    t = {k: con.create_table(f"ref_{k}", v, overwrite=True) for k, v in fr.items()}
    out = {"iris": xi.iris(t["iris"]), "tpch_q1": xi.tpch_q1(t["lineitem"])}
    out |= {f"ecom.{k}": v for k, v in xi.ecommerce(t["orders"], t["customers"]).items()}
    return {k: pl.from_arrow(v.to_pyarrow()) for k, v in out.items()}  # type: ignore[misc]


def run_backend(b: str, ref: dict[str, pl.DataFrame]) -> dict[str, str]:
    fr = example_frames()
    try:
        nat = {k: to_native(b, k, v) for k, v in fr.items()}
        f = {k: nw.from_native(v) for k, v in nat.items()}
    except Exception as e:  # noqa: BLE001
        return {"load": f"LOAD-ERROR {type(e).__name__}: {str(e).splitlines()[0][:160]}"}
    jobs = {
        "iris": lambda: xn.iris(f["iris"]),
        "tpch_q1": lambda: xn.tpch_q1(f["lineitem"]),
    }
    cleaned = lambda: xn.clean_orders(f["orders"])  # noqa: E731
    jobs["ecom.stats"] = lambda: xn.country_month_stats(cleaned(), f["customers"])
    jobs["ecom.status"] = lambda: xn.status_summary(cleaned())
    jobs["ecom.latest"] = lambda: xn.latest_per_key(cleaned())
    jobs["ecom.latest_max"] = lambda: xn.latest_per_key_rowidx(cleaned())
    jobs["ecom.checks"] = lambda: xn.validate_customers(f["customers"])
    res: dict[str, str] = {}
    for name, fn in jobs.items():
        t0 = time.perf_counter()
        try:
            got = collect_polars(fn())
            ok, why = same(ref[name], got)
            res[name] = "OK" if ok else f"DIFF {why}"
        except Exception as e:  # noqa: BLE001
            msg = str(e).strip().splitlines()[0][:200] if str(e).strip() else ""
            res[name] = f"ERROR {type(e).__name__}: {msg}"
            if os.environ.get("E16_TB"):
                traceback.print_exc()
        res[name] += f"  ({time.perf_counter() - t0:.2f}s)"
    return res


def run_ibis_native(b: str, ref: dict[str, pl.DataFrame]) -> dict[str, str]:
    """The ibis reference implementation itself on another ibis backend (ibis's own coverage)."""
    fr = example_frames()
    t = {k: to_native(b, k, v) for k, v in fr.items()}
    jobs = {"iris": lambda: xi.iris(t["iris"]), "tpch_q1": lambda: xi.tpch_q1(t["lineitem"])}
    for k in ["stats", "status", "latest", "latest_max", "checks"]:
        jobs[f"ecom.{k}"] = lambda k=k: xi.ecommerce(t["orders"], t["customers"])[k]
    res = {}
    for name, fn in jobs.items():
        try:
            got = pl.from_arrow(fn().to_pyarrow())
            ok, why = same(ref[name], got)  # type: ignore[arg-type]
            res[name] = "OK" if ok else f"DIFF {why}"
        except Exception as e:  # noqa: BLE001
            res[name] = f"ERROR {type(e).__name__}: {str(e).strip().splitlines()[0][:200] if str(e).strip() else ''}"
    return res


if __name__ == "__main__" and sys.argv[1:2] == ["--ibis-native"]:
    ref = reference()
    for b in sys.argv[2:]:
        print(f"== ibis-native on {b}")
        for k, v in run_ibis_native(b, ref).items():
            print(f"   {k:16s} {v}")
    sys.exit(0)

if __name__ == "__main__":
    ref = reference()
    todo = sys.argv[1:] or BACKENDS
    allres = {}
    for b in todo:
        r = run_backend(b, ref)
        allres[b] = r
        print(f"== {b}")
        for k, v in r.items():
            print(f"   {k:16s} {v}")
        sys.stdout.flush()
    out = HERE.parent / "out" / f"examples_{'_'.join(todo) if sys.argv[1:] else 'all'}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(allres, indent=1))

