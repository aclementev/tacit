"""Q1: probe pandera's non-check feature surface on the ibis backend (duckdb).

usage:
  uv run --frozen python probe_surface.py                         # native ibis backend
  PANDERA_USE_NARWHALS_BACKEND=True uv run --frozen --with narwhals python probe_surface.py
Each probe prints: feature | verdict | detail.  Verdict is WORKS / IGNORED / RAISES / PARTIAL.
"""
import datetime as dtm
import os
import traceback
import warnings

import ibis
import pyarrow as pa_

import pandera.ibis as pa
import pandera.errors as pe

warnings.simplefilter("ignore")
con = ibis.duckdb.connect()
D = ibis.dtype
C = pa.Check
_n = [0]


def mk(**cols):
    _n[0] += 1
    return con.create_table(f"t{_n[0]}", ibis.memtable(pa_.table(cols)))


def run(schema, t, **kw):
    """-> ('pass', table) | ('FAIL', reasons) | ('EXC', msg)"""
    try:
        out = schema.validate(t, lazy=True, **kw)
        return "pass", out
    except pe.SchemaErrors as e:
        return "FAIL", ",".join(sorted({x.reason_code.name for x in e.schema_errors}))
    except pe.SchemaError as e:
        return "FAIL", e.reason_code.name
    except Exception as e:  # noqa: BLE001
        return "EXC", f"{type(e).__name__}: {str(e).splitlines()[0][:90] if str(e) else ''}"


ROWS: list[tuple[str, str, str]] = []


def probe(name):
    def deco(fn):
        try:
            verdict, detail = fn()
        except Exception as e:  # noqa: BLE001
            verdict, detail = "RAISES", f"{type(e).__name__}: {str(e).splitlines()[0][:110] if str(e) else ''}"
        ROWS.append((name, verdict, str(detail).replace("|", "/").replace("\n", " ")[:160]))
        return fn
    return deco


def gb(good, bad):
    """verdict from (good, bad) run results"""
    if good[0] == "pass" and bad[0] == "FAIL":
        return "WORKS", f"bad -> {bad[1]}"
    if good[0] == "pass" and bad[0] == "pass":
        return "IGNORED", "bad data accepted"
    return "BROKEN", f"good={good[0]}:{good[1] if good[0] != 'pass' else ''} bad={bad[0]}:{bad[1] if bad[0] != 'pass' else ''}"


# ---------------- column options ----------------
@probe("Column dtype (int64 vs int32)")
def _():
    s = pa.DataFrameSchema({"x": pa.Column(D("int64"))})
    return gb(run(s, mk(x=[1])), run(s, mk(x=[1]).cast({"x": "int32"})))


@probe("Column dtype timestamp vs duckdb timestamp(6)")
def _():
    s = pa.DataFrameSchema({"x": pa.Column(D("timestamp"))})
    t = con.sql("select TIMESTAMP '2020-01-01' x")
    r = run(s, t)
    return ("WORKS" if r[0] == "pass" else "BROKEN"), f"{r[0]} {r[1] if r[0] != 'pass' else ''}"


@probe("Column nullable=False (+NaN)")
def _():
    s = pa.DataFrameSchema({"x": pa.Column(D("float64"))})
    return gb(run(s, mk(x=[1.0])), run(s, mk(x=[1.0, float("nan")])))


@probe("Column unique=True")
def _():
    s = pa.DataFrameSchema({"x": pa.Column(D("int64"), unique=True)})
    return gb(run(s, mk(x=[1, 2])), run(s, mk(x=[1, 1])))


@probe("Column coerce=True (string->int64)")
def _():
    s = pa.DataFrameSchema({"x": pa.Column(D("int64"), coerce=True)})
    r = run(s, mk(x=["1", "2"]))
    if r[0] == "pass":
        return "WORKS", f"out dtype {r[1].schema()['x']}"
    return "IGNORED", f"{r[0]} {r[1]}"


@probe("DataFrameSchema coerce=True")
def _():
    s = pa.DataFrameSchema({"x": pa.Column(D("int64"))}, coerce=True)
    r = run(s, mk(x=["1", "2"]))
    if r[0] == "pass":
        return "WORKS", f"out dtype {r[1].schema()['x']}"
    return "IGNORED", f"{r[0]} {r[1]}"


