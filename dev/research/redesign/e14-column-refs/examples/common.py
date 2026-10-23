"""Data loading shared by the four spellings."""

from pathlib import Path

import ibis
import ibis.expr.types as ir

E6 = Path(__file__).resolve().parents[2] / "e6-agent-trial"


def load() -> tuple[ir.Table, ir.Table]:
    con = ibis.duckdb.connect()
    return con.read_csv(E6 / "orders.csv"), con.read_csv(E6 / "customers.csv")
