"""Q2/Q6: which pandera built-in/custom checks work on the ibis backend? usage: uv run python cov_matrix.py [duckdb|polars]"""
import sys, warnings, traceback
import ibis
import pandera.ibis as pa
import pandera.errors as pe
warnings.filterwarnings("ignore")

backend = sys.argv[1] if len(sys.argv) > 1 else "duckdb"
con = getattr(ibis, backend).connect()
C = pa.Check
D = ibis.dtype

_n = [0]
def mk(name, data):
    _n[0] += 1
    import pyarrow as pyarrow_
    def arr(v):
        first = next((x for x in v if x is not None), None)
        ty = {int: pyarrow_.int64(), float: pyarrow_.float64(), str: pyarrow_.string()}.get(type(first), pyarrow_.int64())
        return pyarrow_.array(v, type=ty)
    return con.create_table(f"{name}_{_n[0]}", ibis.memtable(pyarrow_.table({k: arr(v) for k, v in data.items()})))

def attempt(schema, tbl, **kw):
    try:
        schema.validate(tbl, lazy=True, **kw)
        return "pass", ""
    except pe.SchemaErrors as e:
        reasons = sorted({x.reason_code.name for x in e.schema_errors})
        msg = str(e.schema_errors[0]).splitlines()[0][:110]
        return "FAIL", ",".join(reasons) + " | " + msg
    except pe.SchemaError as e:
        return "FAIL", f"{e.reason_code.name} | {str(e).splitlines()[0][:110]}"
    except Exception as e:
        return f"EXC {type(e).__name__}", str(e).splitlines()[0][:110] if str(e) else ""

# (label, ibis/py column type, check, good values, bad values)  -- a trailing None is appended to every list (ignore_na)
I = int; F = float; S = str
cases = [
    ("ge(0)",            I, C.ge(0),            [0, 1, 2],     [0, -1]),
    ("le(2)",            I, C.le(2),            [0, 1, 2],     [0, 3]),
    ("gt(0)",            I, C.gt(0),            [1, 2],        [1, 0]),
    ("lt(3)",            I, C.lt(3),            [1, 2],        [1, 3]),
    ("eq(1)",            I, C.eq(1),            [1, 1],        [1, 2]),
    ("ne(1)",            I, C.ne(1),            [2, 3],        [2, 1]),
    ("in_range(1,3)",    I, C.in_range(1, 3),   [1, 2, 3],     [1, 4]),
    ("in_range excl",    I, C.in_range(1, 3, include_min=False, include_max=False), [2], [1]),
    ("isin",             S, C.isin(["a", "b"]), ["a", "b"],    ["a", "z"]),
    ("notin",            S, C.notin(["x"]),     ["a", "b"],    ["a", "x"]),
    ("str_matches",      S, C.str_matches(r"^a\d+$"), ["a1", "a22"], ["a1", "b2"]),
    ("str_contains",     S, C.str_contains("bc"), ["abc", "xbcx"], ["abc", "zzz"]),
    ("str_startswith",   S, C.str_startswith("ab"), ["abc", "abd"], ["abc", "xbc"]),
    ("str_endswith",     S, C.str_endswith("c"), ["abc", "xc"], ["abc", "ab"]),
    ("str_length(2,3)",  S, C.str_length(2, 3), ["ab", "abc"], ["ab", "abcd"]),
    ("str_length(exact)",S, C.str_length(exact_value=2), ["ab", "cd"], ["ab", "abc"]),
    ("unique_values_eq", I, C.unique_values_eq([1, 2]), [1, 2, 2], [1, 3]),
    ("custom col expr",  I, C(lambda d: d.table[d.key] > 0), [1, 2], [1, -1]),
    ("custom tbl-of-bool", I, C(lambda d: d.table.select(d.key).mutate(**{d.key: d.table[d.key] > 0})), [1, 2], [1, -1]),
    ("custom scalar agg", I, C(lambda d: d.table[d.key].sum() > 0), [1, 2], [-5, 1]),
    ("custom python bool", I, C(lambda d: True), [1], [1]),
    ("custom element_wise (py UDF)", I, C(lambda x: x > 0, element_wise=True), [1, 2], [1, -1]),
    ("custom ignore_na=False", I, C(lambda d: d.table[d.key].fill_null(-1) > 0, ignore_na=False), [1, 2], [1, 2]),  # None row must FAIL even in 'good'
    ("custom groupby=",  I, C(lambda d: d.table[d.key] > 0, groupby="g"), [1, 2], [1, -1]),
]

rows = []
for label, ty, chk, good, bad in cases:
    pty = {int: "int64", float: "float64", str: "string"}[ty]
    g = mk("g", {"x": good + [None]}); b = mk("b", {"x": bad + [None]})
    cols = {"x": pa.Column(D(pty), checks=[chk], nullable=True)}
    if "groupby" in label:
        g = mk("g", {"x": good + [None], "g": ["a"] * (len(good) + 1)}); b = mk("b", {"x": bad + [None], "g": ["a"] * (len(bad) + 1)})
        cols["g"] = pa.Column(D("string"))
    try:
        schema = pa.DataFrameSchema(cols)
    except Exception as e:
        rows.append((label, "-", "-", f"REJECTED AT SCHEMA DEFINITION: {type(e).__name__}", str(e)[:110])); continue
    gr, gm = attempt(schema, g); br, bm = attempt(schema, b)
    verdict = ("OK" if (gr == "pass" and br == "FAIL") else
               "SILENT PASS (bad data accepted)" if (gr == "pass" and br == "pass") else
               "FALSE FAIL on good data" if gr == "FAIL" and br == "FAIL" else f"{gr}/{br}")
    rows.append((label, gr, br, verdict, (gm if gr != "pass" else bm)))

