"""Check pandera 0.34.1 ibis backend behaviours tacit assumed."""
import warnings
import ibis
import pandera.ibis as pa
import pandera.errors as pe

t = ibis.memtable({"a": [1, 2], "s": ["1", "2"]})

print("--- coerce=True on ibis")
for name, col in [("int->float", pa.Column(float, coerce=True)), ]:
    try:
        pa.DataFrameSchema({"a": col}).validate(t.select("a"))
        print(name, "OK (coerced)")
    except Exception as e:
        print(name, type(e).__name__, str(e)[:150])
try:
    r = pa.DataFrameSchema({"s": pa.Column(int, coerce=True)}).validate(t.select("s"))
    print("str->int OK", r.schema())
except Exception as e:
    print("str->int", type(e).__name__, str(e)[:150])
try:
    r = pa.DataFrameSchema({"a": pa.Column(float)}, coerce=True).validate(t.select("a"))
    print("schema-level coerce OK", r.schema())
except Exception as e:
    print("schema-level coerce", type(e).__name__, str(e)[:150])

print("--- drop_invalid_rows on ibis")
try:
    sch = pa.DataFrameSchema({"a": pa.Column(int, pa.Check.ge(2))}, drop_invalid_rows=True)
    r = sch.validate(t.select("a"), lazy=True)
    print("drop_invalid_rows ->", r.to_pandas().values.tolist())
except Exception as e:
    print("drop_invalid_rows", type(e).__name__, str(e)[:200])

print("--- lazy")
try:
    pa.DataFrameSchema({"a": pa.Column(int, pa.Check.ge(5)), "s": pa.Column(int)}).validate(t, lazy=True)
except pe.SchemaErrors as e:
    print("SchemaErrors", len(e.schema_errors))

print("--- strategies on ibis schema")
try:
    pa.DataFrameSchema({"a": pa.Column(int)}).example()
except Exception as e:
    print("example()", type(e).__name__, str(e)[:200])

print("--- column_name on error")
try:
    pa.DataFrameSchema({"a": pa.Column(int, pa.Check.ge(5))}).validate(t.select("a"))
except pe.SchemaError as e:
    print("column_name=", e.column_name, "reason=", e.reason_code)

print("--- narwhals backend with ibis")
try:
    import narwhals
    print("narwhals installed", narwhals.__version__)
except ImportError:
    print("narwhals not installed")
