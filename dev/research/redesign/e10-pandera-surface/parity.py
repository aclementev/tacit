"""Q4: semantic parity of hybrid.validate vs pandera DataFrameSchema.validate(lazy=True).

usage: uv run --frozen python parity.py [duckdb|polars]

Compared per case: overall verdict; the set of failing (column, check_index, reason); and, for
row-level checks, the number of failing rows (pandera: len(failure_cases) of that SchemaError).
"""
from __future__ import annotations

import datetime as dtm
import json
import sys
import warnings
from decimal import Decimal

import ibis
import pyarrow as pa_

import pandera.errors as pe
import pandera.extensions as ext
import pandera.ibis as pa
from pandera.api.ibis.types import IbisData

import hybrid

warnings.simplefilter("ignore")
BACKEND = sys.argv[1] if len(sys.argv) > 1 else "duckdb"
con = ibis.duckdb.connect()   # data is built in duckdb SQL, then moved to the target backend
tgt = con if BACKEND == "duckdb" else ibis.polars.connect()
C = pa.Check
D = ibis.dtype
_n = [0]

# dtype -> (ibis dtype, SQL literals v0<v1<v2<v3, python values v0..v3, extra SQL rows)
TD = dtm.timedelta
DTYPES = {
    "int64": ("int64", ["1", "2", "3", "4"], [1, 2, 3, 4], []),
    "float64": ("float64", ["1.5", "2.5", "3.5", "4.5"], [1.5, 2.5, 3.5, 4.5], ["'NaN'::DOUBLE"]),
    "decimal": ("decimal(10, 2)", ["1.10", "2.20", "3.30", "4.40"],
                [Decimal("1.10"), Decimal("2.20"), Decimal("3.30"), Decimal("4.40")], []),
    "string": ("string", ["'a1'", "'b2'", "'c3'", "'d4'"], ["a1", "b2", "c3", "d4"], []),
    "date": ("date", ["DATE '2020-01-01'", "DATE '2020-06-01'", "DATE '2021-01-01'", "DATE '2022-01-01'"],
             [dtm.date(2020, 1, 1), dtm.date(2020, 6, 1), dtm.date(2021, 1, 1), dtm.date(2022, 1, 1)], []),
    "timestamp": ("timestamp", ["TIMESTAMP '2020-01-01 00:00'", "TIMESTAMP '2020-01-01 12:00'",
                                "TIMESTAMP '2020-01-02'", "TIMESTAMP '2021-01-01'"],
                  [dtm.datetime(2020, 1, 1), dtm.datetime(2020, 1, 1, 12), dtm.datetime(2020, 1, 2), dtm.datetime(2021, 1, 1)], []),
    "timestamptz": ("timestamp('UTC')", ["TIMESTAMPTZ '2020-01-01 00:00:00+00'", "TIMESTAMPTZ '2020-01-01 12:00:00+00'",
                                         "TIMESTAMPTZ '2020-01-02 00:00:00+00'", "TIMESTAMPTZ '2021-01-01 00:00:00+00'"],
                    [dtm.datetime(2020, 1, 1, tzinfo=dtm.UTC), dtm.datetime(2020, 1, 1, 12, tzinfo=dtm.UTC),
                     dtm.datetime(2020, 1, 2, tzinfo=dtm.UTC), dtm.datetime(2021, 1, 1, tzinfo=dtm.UTC)], []),
    "time": ("time", ["TIME '01:00'", "TIME '02:30'", "TIME '12:00'", "TIME '23:59'"],
             [dtm.time(1), dtm.time(2, 30), dtm.time(12), dtm.time(23, 59)], []),
    "interval": ("interval('us')", ["INTERVAL '1 hour'", "INTERVAL '1 day 2 hours'", "INTERVAL '3 days'", "INTERVAL '5 days'"],
                 [TD(hours=1), TD(days=1, hours=2), TD(days=3), TD(days=5)], []),
    "boolean": ("boolean", ["false", "true"], [False, True], []),
}


