"""Supplemental coverage probes + shape of failure cases."""
import warnings, ibis, pyarrow as pa_
import pandera.ibis as pa, pandera.errors as pe
warnings.filterwarnings("ignore")
con = ibis.duckdb.connect(); D = ibis.dtype; C = pa.Check
def mk(name, **cols): return con.create_table(name, ibis.memtable(pa_.table(cols)))
def tryv(schema, t, lazy=True):
    try: schema.validate(t, lazy=lazy); return "pass"
    except pe.SchemaErrors as e: return "FAIL(" + ",".join(sorted({x.reason_code.name for x in e.schema_errors})) + ")"
    except pe.SchemaError as e: return f"FAIL({e.reason_code.name})"
    except Exception as e: return f"EXC {type(e).__name__}: {str(e)[:100]}"

s = pa.DataFrameSchema({"x": pa.Column(D("int64"), checks=[C.unique_values_eq([1, 2])])})
print("unique_values_eq no-NULL good/bad:", tryv(s, mk("a1", x=[1, 2, 2])), tryv(s, mk("a2", x=[1, 3])))
def pos(x: int) -> bool: return x > 0
s = pa.DataFrameSchema({"x": pa.Column(D("int64"), checks=[C(pos, element_wise=True)])})
print("element_wise annotated UDF good/bad:", tryv(s, mk("b1", x=[1, 2])), tryv(s, mk("b2", x=[1, -2])))
s = pa.DataFrameSchema({"x": pa.Column(D("int64"), checks=[C(lambda d: d.table[d.key] > 0, groupby="g")]), "g": pa.Column(D("string"))})
print("groupby= (bad row):", tryv(s, mk("c1", x=[1, -1], g=["a", "a"])), "<- accepted at definition; groupby has no effect")
s = pa.DataFrameSchema({"x": pa.Column(D("float64"), checks=[C.ge(0.0)], nullable=True)})
print("float NaN vs ge(0):", tryv(s, mk("d1", x=[1.0, float("nan")])), "(NaN >= 0 is False in duckdb? -> see below)")
print("   duckdb NaN>=0:", con.sql("select 'NaN'::double >= 0 as v").execute().v[0])
s = pa.DataFrameSchema({"x": pa.Column(D("string"), checks=[C.str_matches("a")])})
print("str_matches('a') on 'ba' (pandera anchors with ^):", tryv(s, mk("e1", x=["ba"])))
s = pa.DataFrameSchema({"x": pa.Column(D("timestamp"), checks=[C.ge(__import__('datetime').datetime(2020, 1, 1))])})
t = con.sql("select TIMESTAMP '2019-01-01' as x union all select TIMESTAMP '2021-01-01'")
print("timestamp ge(datetime): bad data ->", tryv(s, t), "| dtype timestamp vs duckdb timestamp(6) reported as mismatch?")

print("\n--- failure case shapes (non-lazy raise, then lazy) ---")
s = pa.DataFrameSchema({"x": pa.Column(D("int64"), checks=[C.ge(0)]), "y": pa.Column(D("string"), checks=[C.isin(["a"])])})
t = mk("f1", x=[1, -1, -2], y=["a", "b", "a"])
try: s.validate(t)
except pe.SchemaError as e:
    print("SchemaError.failure_cases type:", type(e.failure_cases).__name__, "| check_output type:", type(e.check_output).__name__)
    print(repr(e.failure_cases)[:300]); print("message:", str(e)[:200])
try: s.validate(t, lazy=True)
except pe.SchemaErrors as e:
    print("SchemaErrors.failure_cases type:", type(e.failure_cases).__name__); print(e.failure_cases.to_string()[:600])
    print("columns:", list(e.failure_cases.columns))
