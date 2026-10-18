"""Run tacit's real parse/cast on installed ibis 12.0.0 + pandera 0.34.1, default and narwhals backend."""
import os, sys, warnings
if len(sys.argv) > 1 and sys.argv[1] == "narwhals":
    os.environ["PANDERA_USE_NARWHALS_BACKEND"] = "True"
from typing import Annotated
import ibis
import tacit
from tacit import Schema, Check, DataFrame

class S(Schema):
    a: Annotated[int, Check.ge(0)]
    s: str

t = ibis.memtable({"a": [1, 2], "s": ["x", "y"]})
df = S.parse(t)
print(type(df).__name__, isinstance(df, ibis.Table))
bad = ibis.memtable({"a": [-1, 2], "s": ["x", "y"]})
try:
    S.parse(bad)
except Exception as e:
    print("bad:", type(e).__name__, type(e.__cause__).__name__ if e.__cause__ else None)
c = ibis.memtable({"a": ["1", "2"], "s": ["x", "y"]})
print("coerced:", S.parse(c).schema())