def make_table(dtype_key: str, with_null: bool):
    ty, lits, _, extra = DTYPES[dtype_key]
    rows = lits + extra + (["NULL"] if with_null else [])
    sql_ty = {"string": "VARCHAR", "decimal(10, 2)": "DECIMAL(10,2)", "timestamp('UTC')": "TIMESTAMPTZ",
              "interval('us')": "INTERVAL", "float64": "DOUBLE", "int64": "BIGINT"}.get(ty, ty.upper())
    _n[0] += 1
    sql = " UNION ALL ".join(f"SELECT {i} AS rid, CAST({r} AS {sql_ty}) AS x" for i, r in enumerate(rows))
    t = con.sql(f"SELECT x FROM ({sql}) ORDER BY rid")
    name = f"d{_n[0]}"
    if tgt is con:
        return con.create_table(name, t)
    return tgt.create_table(name, t.to_pyarrow())


def builtin_checks(dk: str):
    _, _, v, _ = DTYPES[dk]
    if dk == "boolean":
        return [C.eq(True), C.ne(True), C.isin([True]), C.notin([False]), C.unique_values_eq([False, True])]
    cs = [C.eq(v[1]), C.ne(v[1]), C.gt(v[1]), C.ge(v[1]), C.lt(v[2]), C.le(v[2]), C.ge(v[0]),
          C.in_range(v[1], v[2]), C.in_range(v[1], v[2], include_min=False, include_max=False),
          C.in_range(v[1], v[2], include_min=True, include_max=False), C.between(v[0], v[3]),
          C.isin([v[0], v[1]]), C.notin([v[3]]), C.unique_values_eq(v), C.unique_values_eq(v[:1]),
          C.ge(v[1], ignore_na=False)]
    if dk == "decimal":
        cs += [C.ge(2.0), C.le(3)]                               # float / int params vs decimal column
    if dk == "interval":
        cs += [C.ge(TD(days=1, seconds=1)), C.lt(TD(days=4, hours=1))]   # mixed-unit timedelta path
    if dk == "timestamp":
        cs += [C.ge(dtm.date(2020, 1, 2))]                        # date param vs timestamp column
    if dk == "string":
        cs += [C.str_matches(r"[ab]\d"), C.str_matches("b"), C.str_contains(r"\d"), C.str_contains("2"),
               C.str_startswith("a"), C.str_endswith("4"), C.str_length(2, 2), C.str_length(exact_value=2),
               C.str_length(min_value=3), C.str_length(max_value=1), C.str_matches(__import__("re").compile("^c"))]
    return cs


if not hasattr(C, "e10_divisible"):
    @ext.register_check_method(statistics=["by"])
    def e10_divisible(data: IbisData, *, by: int):
        return data.table[data.key] % by == 0

    @ext.register_check_method(statistics=["lo"])
    def e10_tbl_ge(data: IbisData, *, lo: int):        # registered check returning a boolean table
        return data.table.select(**{data.key: data.table[data.key] >= lo})


def pos(x: int) -> bool:
    return x > 1


