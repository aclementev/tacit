"""Q4: one-query validation over narwhals, vs pandera (narwhals backend and native backends).

Engine-level counts: duckdb QueryLog rows, polars LazyFrame.collect calls, Spark jobs (job group).
usage:
  uv run python val/run_validation.py tacit  <rows> <backend...>
  PANDERA_USE_NARWHALS_BACKEND=True uv run python val/run_validation.py pandera <rows> <backend...>
  uv run python val/run_validation.py pandera <rows> <backend...>          # pandera native backends
backends: polars, duckdb, ibis-duckdb, pyspark
"""

from __future__ import annotations

import json
import os
import sys
import time
import warnings
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE.parent / "src")]
warnings.filterwarnings("ignore")
# pandera validates pl.LazyFrame / SQL-lazy frames at SCHEMA_ONLY depth by default; force data checks
os.environ.setdefault("PANDERA_VALIDATION_DEPTH", "SCHEMA_AND_DATA")

import numpy as np  # noqa: E402
import polars as pl  # noqa: E402

COUNT = {"polars": 0}
_orig_collect = pl.LazyFrame.collect


def _counting_collect(self: Any, *a: Any, **k: Any) -> Any:
    COUNT["polars"] += 1
    return _orig_collect(self, *a, **k)


pl.LazyFrame.collect = _counting_collect  # type: ignore[method-assign]


