import os, sys
if "narwhals" in sys.argv: os.environ["PANDERA_USE_NARWHALS_BACKEND"] = "True"
import ibis, pandera.ibis as pa, pandera.errors as pe
t = ibis.memtable({"a": [1, -2, None], "s": ["x", "y", "z"]})
cases = {
 "check": pa.DataFrameSchema({"a": pa.Column(float, pa.Check.ge(0), nullable=True)}),
 "null": pa.DataFrameSchema({"a": pa.Column(float)}),
 "dtype": pa.DataFrameSchema({"a": pa.Column(str, nullable=True)}),
 "missing": pa.DataFrameSchema({"zz": pa.Column(int)}),
 "extra": pa.DataFrameSchema({"a": pa.Column(float, nullable=True)}, strict=True),
}
for k, s in cases.items():
    try:
        s.validate(t)
        print(k, "no error")
    except pe.SchemaError as e:
        fc = e.failure_cases
        print(f"{k:8} reason={e.reason_code.name:24} column_name={e.column_name!r:6} fc_type={type(fc).__module__}.{type(fc).__name__} check={type(e.check).__name__}")