CUSTOM = [  # (label, schema builder, table builder)
    ("registered vectorized", lambda: {"x": pa.Column(D("int64"), nullable=True, checks=[C.e10_divisible(by=2)])}, "int64"),
    ("registered table-output", lambda: {"x": pa.Column(D("int64"), nullable=True, checks=[C.e10_tbl_ge(lo=2)])}, "int64"),
    ("lambda col expr", lambda: {"x": pa.Column(D("int64"), nullable=True, checks=[C(lambda d: d.table[d.key] > 2)])}, "int64"),
    ("lambda dict output", lambda: {"x": pa.Column(D("int64"), nullable=True, checks=[C(lambda d: {d.key: d.table[d.key] > 2})])}, "int64"),
    ("lambda select->mutate", lambda: {"x": pa.Column(D("int64"), nullable=True, checks=[
        C(lambda d: d.table.select(d.key).mutate(**{d.key: d.table[d.key] > 2}))])}, "int64"),
    ("scalar agg pass", lambda: {"x": pa.Column(D("int64"), nullable=True, checks=[C(lambda d: d.table[d.key].sum() > 0)])}, "int64"),
    ("scalar agg fail", lambda: {"x": pa.Column(D("int64"), nullable=True, checks=[C(lambda d: d.table[d.key].mean() > 10)])}, "int64"),
    ("python bool False", lambda: {"x": pa.Column(D("int64"), nullable=True, checks=[C(lambda d: False)])}, "int64"),
    ("element_wise annotated", lambda: {"x": pa.Column(D("int64"), nullable=True, checks=[C(pos, element_wise=True)])}, "int64"),
    ("ignore_na=False custom", lambda: {"x": pa.Column(D("int64"), nullable=True, checks=[
        C(lambda d: d.table[d.key].fill_null(0) > 0, ignore_na=False)])}, "int64"),
    ("raise_warning", lambda: {"x": pa.Column(D("int64"), nullable=True, checks=[C.ge(3, raise_warning=True)])}, "int64"),
    ("n_failure_cases=1", lambda: {"x": pa.Column(D("int64"), nullable=True, checks=[C.ge(3, n_failure_cases=1)])}, "int64"),
    ("groupby (ignored upstream)", lambda: {"x": pa.Column(D("int64"), nullable=True, checks=[C(lambda d: d.table[d.key] > 2, groupby="x")])}, "int64"),
    ("not nullable int", lambda: {"x": pa.Column(D("int64"))}, "int64"),
    ("not nullable float NaN", lambda: {"x": pa.Column(D("float64"))}, "float64"),
    ("regex column", lambda: {"^x$": pa.Column(D("int64"), regex=True, nullable=True, checks=[C.ge(2)])}, "int64"),
    ("empty table, ge(0)", lambda: {"x": pa.Column(D("int64"), checks=[C.ge(0)])}, "EMPTY"),
    ("schema unique (NULL single)", lambda: ({"x": pa.Column(D("int64"), nullable=True)}, {"unique": ["x"]}), "int64"),
]

DF_CASES = [  # two-column tables
    ("df-level col expr a<b", [C(lambda d: d.table.a < d.table.b)]),
    ("df-level scalar", [C(lambda d: d.table.a.sum() < d.table.b.sum())]),
    ("df-level bool table", [C(lambda d: d.table.select(ok=d.table.a < d.table.b))]),
    ("df-level element_wise", [C(pos, element_wise=True)]),
    ("df-level ignore_na table", [C(lambda d: d.table.select(p=d.table.a < 3, q=d.table.b > 0))]),
    ("schema unique [a,b] w/ NULL dup", "unique"),
    ("schema unique report_duplicates=exclude_first", "unique_ef"),
]


def pandera_result(schema, t):
    try:
        schema.validate(t, lazy=True)
        return {}
    except pe.SchemaErrors as e:
        out = {}
        for err in e.schema_errors:
            col = getattr(err.schema, "name", None) if isinstance(err.schema, pa.Column) else None
            col = col.strip("^$") if col else col   # regex Column names are restored to the pattern
            reason = err.reason_code.name
            idx = err.check_index if reason == "DATAFRAME_CHECK" else None
            fc = err.failure_cases
            import pandas as pd
            if reason == "DUPLICATES":
                n = None
            elif isinstance(fc, pd.DataFrame):
                n = len(fc)
            elif isinstance(fc, ibis.Table):
                n = int(fc.count().execute())
            else:
                n = None
            out[(col, idx, reason)] = n
        return out
    except Exception as e:  # noqa: BLE001
        return {"EXC": f"{type(e).__name__}: {str(e)[:80]}"}


def _is_row_check(err) -> bool:
    import pandas as pd
    return isinstance(err.failure_cases, pd.DataFrame)


def hybrid_result(schema, t):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            r = hybrid.validate(schema, t, column_unique=False)
    except Exception as e:  # noqa: BLE001
        return {"EXC": f"{type(e).__name__}: {str(e)[:80]}"}, None
    out = {}
    for f in r.failures:
        n = None if f.reason == "DUPLICATES" else f.count
        out[(f.column, f.check_index if f.reason == "DATAFRAME_CHECK" else None, f.reason)] = n
    return out, r


results = []


