from typing import reveal_type
import narwhals as nw
import polars as pl
import ibis

def f[T: nw.typing.IntoFrame](df: T) -> T:
    return nw.from_native(df).with_columns(y=nw.col("amnt") * 2).to_native()

pdf = pl.DataFrame({"amount": [1.0]})
reveal_type(f(pdf))
t = ibis.memtable({"amount": [1.0]})
n = nw.from_native(t)
reveal_type(n)
print(type(n).__name__, n.collect_schema())
print(n.with_columns(y=nw.col("amount") * 2).to_native().execute())
try:
    f(pdf)
except Exception as e:
    print("ERR typo", type(e).__name__)
