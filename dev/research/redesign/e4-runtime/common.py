"""Shared helpers: schema, data generation, duckdb query logging."""
from __future__ import annotations

import time
from contextlib import contextmanager
from datetime import datetime
from typing import Annotated

import ibis
import tacit
from tacit import Check, Nullable

STATUSES = ["active", "inactive", "pending", "closed"]


class Customer(tacit.Schema):
    """10 columns, 10 checks (+ nullability on 4 columns)."""

    id: int                                                              # non-null
    age: Annotated[int, Check.ge(0), Check.le(120)]                      # 2 checks
    score: Annotated[float, Check.ge(0.0), Check.le(1.0), Nullable()]    # 2 checks, nullable
    status: Annotated[str, Check.isin(STATUSES)]                         # 1 check
    email: Annotated[str, Check.str_matches(r"^[^@]+@[^@]+\.[a-z]+$")]  # 1 check
    country: Annotated[str, Check.str_length(2, 2)]                      # 1 check
    amount: Annotated[float, Check.ge(0.0)]                              # 1 check
    qty: Annotated[int, Check.gt(0)]                                     # 1 check
    created: Annotated[datetime, Nullable()]                             # nullable
    note: Annotated[str, Nullable()]                                     # nullable


def gen_sql(n: int, bad_rate: float = 0.0, as_varchar: bool = False) -> str:
    """SQL that generates n rows of Customer-shaped data.

    bad_rate > 0 injects violations into several columns (about bad_rate each).
    """
    thr = int(1 / bad_rate) if bad_rate else 0

    def bad(i: str, good: str, badv: str) -> str:
        if not thr:
            return good
        return f"CASE WHEN {i} % {thr} = 7 THEN {badv} ELSE {good} END"

    cols = {
        "id": "i",
        "age": bad("i", "(i % 100)::BIGINT", "-5::BIGINT"),
        "score": "CASE WHEN i % 10 = 3 THEN NULL ELSE " + bad("i", "random()", "1.5") + " END",
        "status": bad("i", "(['active','inactive','pending','closed'])[1 + i % 4]", "'bogus'"),
        "email": bad("i", "'user' || i || '@example.com'", "'not-an-email'"),
        "country": bad("i", "(['US','DE','FR','ES','IT'])[1 + i % 5]", "'USA'"),
        "amount": bad("i", "((i % 1000) * 1.5)::DOUBLE", "-1.0::DOUBLE"),
        "qty": bad("i", "1 + i % 20", "0::BIGINT"),
        "created": "CASE WHEN i % 17 = 0 THEN NULL ELSE TIMESTAMP '2024-01-01' + to_seconds(i % 31536000) END",
        "note": "CASE WHEN i % 3 = 0 THEN NULL ELSE 'note ' || (i % 100) END",
    }
    sel = ", ".join(
        f"CAST(({e}) AS VARCHAR) AS {k}" if as_varchar else f"({e}) AS {k}" for k, e in cols.items()
    )
    return f"SELECT {sel} FROM (SELECT unnest(range({n}))::BIGINT AS i)"


def make_con(n: int, bad_rate: float = 0.0, as_varchar: bool = False, name: str = "t", threads: int | None = None):
    con = ibis.duckdb.connect()
    if threads:
        con.raw_sql(f"SET threads={threads}")
    con.raw_sql(f"CREATE TABLE {name} AS {gen_sql(n, bad_rate, as_varchar)}")
    con.raw_sql("CALL enable_logging('QueryLog')")
    return con, con.table(name)


def log_reset(con):
    con.raw_sql("CALL truncate_duckdb_logs()")


def log_queries(con):
    """Return list of logged data queries since last reset (excluding DESCRIBE/housekeeping)."""
    rows = con.raw_sql("SELECT message FROM duckdb_logs WHERE type = 'QueryLog' ORDER BY timestamp").fetchall()
    out = []
    for (m,) in rows:
        s = m.strip()
        if not s or s.startswith(("DESCRIBE", "SELECT CURRENT_", "CALL ", "SELECT message FROM duckdb_logs")):
            continue
        out.append(s)
    return out


def log_describe_count(con):
    rows = con.raw_sql("SELECT message FROM duckdb_logs WHERE type = 'QueryLog'").fetchall()
    return sum(1 for (m,) in rows if m.strip().startswith("DESCRIBE"))


@contextmanager
def timer():
    r = {}
    t0 = time.perf_counter()
    yield r
    r["s"] = time.perf_counter() - t0
