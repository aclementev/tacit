import polars as pl
from typing import reveal_type

df = pl.DataFrame({"a": [1, 2], "b": ["x", "y"]})
reveal_type(df)
df2 = df.with_columns(c=pl.col("a") * 2)
reveal_type(df2)
df.select("nonexistent")          # does pyrefly flag?
df2.select("c")
df.filter(pl.col("zzz") > 1)
