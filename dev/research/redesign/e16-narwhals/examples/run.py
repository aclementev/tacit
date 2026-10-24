"""Run the tacit_nw (T2-on-narwhals) examples and the native polars/PySpark examples on each backend,
comparing with the ibis-duckdb reference (cap/examples_ibis.py). Also count validation queries.

usage: uv run python examples/run.py <backend ...>    (backends as in common.py; plus native-polars, native-pyspark)
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE.parent / "cap"), str(HERE.parent / "src"), str(HERE)]

import narwhals.stable.v2 as nw  # noqa: E402
import polars as pl  # noqa: E402

import t2nw  # noqa: E402
from common import collect_polars, example_frames, same, to_native  # noqa: E402
from run_examples import reference  # noqa: E402
from tacit_nw._validate import STATS  # noqa: E402

ECOM = {"stats": "ecom.stats", "status": "ecom.status", "latest": "ecom.latest"}


def as_pl(x: object) -> pl.DataFrame:
    if isinstance(x, (nw.LazyFrame, nw.DataFrame)):
        return collect_polars(x)
    return collect_polars(nw.from_native(x))


def run(backend: str, ref: dict[str, pl.DataFrame]) -> dict[str, str]:
    fr = example_frames()
    res: dict[str, str] = {}
    native_mode = backend.startswith("native-")
    load = "polars-eager" if backend == "native-polars" else "pyspark" if backend == "native-pyspark" else backend
    nat = {k: to_native(load, k, v) for k, v in fr.items()}
    jobs: dict[str, object] = {}
    if native_mode:
        import native

        fn = native.ecommerce_polars if backend == "native-polars" else native.ecommerce_spark
        jobs = {"ecom": lambda: fn(nat["orders"], nat["customers"])}
    else:
        jobs = {"iris": lambda: t2nw.iris(nat["iris"]), "tpch_q1": lambda: t2nw.tpch_q1(nat["lineitem"]),
                "ecom": lambda: t2nw.ecommerce(nat["orders"], nat["customers"])}
    for name, job in jobs.items():
        STATS["queries"] = 0
        try:
            out = job()  # type: ignore[operator]
            q = STATS["queries"]
            outs = {ECOM[k]: v for k, v in out.items()} if name == "ecom" else {name: out}
            for k, v in outs.items():
                ok, why = same(ref[k], as_pl(v))
                res[k] = ("OK" if ok else f"DIFF {why}")
            res[f"{name}.validation_queries"] = str(q)
        except Exception as e:  # noqa: BLE001
            res[name] = f"ERROR {type(e).__name__}: {str(e).strip().splitlines()[0][:200] if str(e).strip() else ''}"
            if os.environ.get("E16_TB"):
                traceback.print_exc()
    return res


if __name__ == "__main__":
    ref = reference()
    for b in sys.argv[1:]:
        print(f"== {b}")
        for k, v in run(b, ref).items():
            print(f"   {k:28s} {v}")
        sys.stdout.flush()
