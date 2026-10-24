"""Shared helpers for E16: example data, backend loaders, result normalisation.

Backends (native objects handed to `nw.from_native`):
  polars-eager, polars-lazy, duckdb, pyspark, pyspark-connect, sqlframe-duckdb,
  ibis-duckdb, ibis-polars, and (if E16_PG is set, e.g. "postgresql://postgres:pw@127.0.0.1:55432/postgres")
  sqlframe-postgres, ibis-postgres.
"""

from __future__ import annotations

import os
import warnings
from datetime import date, datetime
from pathlib import Path
from typing import Any

import polars as pl

warnings.filterwarnings("ignore")

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
E6 = HERE.parent / "e6-agent-trial"
DATA = REPO / "examples" / "data"


def example_frames() -> dict[str, pl.DataFrame]:
    """The data the three E8/E13 examples run on, read once with polars (types made explicit)."""
    iris = pl.read_csv(DATA / "iris.csv")
    li = pl.read_csv(DATA / "lineitem.csv", try_parse_dates=True)
    orders = pl.read_csv(E6 / "orders.csv", try_parse_dates=True).with_columns(
        pl.col("amount").cast(pl.Float64), pl.col("discount").cast(pl.Float64)
    )
    customers = pl.read_csv(E6 / "customers.csv", try_parse_dates=True)
    return {"iris": iris, "lineitem": li, "orders": orders, "customers": customers}


# --------------------------------------------------------------------------- spark
_SPARK: dict[str, Any] = {}


def spark(kind: str = "pyspark") -> Any:
    if kind in _SPARK:
        return _SPARK[kind]
    from pyspark.sql import SparkSession

    os.environ.setdefault("PYSPARK_PYTHON", os.sys.executable)  # type: ignore[attr-defined]
    b = SparkSession.builder.config("spark.ui.enabled", "false").config("spark.sql.shuffle.partitions", "4")
    b = b.config("spark.sql.session.timeZone", "UTC").config("spark.driver.memory", "4g")
    if kind == "pyspark-connect":
        s = b.remote("local[4]").getOrCreate()
    else:
        s = b.master("local[4]").getOrCreate()
        s.sparkContext.setLogLevel("ERROR")
    _SPARK[kind] = s
    return s


_DUCK: dict[str, Any] = {}


def duck() -> Any:
    import duckdb

    if "con" not in _DUCK:
        _DUCK["con"] = duckdb.connect()
    return _DUCK["con"]


def ibis_con(kind: str) -> Any:
    import ibis

    key = f"ibis-{kind}"
    if key not in _DUCK:
        if kind == "duckdb":
            _DUCK[key] = ibis.duckdb.connect()
        elif kind == "polars":
            _DUCK[key] = ibis.polars.connect()
        elif kind == "postgres":
            _DUCK[key] = ibis.connect(os.environ["E16_PG"])
        elif kind == "pyspark":
            _DUCK[key] = ibis.pyspark.connect(spark("pyspark"))
    return _DUCK[key]


def sqlframe_session(kind: str) -> Any:
    key = f"sqlframe-{kind}"
    if key not in _DUCK:
        if kind == "duckdb":
            from sqlframe.duckdb import DuckDBSession

            _DUCK[key] = DuckDBSession()
        elif kind == "postgres":
            import psycopg2  # type: ignore[import-untyped]
            from sqlframe.postgres import PostgresSession

            _DUCK[key] = PostgresSession(conn=psycopg2.connect(os.environ["E16_PG"]))
    return _DUCK[key]


_PG_N = [0]

_DDL = {pl.Int64: "bigint", pl.Int32: "int", pl.Float64: "double", pl.String: "string", pl.Date: "date", pl.Boolean: "boolean"}


def ddl(df: pl.DataFrame) -> str:
    """Spark-style DDL schema for createDataFrame(rows, schema=...)."""
    parts = []
    for n, t in df.schema.items():
        typ = "timestamp_ntz" if isinstance(t, pl.Datetime) else _DDL[t.base_type()]  # type: ignore[index]
        parts.append(f"{n} {typ}")
    return ", ".join(parts)


