"""Runtime side of the conformance harness: what ibis actually does for each case.

python runtime.py OUT.json      (needs only ibis[duckdb]; run under any ibis version)

For each case: build the expression on real ibis columns of the right dtype
(non-null dtypes `!int64` etc. for non-null receivers), record exception or
result kind (column/scalar/table/other), dtype family, ibis dtype nullability,
then execute it on duckdb (per-group for reductions, so all-NULL groups and
single-row groups are exercised) and record whether NULL / NaN appear.
"""

from __future__ import annotations

import json
import math
import sys
import warnings
from datetime import date, datetime, time
from decimal import Decimal

import ibis
import ibis.expr.types as ir
import pyarrow as pa
import pyarrow.compute as pc

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from cases import FAMS, all_cases  # noqa: E402

warnings.filterwarnings("ignore")

DTYPE = {"bool": "boolean", "int": "int64", "float": "float64", "Decimal": "decimal(12, 2)",
         "str": "string", "datetime": "timestamp", "date": "date", "time": "time"}
# 5 rows, groups a,a,b,b,c: group b is all-NULL in the nullable columns, group c is a single row.
G = ["a", "a", "b", "b", "c"]
VALS = {
    "bool": [True, False, True, False, True],
    "int": [1, 2, 3, 4, 5],
    "float": [1.5, 2.5, -0.5, 4.0, 3.25],
    "Decimal": [Decimal("1.50"), Decimal("2.25"), Decimal("-0.50"), Decimal("4.00"), Decimal("3.25")],
    "str": ["apple", "banana", "a", "", "cherry"],
    "datetime": [datetime(2024, 1, 2, 3, 4, 5), datetime(2024, 2, 3), datetime(2023, 5, 6, 7), datetime(2024, 6, 1), datetime(2022, 1, 1)],
    "date": [date(2024, 1, 2), date(2024, 2, 3), date(2023, 5, 6), date(2024, 6, 1), date(2022, 1, 1)],
    "time": [time(1, 2, 3), time(4, 5), time(23, 0), time(12, 0), time(0, 0, 1)],
}
OTHER = {  # second operand column: different values, no zeros (division-by-zero is not what we test)
    "bool": [False, False, True, True, True],
    "int": [2, 3, -1, 7, 1],
    "float": [2.0, 0.5, -1.5, 3.0, 1.0],
    "Decimal": [Decimal("2.00"), Decimal("0.50"), Decimal("-1.50"), Decimal("3.00"), Decimal("1.00")],
    "str": ["a", "b", "c", "d", "e"],
    "datetime": [datetime(2024, 1, 1), datetime(2024, 2, 2), datetime(2024, 3, 3), datetime(2024, 4, 4), datetime(2024, 5, 5)],
    "date": [date(2024, 1, 1), date(2024, 2, 2), date(2024, 3, 3), date(2024, 4, 4), date(2024, 5, 5)],
    "time": [time(1), time(2), time(3), time(4), time(5)],
}


def family(d) -> str:
    for test, name in [("is_boolean", "bool"), ("is_integer", "int"), ("is_floating", "float"),
                       ("is_decimal", "Decimal"), ("is_string", "str"), ("is_timestamp", "datetime"),
                       ("is_date", "date"), ("is_time", "time"), ("is_interval", "timedelta")]:
        if getattr(d, test)():
            return name
    return str(d)


def build_table():
    data, schema = {"g": G}, {"g": "!string"}
    for f in FAMS:
        nulls = [v if g != "b" else None for v, g in zip(VALS[f], G)]
        onulls = [v if i != 1 else None for i, v in enumerate(OTHER[f])]
        data |= {f"c_{f}": VALS[f], f"n_{f}": nulls, f"d_{f}": OTHER[f], f"dn_{f}": onulls}
        schema |= {f"c_{f}": "!" + DTYPE[f], f"n_{f}": DTYPE[f], f"d_{f}": "!" + DTYPE[f], f"dn_{f}": DTYPE[f]}
    sch = ibis.schema(schema)
    tbl = pa.table({k: pa.array(v, type=sch[k].to_pyarrow()) for k, v in data.items()})
    try:
        return ibis.memtable(tbl, schema=sch)
    except Exception:  # older ibis: no schema= for arrow input
        return ibis.memtable(tbl).cast(sch)


def kind(e) -> str:
    if isinstance(e, ir.Table):
        return "Table"
    if isinstance(e, ir.Column):
        return "Column"
    if isinstance(e, ir.Scalar):
        return "Scalar"
    if isinstance(e, ir.Value):
        return "Value"
    return type(e).__name__


def nulls_nans(arr: pa.ChunkedArray) -> tuple[int, int]:
    nn = arr.null_count
    nan = 0
    if pa.types.is_floating(arr.type):
        nan = int(pc.sum(pc.is_nan(arr.fill_null(0.0))).as_py() or 0)
    return nn, nan


def execute(con, t, e, k):
    if k == "Column":
        arr = con.to_pyarrow(t.select(r=e))["r"]
        return nulls_nans(arr), None
    if k == "Scalar":
        rel = e.op().relations if hasattr(e.op(), "relations") else ()
        if not rel:
            v = con.to_pyarrow(e)
            arr = pa.chunked_array([pa.array([v.as_py()], type=v.type)])
            return nulls_nans(arr), None
        grouped = con.to_pyarrow(t.group_by("g").aggregate(r=e))["r"]
        empty = con.to_pyarrow(t.filter(ibis.literal(False)).aggregate(r=e))["r"]
        return nulls_nans(grouped), empty.null_count
    if k == "Table":
        con.to_pyarrow(e)
    return None, None


def main(out: str) -> None:
    t = build_table()
    con = ibis.duckdb.connect()
    res = {}
    for c in all_cases():
        x = getattr(t, f"{'n' if c.nullable else 'c'}_{c.fam}")
        if c.container == "Scalar":
            x = x.max()
        ns = {"x": x, "y": getattr(t, f"d_{c.fam}"), "yn": getattr(t, f"dn_{c.fam}"), "ibis": ibis,
              "Decimal": Decimal, "datetime": datetime, "date": date, "time": time}
        r: dict[str, object] = {"expr": c.expr}
        try:
            e = eval(c.expr, ns)
        except Exception as ex:  # noqa: BLE001
            r["error"] = f"{type(ex).__name__}: {str(ex).splitlines()[0][:160] if str(ex) else ''}"
            res[c.id] = r
            continue
        k = kind(e)
        r["kind"] = k
        if isinstance(e, ir.Value):
            r["dtype"] = str(e.type())
            r["fam"] = family(e.type())
            r["dtype_nullable"] = bool(e.type().nullable)
        elif not isinstance(e, ir.Table):
            r["pyvalue"] = repr(e)[:80]
        try:
            (nn_nan, empty_null) = execute(con, t, e, k)
            if nn_nan is not None:
                r["nulls"], r["nans"] = nn_nan
            if empty_null is not None:
                r["empty_null"] = empty_null
        except Exception as ex:  # noqa: BLE001
            r["exec_error"] = f"{type(ex).__name__}: {str(ex).splitlines()[0][:160] if str(ex) else ''}"
        res[c.id] = r
    json.dump({"ibis": ibis.__version__, "cases": res}, open(out, "w"), indent=0)
    errs = sum("error" in v for v in res.values())
    print(f"ibis {ibis.__version__}: {len(res)} cases, {errs} construction errors -> {out}")


if __name__ == "__main__":
    main(sys.argv[1])
