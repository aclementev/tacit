import dataframely as dy
import polars as pl

class Raw(dy.Schema):
    amount = dy.Float64()

reveal_type(Raw.amount.col)
Raw.amnt.col   # typo
def f(df: dy.DataFrame[Raw]) -> pl.DataFrame:
    return df.select(Raw.amount.col, pl.col("amnt"))  # string typo unchecked
