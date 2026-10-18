"""Pandera ibis with the opt-in narwhals backend (needs narwhals)."""
import os
os.environ["PANDERA_USE_NARWHALS_BACKEND"] = "True"
import ibis, narwhals
import pandera.ibis as pa
import pandera.errors as pe
print("narwhals", narwhals.__version__)
t = ibis.memtable({"a": [1, 2], "s": ["1", "2"]})

def tryit(label, fn):
    try:
        r = fn(); print(label, "OK", r)
    except Exception as e:
        print(label, type(e).__name__, str(e)[:160].replace("\n"," "))

tryit("coerce int->float col", lambda: type(pa.DataFrameSchema({"a": pa.Column(float, coerce=True)}).validate(t.select("a"))).__name__)
tryit("coerce str->int", lambda: pa.DataFrameSchema({"s": pa.Column(int, coerce=True)}).validate(t.select("s")).schema())
tryit("check ge", lambda: pa.DataFrameSchema({"a": pa.Column(int, pa.Check.ge(5))}).validate(t.select("a")))
tryit("lazy", lambda: pa.DataFrameSchema({"a": pa.Column(int, pa.Check.ge(5)), "s": pa.Column(int)}).validate(t, lazy=True))
tryit("example", lambda: pa.DataFrameSchema({"a": pa.Column(int)}).example())
tryit("returns type", lambda: type(pa.DataFrameSchema({"a": pa.Column(int)}).validate(t.select("a"))).__name__)