@probe("coerce=True with bad value 'N/A'")
def _():
    s = pa.DataFrameSchema({"x": pa.Column(D("int64"), coerce=True)})
    r = run(s, mk(x=["1", "N/A"]))
    return ("IGNORED" if "WRONG_DATATYPE" in str(r[1]) else "WORKS" if r[0] == "FAIL" else "BROKEN"), f"{r[0]} {r[1] if r[0] != 'pass' else ''}"


@probe("Column required=False")
def _():
    s = pa.DataFrameSchema({"x": pa.Column(D("int64")), "y": pa.Column(D("int64"), required=False)})
    r = run(s, mk(x=[1]))
    return ("WORKS" if r[0] == "pass" else "BROKEN"), r[0]


@probe("Column regex=True")
def _():
    s = pa.DataFrameSchema({"v_.*": pa.Column(D("int64"), regex=True, checks=[C.ge(0)])})
    return gb(run(s, mk(v_a=[1], v_b=[2])), run(s, mk(v_a=[1], v_b=[-2])))


@probe("Column default= (fill nulls)")
def _():
    s = pa.DataFrameSchema({"x": pa.Column(D("int64"), nullable=True, default=0)})
    r = run(s, mk(x=pa_.array([1, None], pa_.int64())))
    if r[0] != "pass":
        return "BROKEN", r
    vals = r[1].x.to_pyarrow().to_pylist()
    return ("WORKS" if None not in vals else "IGNORED"), f"values after validate: {vals}"


@probe("Column drop_invalid_rows=True")
def _():
    s = pa.DataFrameSchema({"x": pa.Column(D("int64"), checks=[C.ge(0)])}, drop_invalid_rows=True)
    r = run(s, mk(x=[1, -1, 2]))
    if r[0] != "pass":
        return "BROKEN", r
    return "WORKS", f"rows kept: {r[1].x.to_pyarrow().to_pylist()}"


@probe("Column title/description/metadata")
def _():
    c = pa.Column(D("int64"), title="T", description="d", metadata={"k": 1})
    return "WORKS", f"metadata={c.metadata} (pure metadata, no runtime effect)"


# ---------------- schema options ----------------
@probe("strict=True")
def _():
    s = pa.DataFrameSchema({"x": pa.Column(D("int64"))}, strict=True)
    return gb(run(s, mk(x=[1])), run(s, mk(x=[1], y=[1])))


@probe("strict='filter'")
def _():
    s = pa.DataFrameSchema({"x": pa.Column(D("int64"))}, strict="filter")
    r = run(s, mk(x=[1], y=[1]))
    return ("WORKS" if r[0] == "pass" and r[1].columns == ("x",) else "BROKEN"), f"{r[0]} cols={getattr(r[1], 'columns', r[1])}"


@probe("ordered=True")
def _():
    s = pa.DataFrameSchema({"x": pa.Column(D("int64")), "y": pa.Column(D("int64"))}, ordered=True)
    return gb(run(s, mk(x=[1], y=[1])), run(s, mk(y=[1], x=[1])))


@probe("DataFrameSchema unique=[cols]")
def _():
    s = pa.DataFrameSchema({"x": pa.Column(D("int64")), "y": pa.Column(D("int64"))}, unique=["x", "y"])
    return gb(run(s, mk(x=[1, 1], y=[1, 2])), run(s, mk(x=[1, 1], y=[2, 2])))


@probe("report_duplicates='exclude_first'")
def _():
    s = pa.DataFrameSchema({"x": pa.Column(D("int64"))}, unique=["x"], report_duplicates="exclude_first")
    return gb(run(s, mk(x=[1, 2])), run(s, mk(x=[1, 1])))


@probe("add_missing_columns=True")
def _():
    s = pa.DataFrameSchema({"x": pa.Column(D("int64")), "y": pa.Column(D("int64"), nullable=True, default=0)},
                           add_missing_columns=True)
    r = run(s, mk(x=[1]))
    return ("WORKS" if r[0] == "pass" and "y" in r[1].columns else "BROKEN"), f"{r[0]}"