def make(n: int, bad: bool) -> pl.DataFrame:
    rng = np.random.default_rng(0)
    status = np.array(["pending", "shipped", "cancelled"])[rng.integers(0, 3, n)].astype(object)
    amount = rng.uniform(0, 500, n).round(2)
    if bad:
        idx = rng.choice(n, max(1, n // 1000), replace=False)
        amount[idx[: len(idx) // 2]] = -1.0
        status[idx[len(idx) // 2:]] = "refunded"
    disc = np.where(rng.random(n) < 0.3, np.nan, rng.uniform(0, 20, n).round(2))
    return pl.DataFrame({
        "order_id": np.arange(n), "customer_id": rng.integers(0, n // 10 + 1, n),
        "status": status.astype(str), "amount": amount, "discount": disc,
        "email": [f"u{i % 997}@x.com" for i in range(n)] if n <= 2_000_000 else None,
    }).with_columns(pl.col("discount").fill_nan(None)).drop_nulls("order_id")


def load(backend: str, df: pl.DataFrame) -> tuple[Any, Any]:
    if backend == "polars":
        return df.lazy(), None
    if backend == "duckdb":
        import duckdb

        con = duckdb.connect()
        con.execute("CREATE TABLE orders AS SELECT * FROM df")
        con.execute("CALL enable_logging('QueryLog')")
        return con.table("orders"), con
    if backend == "ibis-duckdb":
        import ibis

        con = ibis.duckdb.connect()
        t = con.create_table("orders", df)
        con.con.execute("CALL enable_logging('QueryLog')")
        return t, con.con
    if backend == "pyspark":
        sys.path.insert(0, str(HERE.parent))
        from common import spark

        s = spark("pyspark")
        sdf = s.createDataFrame(df.to_arrow()).cache()
        sdf.count()
        return sdf, s
    raise ValueError(backend)


def engine_count(backend: str, h: Any) -> int:
    if backend in ("duckdb", "ibis-duckdb"):
        rows = h.execute("SELECT message FROM duckdb_logs WHERE type='QueryLog'").fetchall()
        return sum(1 for (m,) in rows if "duckdb_logs" not in m and not m.lstrip().upper().startswith(("CALL", "CREATE")))
    if backend == "polars":
        return COUNT["polars"]
    if backend == "pyspark":
        return len(h.sparkContext.statusTracker().getJobIdsForGroup("v"))
    return -1


def reset(backend: str, h: Any) -> None:
    COUNT["polars"] = 0
    if backend in ("duckdb", "ibis-duckdb"):
        h.execute("CALL truncate_duckdb_logs()")
    if backend == "pyspark":
        h.sparkContext.setJobGroup("v" + str(time.time_ns()), "v")
        h.sparkContext.setJobGroup("v", "v")


import tacit_nw as tc  # noqa: E402
from tacit_nw import Column  # noqa: E402


class Orders(tc.Schema):
    order_id: Column[int] = tc.field(unique=True)
    customer_id: Column[int]
    status: Column[str] = tc.field(isin=["pending", "shipped", "cancelled"])
    amount: Column[float] = tc.field(ge=0, le=10_000)
    discount: Column[float | None] = tc.field(ge=0)
    email: Column[str] = tc.field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def tacit_validate(native: Any) -> tuple[bool, int]:
    try:
        Orders.parse(native)
        return True, 0
    except tc.ValidationError as e:
        return False, len(e.issues)


def pandera_validate(backend: str, native: Any) -> tuple[bool, int]:
    if backend == "polars":
        import pandera.polars as pa
    elif backend in ("ibis-duckdb",):
        import pandera.ibis as pa  # type: ignore[no-redef]
    elif backend == "pyspark":
        import pandera.pyspark as pa  # type: ignore[no-redef]
    else:
        raise ValueError("pandera has no duckdb-relation backend (use ibis-duckdb)")
    if backend == "pyspark":
        import pyspark.sql.types as T

        cols = {"order_id": pa.Column(T.LongType(), unique=True) if "unique" in pa.Column.__init__.__code__.co_varnames else pa.Column(T.LongType()),
                "customer_id": pa.Column(T.LongType()),
                "status": pa.Column(T.StringType(), pa.Check.isin(["pending", "shipped", "cancelled"])),
                "amount": pa.Column(T.DoubleType(), [pa.Check.ge(0), pa.Check.le(10_000)]),
                "discount": pa.Column(T.DoubleType(), pa.Check.ge(0), nullable=True),
                "email": pa.Column(T.StringType(), pa.Check.str_matches(r"^[^@\s]+@[^@\s]+\.[^@\s]+$"))}
    else:
        cols = {"order_id": pa.Column(int, unique=True), "customer_id": pa.Column(int),
                "status": pa.Column(str, pa.Check.isin(["pending", "shipped", "cancelled"])),
                "amount": pa.Column(float, [pa.Check.ge(0), pa.Check.le(10_000)]),
                "discount": pa.Column(float, pa.Check.ge(0), nullable=True),
                "email": pa.Column(str, pa.Check.str_matches(r"^[^@\s]+@[^@\s]+\.[^@\s]+$"))}
    schema = pa.DataFrameSchema(cols)
    try:
        out = schema.validate(native, lazy=True)
        if backend == "pyspark":  # pandera.pyspark reports errors on the frame instead of raising
            errs = getattr(out, "pandera", None)
            errors = errs.errors if errs is not None else {}
            n = sum(len(v) for d in errors.values() for v in d.values()) if errors else 0
            return n == 0, n
        return True, 0
    except Exception as e:  # noqa: BLE001
        fc = getattr(e, "failure_cases", None)
        if type(e).__name__ != "SchemaErrors":
            raise
        return False, (len(fc) if fc is not None and hasattr(fc, "__len__") else -1)


if __name__ == "__main__":
    who, n = sys.argv[1], int(sys.argv[2])
    flavour = who + ("-narwhals" if who == "pandera" and os.environ.get("PANDERA_USE_NARWHALS_BACKEND") else "")
    results = []
    for backend in sys.argv[3:]:
        for bad in (False, True):
            df = make(n, bad)
            native, h = load(backend, df)
            for rep in range(2):  # rep 0 = warm-up (imports), rep 1 = measured
                reset(backend, h)
                t0 = time.perf_counter()
                try:
                    ok, nissues = tacit_validate(native) if who == "tacit" else pandera_validate(backend, native)
                    err = ""
                except Exception as e:  # noqa: BLE001
                    ok, nissues, err = False, -1, f"{type(e).__name__}: {str(e).splitlines()[0][:140] if str(e) else ''}"
                dt = time.perf_counter() - t0
            q = engine_count(backend, h)
            r = {"who": flavour, "backend": backend, "rows": n, "bad": bad, "valid": ok, "issues": nissues, "engine_queries": q, "seconds": round(dt, 3), "error": err}
            results.append(r)
            print(json.dumps(r))
            sys.stdout.flush()
    out = HERE.parent / "out" / f"validation_{flavour}_{n}_{'_'.join(sys.argv[3:])}.json"
    out.write_text(json.dumps(results, indent=1))