def to_native(backend: str, name: str, df: pl.DataFrame) -> Any:
    """Load a polars DataFrame into `backend`, returning the backend's native frame."""
    if backend == "polars-eager":
        return df
    if backend == "polars-lazy":
        return df.lazy()
    if backend == "duckdb":  # default connection, the way `duckdb.sql(...)` users get relations
        import duckdb

        return duckdb.from_arrow(df.to_arrow())
    if backend == "duckdb-conn":  # explicit connection, the way applications usually hold one
        con = duck()
        arrow = df.to_arrow()  # noqa: F841  (referenced by name below)
        con.register(f"_{name}", arrow)
        return con.table(f"_{name}")
    if backend in ("pyspark", "pyspark-connect"):
        s = spark(backend)
        return s.createDataFrame(df.rows(), schema=ddl(df))
    if backend == "sqlframe-duckdb":
        sess = sqlframe_session("duckdb")
        # sess.table() over a registered arrow view fails inside sqlframe's column resolution; use createDataFrame
        # (to_pandas() would turn nulls into NaN, which SQL engines treat as non-null)
        return sess.createDataFrame(df.rows(), schema=ddl(df))
    if backend.startswith("ibis-"):
        import ibis

        con = ibis_con(backend.removeprefix("ibis-"))
        tname = f"t_{name}"
        if backend == "ibis-pyspark":
            spark("pyspark").createDataFrame(df.rows(), schema=ddl(df)).createOrReplaceTempView(tname)
            return con.table(tname)
        if backend == "ibis-postgres":
            _PG_N[0] += 1
            tname = f"t_{name}_{_PG_N[0]}"
            return con.create_table(tname, ibis.memtable(df.to_arrow()), overwrite=True)
        return con.create_table(tname, df, overwrite=True)
    if backend == "sqlframe-postgres":
        import ibis

        _PG_N[0] += 1
        tname = f"s_{name}_{_PG_N[0]}"
        ibis_con("postgres").create_table(tname, ibis.memtable(df.to_arrow()), overwrite=True)
        _ = ibis
        return sqlframe_session("postgres").table(tname)
    raise ValueError(backend)


FALLBACKS: list[str] = []


def collect_polars(x: Any) -> pl.DataFrame:
    """narwhals frame (eager or lazy) -> polars DataFrame."""
    import narwhals as nw  # main-namespace classes are the bases of the stable.v2 ones

    if isinstance(x, nw.LazyFrame):
        try:
            x = x.collect(backend="polars")
        except NotImplementedError:
            # sqlframe engines without Arrow support (postgres): narwhals' collect() needs toArrow();
            # fall back to the native row API. Recorded as a narwhals/sqlframe gap.
            rows = nw.to_native(x).collect()
            FALLBACKS.append("sqlframe-rows")
            return pl.DataFrame([r.asDict() for r in rows])
    if isinstance(x, nw.DataFrame):
        return x.to_polars()
    if isinstance(x, pl.LazyFrame):
        return x.collect()
    if isinstance(x, pl.DataFrame):
        return x
    raise TypeError(type(x))


def normalise(df: pl.DataFrame) -> pl.DataFrame:
    """Order-insensitive, float-rounded, dtype-relaxed view for comparison across engines."""
    exprs = []
    for n, t in df.schema.items():
        c = pl.col(n)
        if t.is_float() or t.is_decimal():
            c = c.cast(pl.Float64).round(6)
        elif t.is_integer():
            c = c.cast(pl.Int64)
        elif isinstance(t, pl.Datetime):
            c = c.dt.replace_time_zone(None).cast(pl.Datetime("us"))
        exprs.append(c.alias(n))
    out = df.select(exprs)
    return out.sort(out.columns, nulls_last=True) if out.height else out


def same(a: pl.DataFrame, b: pl.DataFrame) -> tuple[bool, str]:
    a, b = normalise(a), normalise(b)
    if a.columns != b.columns and sorted(a.columns) == sorted(b.columns):
        b = b.select(a.columns)  # column order only (e.g. pivot output) -- not counted as a difference
    if a.columns != b.columns:
        return False, f"columns {a.columns} vs {b.columns}"
    if a.shape != b.shape:
        return False, f"shape {a.shape} vs {b.shape}"
    try:
        b = b.cast(a.schema, strict=False)  # type: ignore[arg-type]
    except Exception:
        pass
    if a.equals(b):
        return True, ""
    for col in a.columns:
        if not a[col].equals(b[col]):
            return False, f"col {col}: {a[col].head(3).to_list()} vs {b[col].head(3).to_list()}"
    return False, "dtype"


_ = (date, datetime)
