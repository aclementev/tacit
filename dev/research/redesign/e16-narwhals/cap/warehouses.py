"""Q1 warehouses, compile-only (no credentials here): can the narwhals ports be turned into
BigQuery / Snowflake / Databricks / Redshift SQL?
  (a) narwhals -> sqlframe StandaloneSession -> df.sql(dialect=...)
  (b) narwhals -> ibis unbound table -> ibis.to_sql(dialect=...)
Executed for real elsewhere: postgres (sqlframe + ibis), Spark Connect (local server).
usage: uv run python cap/warehouses.py
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent)]
warnings.filterwarnings("ignore")

import ibis  # noqa: E402
import narwhals.stable.v2 as nw  # noqa: E402

import examples_nw as xn  # noqa: E402

ORD = {"order_id": "int64", "customer_id": "int64", "order_ts": "timestamp", "status": "string", "amount": "float64", "discount": "float64"}
CUS = {"customer_id": "int64", "name": "string", "email": "string", "country": "string", "signup_date": "date"}
LI = {"l_orderkey": "int64", "l_quantity": "float64", "l_extendedprice": "float64", "l_discount": "float64", "l_tax": "float64",
      "l_returnflag": "string", "l_linestatus": "string", "l_shipdate": "date"}


def pipelines(o, c, li):
    cl = xn.clean_orders(o)
    return {"tpch_q1": xn.tpch_q1(li), "stats": xn.country_month_stats(cl, c), "status": xn.status_summary(cl), "latest": xn.latest_per_key(cl)}


def via_sqlframe(dialect: str) -> dict[str, str]:
    from sqlframe.standalone import StandaloneSession

    s = StandaloneSession.builder.config("sqlframe.input.dialect", "spark").config("sqlframe.output.dialect", dialect).getOrCreate()
    spark_types = {"int64": "bigint", "float64": "double", "string": "string", "timestamp": "timestamp", "date": "date"}

    def mk(name: str, sch: dict[str, str]):
        s.catalog.add_table(name, {k: spark_types[v] for k, v in sch.items()})
        return nw.from_native(s.table(name))

    out = {}
    for k, v in pipelines(mk("orders", ORD), mk("customers", CUS), mk("lineitem", LI)).items():
        try:
            out[k] = f"OK ({len(nw.to_native(v).sql(dialect=dialect))} chars)"
        except Exception as e:  # noqa: BLE001
            out[k] = f"ERROR {type(e).__name__}: {str(e).splitlines()[0][:120]}"
    return out


def via_ibis(dialect: str) -> dict[str, str]:
    o, c, li = (nw.from_native(ibis.table(sch, name=n)) for n, sch in (("orders", ORD), ("customers", CUS), ("lineitem", LI)))
    out = {}
    for k, v in pipelines(o, c, li).items():
        try:
            out[k] = f"OK ({len(ibis.to_sql(nw.to_native(v), dialect=dialect))} chars)"
        except Exception as e:  # noqa: BLE001
            out[k] = f"ERROR {type(e).__name__}: {str(e).splitlines()[0][:120]}"
    return out


if __name__ == "__main__":
    for d in ["bigquery", "snowflake", "databricks", "redshift", "postgres"]:
        for how, fn in (("sqlframe-standalone", via_sqlframe), ("ibis-unbound", via_ibis)):
            try:
                r = fn(d)
            except Exception as e:  # noqa: BLE001
                r = {"setup": f"ERROR {type(e).__name__}: {str(e).splitlines()[0][:150]}"}
            print(f"{d:10s} {how:20s} " + "  ".join(f"{k}={v.split(' (')[0]}" for k, v in r.items()))
            bad = {k: v for k, v in r.items() if not v.startswith("OK")}
            for k, v in bad.items():
                print(f"{'':32s}{k}: {v}")