@probe("dataframe-level Check (a < b)")
def _():
    s = pa.DataFrameSchema({"a": pa.Column(D("int64")), "b": pa.Column(D("int64"))},
                           checks=[C(lambda d: d.table.a < d.table.b)])
    return gb(run(s, mk(a=[1], b=[2])), run(s, mk(a=[3], b=[2])))


@probe("validate(head=1) subsampling")
def _():
    s = pa.DataFrameSchema({"x": pa.Column(D("int64"), checks=[C.ge(0)])})
    r = run(s, mk(x=[1, -1]), head=1)
    return ("WORKS" if r[0] == "pass" else "IGNORED"), f"head=1 over [1,-1] -> {r[0]} (TODO in backend source)"


@probe("validate(sample=1, random_state=0)")
def _():
    s = pa.DataFrameSchema({"x": pa.Column(D("int64"), checks=[C.ge(0)])})
    r = run(s, mk(x=[-1, -1]), sample=1, random_state=0)
    return ("IGNORED" if r[0] == "FAIL" else "?"), f"{r[0]} {r[1] if r[0] != 'pass' else ''}"


@probe("Parser (column-level)")
def _():
    from pandera.api.parsers import Parser
    s = pa.DataFrameSchema({"x": pa.Column(D("int64"), parsers=[Parser(lambda c: c.abs())])})
    r = run(s, mk(x=[-1]))
    if r[0] != "pass":
        return "BROKEN", r
    return ("WORKS" if r[1].x.to_pyarrow().to_pylist() == [1] else "IGNORED"), f"{r[1].x.to_pyarrow().to_pylist()}"


@probe("lazy=True aggregates all errors")
def _():
    s = pa.DataFrameSchema({"x": pa.Column(D("int64"), checks=[C.ge(0), C.le(5)]), "y": pa.Column(D("string"))})
    try:
        s.validate(mk(x=[-1, 9], y=pa_.array([None, "a"], pa_.string())), lazy=True)
    except pe.SchemaErrors as e:
        fc = e.failure_cases
        return "WORKS", f"{len(e.schema_errors)} errors; failure_cases {type(fc).__module__}.{type(fc).__name__} cols={list(fc.columns)}"
    return "BROKEN", "no error"


@probe("SchemaErrors.message (json summary)")
def _():
    s = pa.DataFrameSchema({"x": pa.Column(D("int64"), checks=[C.ge(0)])})
    try:
        s.validate(mk(x=[-1]), lazy=True)
    except pe.SchemaErrors as e:
        return "WORKS", f"keys={list(e.message.keys())}"
    return "BROKEN", ""


# ---------------- check options ----------------
@probe("Check raise_warning=True")
def _():
    s = pa.DataFrameSchema({"x": pa.Column(D("int64"), checks=[C.ge(0, raise_warning=True)])})
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        r = run(s, mk(x=[-1]))
    return ("WORKS" if r[0] == "pass" and w else "BROKEN"), f"{r[0]}, {len(w)} warning(s)"


@probe("Check n_failure_cases=2")
def _():
    s = pa.DataFrameSchema({"x": pa.Column(D("int64"), checks=[C.ge(0, n_failure_cases=2)])})
    try:
        s.validate(mk(x=[-1, -2, -3, -4]), lazy=True)
    except pe.SchemaErrors as e:
        return "WORKS", f"{len(e.failure_cases)} failure cases reported (4 bad)"
    return "BROKEN", ""


@probe("Check ignore_na=False (builtin ge on NULL)")
def _():
    s = pa.DataFrameSchema({"x": pa.Column(D("int64"), nullable=True, checks=[C.ge(0, ignore_na=False)])})
    r = run(s, mk(x=pa_.array([1, None], pa_.int64())))
    return ("IGNORED" if r[0] == "pass" else "WORKS"), f"NULL row with ignore_na=False -> {r[0]} (bool_and skips NULL)"