# column-level / dataframe-level features
extra = []
dup = mk("d", {"x": [1, 1, 2]}); uniq = mk("u", {"x": [1, 2, 3]})
extra.append(("Column(unique=True)", attempt(pa.DataFrameSchema({"x": pa.Column(D("int64"), unique=True)}), uniq),
              attempt(pa.DataFrameSchema({"x": pa.Column(D("int64"), unique=True)}), dup)))
extra.append(("DataFrameSchema(unique=['x'])", attempt(pa.DataFrameSchema({"x": pa.Column(D("int64"))}, unique=["x"]), uniq),
              attempt(pa.DataFrameSchema({"x": pa.Column(D("int64"))}, unique=["x"]), dup)))
two_g = mk("tg", {"a": [1, 2], "b": [2, 3]}); two_b = mk("tb", {"a": [1, 5], "b": [2, 3]})
df_chk = pa.DataFrameSchema({"a": pa.Column(D("int64")), "b": pa.Column(D("int64"))}, checks=[C(lambda d: d.table.a < d.table.b)])
extra.append(("df-level check a<b (col expr)", attempt(df_chk, two_g), attempt(df_chk, two_b)))
df_chk2 = pa.DataFrameSchema({"a": pa.Column(D("int64")), "b": pa.Column(D("int64"))}, checks=[C(lambda d: d.table.a.sum() < d.table.b.sum())])
extra.append(("df-level check sum(a)<sum(b) (scalar)", attempt(df_chk2, two_g), attempt(df_chk2, two_b)))
df_chk3 = pa.DataFrameSchema({"a": pa.Column(D("int64")), "b": pa.Column(D("int64"))}, checks=[C(lambda d: d.table.select(ok=d.table.a < d.table.b))])
extra.append(("df-level check -> bool Table", attempt(df_chk3, two_g), attempt(df_chk3, two_b)))
nn = pa.DataFrameSchema({"x": pa.Column(D("int64"), nullable=False)})
extra.append(("nullable=False", attempt(nn, mk("n1", {"x": [1, 2]})), attempt(nn, mk("n2", {"x": [1, None]}))))
nnf = pa.DataFrameSchema({"x": pa.Column(D("float64"), nullable=False)})
extra.append(("nullable=False float NaN", attempt(nnf, mk("n3", {"x": [1.0, 2.0]})), attempt(nnf, mk("n4", {"x": [1.0, float('nan')]}))))
dts = pa.DataFrameSchema({"x": pa.Column(D("int64"))})
extra.append(("dtype mismatch (str vs int64)", attempt(dts, mk("t1", {"x": [1]})), attempt(dts, mk("t2", {"x": ["a"]}))))
extra.append(("dtype int32 vs int64", attempt(dts, mk("t1", {"x": [1]})), attempt(dts, mk("t3", {"x": [1]}).cast({"x": "int32"}))))
st = pa.DataFrameSchema({"x": pa.Column(D("int64"))}, strict=True)
extra.append(("strict: extra column", attempt(st, mk("s1", {"x": [1]})), attempt(st, mk("s2", {"x": [1], "y": [1]}))))
extra.append(("missing column", attempt(st, mk("s1", {"x": [1]})), attempt(st, mk("s3", {"y": [1]}))))
co = pa.DataFrameSchema({"x": pa.Column(D("int64"), coerce=True)})
extra.append(("Column(coerce=True) '1'->int64", attempt(co, mk("c1", {"x": [1]})), attempt(co, mk("c2", {"x": ["1", "2"]}))))
co2 = pa.DataFrameSchema({"x": pa.Column(D("int64"))}, coerce=True)
extra.append(("DataFrameSchema(coerce=True)", attempt(co2, mk("c1", {"x": [1]})), attempt(co2, mk("c2", {"x": ["1", "2"]}))))
rx = pa.DataFrameSchema({"v_.*": pa.Column(D("int64"), regex=True, checks=[C.ge(0)])})
extra.append(("regex columns + ge(0)", attempt(rx, mk("r1", {"v_a": [1], "v_b": [2]})), attempt(rx, mk("r2", {"v_a": [1], "v_b": [-2]}))))

print(f"### backend={backend}  ibis={ibis.__version__}")
print("| check | good data (+NULL row) | bad data | verdict | detail |"); print("|---|---|---|---|---|")
for r in rows: print("| " + " | ".join(str(x).replace("|", "/") for x in r) + " |")
print("\n| feature | good | bad | detail (bad run) |"); print("|---|---|---|---|")
for lab, (gr, gm), (br, bm) in extra:
    print(f"| {lab} | {gr} {gm[:60] if gr!='pass' else ''} | {br} | {bm[:150].replace('|','/')} |")