def _empty():
    _n[0] += 1
    e = con.sql("SELECT 1::BIGINT AS x WHERE false")
    return con.create_table(f"e{_n[0]}", e) if tgt is con else tgt.create_table(f"e{_n[0]}", e.to_pyarrow())


sys.path.insert(0, "../e4-runtime")
from common import log_queries, log_reset  # noqa: E402
if tgt is con:
    con.raw_sql("CALL enable_logging('QueryLog')")


def _nq():
    return len(log_queries(con)) if tgt is con else None


def compare(label, schema, t):
    log_reset(con) if tgt is con else None
    p = pandera_result(schema, t)
    pq = _nq()
    log_reset(con) if tgt is con else None
    h, rep = hybrid_result(schema, t)
    hq = _nq()
    if p == h:
        verdict = "MATCH"
    elif set(p) == set(h):
        verdict = "COUNT-DIFF"
    else:
        verdict = "MISMATCH"
    results.append(dict(case=label, verdict=verdict, pandera=str(p), hybrid=str(h),
                        queries=hq, pandera_queries=pq, fallbacks=getattr(rep, "n_fallback", None)))


def main():
    for dk in DTYPES:
        if BACKEND != "duckdb" and dk == "interval":
            continue  # duckdb INTERVAL -> arrow month_day_nano can't be moved to polars via ibis
        for with_null in (True, False):
            t = make_table(dk, with_null)
            for ck in builtin_checks(dk):
                for nullable in (True, False):
                    try:
                        schema = pa.DataFrameSchema({"x": pa.Column(t.schema()["x"], checks=[ck], nullable=nullable)})
                    except Exception as e:  # noqa: BLE001
                        results.append(dict(case=f"{dk} {ck.error}", verdict="SCHEMA-EXC", pandera=str(e)[:80], hybrid=""))
                        continue
                    compare(f"{dk:<11} null={int(with_null)} nullable={int(nullable)} {ck.error}"
                            f"{' ignore_na=False' if not ck.ignore_na else ''}", schema, t)

    for label, build, dk in CUSTOM:
        spec = build()
        kw = {}
        if isinstance(spec, tuple):
            spec, kw = spec
        t = make_table(dk, True) if dk != "EMPTY" else _empty()
        compare(f"custom: {label}", pa.DataFrameSchema(spec, **kw), t)

    _n[0] += 1
    ab = con.sql("SELECT * FROM (VALUES (1, 2), (3, 2), (NULL, 5), (2, NULL), (NULL, 5)) v(a, b)")
    ab = con.create_table(f"ab{_n[0]}", ab) if tgt is con else tgt.create_table(f"ab{_n[0]}", ab.to_pyarrow())
    cols = {"a": pa.Column(D("int32"), nullable=True), "b": pa.Column(D("int32"), nullable=True)}
    for label, checks in DF_CASES:
        if checks == "unique":
            schema = pa.DataFrameSchema(cols, unique=["a", "b"])
        elif checks == "unique_ef":
            schema = pa.DataFrameSchema(cols, unique=["a", "b"], report_duplicates="exclude_first")
        else:
            schema = pa.DataFrameSchema(cols, checks=checks)
        compare(f"df: {label}", schema, ab)

    from collections import Counter
    print(f"### parity on {BACKEND}: {len(results)} cases -> {dict(Counter(r['verdict'] for r in results))}")
    if tgt is con:
        print(f"logged data queries: pandera total {sum(r['pandera_queries'] or 0 for r in results)}, "
              f"hybrid total {sum(r['queries'] or 0 for r in results)}; max per case pandera "
              f"{max(r['pandera_queries'] or 0 for r in results)}, hybrid {max(r['queries'] or 0 for r in results)}")
    print(f"queries per hybrid run: {dict(Counter(r.get('queries') for r in results))}; "
          f"fallback checks: {sum(r.get('fallbacks') or 0 for r in results)}")
    for r in results:
        if r["verdict"] != "MATCH":
            print(f"{r['verdict']:<10} {r['case']}\n    pandera={r['pandera']}\n    hybrid ={r['hybrid']}")
    json.dump(results, open(f"parity_{BACKEND}.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