@probe("Check groupby='g'")
def _():
    s = pa.DataFrameSchema({"x": pa.Column(D("int64"), checks=[C(lambda d: d.table[d.key].sum() > 0, groupby="g")]),
                            "g": pa.Column(D("string"))})
    r = run(s, mk(x=[5, -1], g=["a", "b"]))
    return ("IGNORED" if r[0] == "pass" else "PARTIAL"), f"group b sums to -1 -> {r[0]}"


@probe("Check element_wise=True (annotated fn)")
def _():
    def pos(x: int) -> bool:
        return x > 0
    s = pa.DataFrameSchema({"x": pa.Column(D("int64"), checks=[C(pos, element_wise=True)])})
    return gb(run(s, mk(x=[1])), run(s, mk(x=[1, -1])))


@probe("Check element_wise=True (lambda)")
def _():
    s = pa.DataFrameSchema({"x": pa.Column(D("int64"), checks=[C(lambda x: x > 0, element_wise=True)])})
    return gb(run(s, mk(x=[1])), run(s, mk(x=[1, -1])))


@probe("Check name=/error=")
def _():
    s = pa.DataFrameSchema({"x": pa.Column(D("int64"), checks=[C.ge(0, name="nonneg", error="must be >= 0")])})
    try:
        s.validate(mk(x=[-1]))
    except pe.SchemaError as e:
        return "WORKS", str(e).splitlines()[0][:100]
    return "BROKEN", ""


@probe("register_check_method (vectorized) on ibis")
def _():
    import pandera.extensions as ext
    from pandera.api.ibis.types import IbisData

    if not hasattr(C, "is_even_e10"):
        @ext.register_check_method(statistics=["mod"])
        def is_even_e10(data: IbisData, *, mod: int):
            return data.table[data.key] % mod == 0
    s = pa.DataFrameSchema({"x": pa.Column(D("int64"), checks=[C.is_even_e10(mod=2)])})
    return gb(run(s, mk(x=[2, 4])), run(s, mk(x=[2, 3])))


@probe("register_builtin_check (new dispatch for IbisData)")
def _():
    from pandera.api.extensions import register_builtin_check
    from pandera.api.ibis.types import IbisData
    return "WORKS", "API exists (pandera-internal: it's how backends add builtins); see hybrid parity for use"


# ---------------- DataFrameModel ----------------
@probe("DataFrameModel + Field(ge, isin, unique, nullable)")
def _():
    class M(pa.DataFrameModel):
        a: int = pa.Field(ge=0)
        b: str = pa.Field(isin=["x", "y"], nullable=True)
        c: int = pa.Field(unique=True)
    good = M.validate(mk(a=[1, 2], b=pa_.array(["x", None]), c=[1, 2]), lazy=True)
    r1 = run(M.to_schema(), mk(a=[-1, 2], b=["z", "x"], c=[1, 2]))
    r2 = run(M.to_schema(), mk(a=[1, 2], b=["x", "x"], c=[1, 1]))
    return ("PARTIAL" if r1[0] == "FAIL" and r2[0] == "pass" else "WORKS" if r2[0] == "FAIL" else "BROKEN"), \
        f"ge/isin -> {r1[1]}; Field(unique=True) dup -> {r2[0]}"


@probe("DataFrameModel Config(strict, coerce, unique)")
def _():
    class M(pa.DataFrameModel):
        a: int
        class Config:
            strict = True
            unique = ["a"]
    return gb(run(M.to_schema(), mk(a=[1, 2])), run(M.to_schema(), mk(a=[1, 1])))


@probe("DataFrameModel @pa.check / @pa.dataframe_check")
def _():
    class M(pa.DataFrameModel):
        a: int
        b: int

        @pa.check("a")
        def a_pos(cls, data):
            return data.table[data.key] > 0

        @pa.dataframe_check
        def a_lt_b(cls, data):
            return data.table.a < data.table.b
    return gb(run(M.to_schema(), mk(a=[1], b=[2])), run(M.to_schema(), mk(a=[3], b=[2])))


