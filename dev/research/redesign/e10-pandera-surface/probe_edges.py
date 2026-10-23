"""Edge semantics of pandera's ibis backend that any re-executor must match (or knowingly fix)."""
import sys
import warnings

sys.path.insert(0, "../e4-runtime")
warnings.simplefilter("ignore")
import ibis  # noqa: E402
import pyarrow as pa_  # noqa: E402

import pandera.ibis as pa  # noqa: E402
from pandera.config import ValidationDepth, config_context  # noqa: E402
from common import log_queries, log_reset  # noqa: E402

con = ibis.duckdb.connect()
con.raw_sql("CALL enable_logging('QueryLog')")
D = ibis.dtype


def v(s, t):
    try:
        s.validate(t, lazy=True)
        return "pass"
    except Exception as e:  # noqa: BLE001
        return f"{type(e).__name__}: {str(e)[:160]!r}"


t = con.create_table("e", ibis.memtable(pa_.table({"x": pa_.array([], pa_.int64())})))
s = pa.DataFrameSchema({"x": pa.Column(D("int64"), checks=[pa.Check.ge(0)])})
print("empty table + ge(0):", v(s, t))

t3 = con.create_table("g", ibis.memtable(pa_.table({"x": pa_.array([None, None], pa_.int64())})))
s3 = pa.DataFrameSchema({"x": pa.Column(D("int64"), nullable=True, checks=[pa.Check.ge(0)])})
print("all-NULL nullable column + ge(0):", v(s3, t3))

t2 = con.create_table("f", ibis.memtable(pa_.table({"x": [1, 2], "y": ["a", "b"]})))
s2 = pa.DataFrameSchema({"x": pa.Column(D("int64"), checks=[pa.Check.ge(0)]), "y": pa.Column(D("string"))}, strict=True)
log_reset(con)
with config_context(validation_depth=ValidationDepth.SCHEMA_ONLY):
    s2.validate(t2, lazy=True)
print("SCHEMA_ONLY data queries:", len(log_queries(con)))
log_reset(con)
s2.validate(t2, lazy=True)
print("SCHEMA_AND_DATA data queries:", len(log_queries(con)))

tn = con.create_table("n", ibis.memtable(pa_.table({"x": pa_.array([1, None, None], pa_.int64())})))
su = pa.DataFrameSchema({"x": pa.Column(D("int64"), nullable=True)}, unique=["x"])
print("schema unique=['x'] with two NULLs:", v(su, tn))
tn1 = con.create_table("n1", ibis.memtable(pa_.table({"x": pa_.array([1, 2, None], pa_.int64())})))
print("schema unique=['x'] with one NULL:", v(su, tn1))

tf = con.create_table("fl", ibis.memtable(pa_.table({"x": pa_.array([1.0, float("nan")])})))
for c in (pa.Check.ge(0.0), pa.Check.le(5.0), pa.Check.in_range(0.0, 5.0), pa.Check.isin([1.0]), pa.Check.ne(2.0)):
    sf = pa.DataFrameSchema({"x": pa.Column(D("float64"), nullable=True, checks=[c])})
    print(f"float NaN vs {c.error}:", v(sf, tf)[:60])