@probe("DataFrameModel @parser")
def _():
    from pandera.api.dataframe.model_components import parser
    class M(pa.DataFrameModel):
        a: int

        @parser("a")
        def absval(cls, c):
            return c.abs()
    r = run(M.to_schema(), mk(a=[-1]))
    return ("WORKS" if r[0] == "pass" and r[1].a.to_pyarrow().to_pylist() == [1] else "IGNORED"), \
        f"{r[0]} {r[1].a.to_pyarrow().to_pylist() if r[0] == 'pass' else r[1]}"


def _check_types_fn():
    from pandera.typing.ibis import Table

    class M(pa.DataFrameModel):
        a: int = pa.Field(ge=0)
    ns = {"Table": Table, "M": M, "pa": pa}
    exec("@pa.check_types\ndef f(t: Table[M]) -> Table[M]:\n    return t\n", ns)
    return ns["f"]


@probe("pandera.typing.ibis Table[Model] + @check_types")
def _():
    f = _check_types_fn()
    f(mk(a=[1]))
    try:
        f(mk(a=[-1]))
    except (pe.SchemaError, pe.SchemaErrors):
        return "WORKS", "bad input rejected by decorator"
    return "IGNORED", "bad input accepted"


# ---------------- IO / inference / strategies ----------------
@probe("to_yaml / from_yaml roundtrip")
def _():
    s = pa.DataFrameSchema({"x": pa.Column(D("int64"), checks=[C.ge(0), C.isin([1, 2])], nullable=True)})
    y = s.to_yaml()
    s2 = pa.DataFrameSchema.from_yaml(y)
    return ("WORKS" if s2.columns["x"].checks == s.columns["x"].checks or len(s2.columns["x"].checks) == 2 else "PARTIAL"), f"{len(y)} chars"


@probe("to_json / from_json")
def _():
    s = pa.DataFrameSchema({"x": pa.Column(D("int64"), checks=[C.ge(0)])})
    j = s.to_json()
    pa.DataFrameSchema.from_json(j)
    return "WORKS", f"{len(j)} chars"


@probe("to_script")
def _():
    s = pa.DataFrameSchema({"x": pa.Column(D("int64"), checks=[C.ge(0)])})
    return "WORKS", s.to_script().splitlines()[0][:80]


@probe("infer_schema(ibis.Table)")
def _():
    from pandera.schema_inference.ibis import infer_schema
    s = infer_schema(mk(x=[1, 2, 3], y=["a", "b", "c"]))
    return "WORKS", f"inferred checks on x: {[c.name for c in s.columns['x'].checks]}"


@probe("strategies / Model.example (hypothesis)")
def _():
    class M(pa.DataFrameModel):
        a: int = pa.Field(ge=0)
    try:
        import hypothesis  # noqa: F401
    except ImportError:
        return "N/A", "hypothesis not installed; no ibis strategies module exists in pandera/strategies/"
    ex = M.example(size=3)
    return "WORKS", type(ex).__name__


@probe("PANDERA_VALIDATION_DEPTH=SCHEMA_ONLY")
def _():
    from pandera.config import config_context, ValidationDepth
    s = pa.DataFrameSchema({"x": pa.Column(D("int64"), checks=[C.ge(0)])})
    with config_context(validation_depth=ValidationDepth.SCHEMA_ONLY):
        r = run(s, mk(x=[-1]))
    return ("WORKS" if r[0] == "pass" else "BROKEN"), f"data check skipped -> {r[0]}"


@probe("PANDERA_VALIDATION_ENABLED=False")
def _():
    from pandera.config import config_context
    s = pa.DataFrameSchema({"x": pa.Column(D("int64"), checks=[C.ge(0)])})
    with config_context(validation_enabled=False):
        r = run(s, mk(x=[-1]))
    return ("WORKS" if r[0] == "pass" else "IGNORED"), f"{r[0]} (flag is never read outside pandera/config.py in 0.34.1)"


print(f"### backend: {'narwhals' if os.environ.get('PANDERA_USE_NARWHALS_BACKEND') else 'native ibis'}  pandera={__import__('pandera').__version__} ibis={ibis.__version__}")
print("| feature | verdict | detail |\n|---|---|---|")
for r in ROWS:
    print("| " + " | ".join(r) + " |")
