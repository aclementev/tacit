# ruff: noqa: B018
"""What do the four checkers see for plain narwhals, polars and pyspark code? (Q3 / Q2)

Lines marked `# E:` should be errors in an ideal world; `# R:` record the revealed type.
"""

from typing import reveal_type

import narwhals.stable.v2 as nw
import polars as pl
from pyspark.sql import DataFrame as SparkDF
from pyspark.sql import functions as F


def narwhals_frames(lf: nw.LazyFrame[pl.LazyFrame], df: nw.DataFrame[pl.DataFrame]) -> None:
    reveal_type(nw.col("a") + 1)  # R: Expr (no dtype)
    reveal_type(nw.col("a").str.to_uppercase())  # R: Expr
    reveal_type(nw.col("a").sum())  # R: Expr
    reveal_type(df.select(nw.col("a") + 1))  # R: DataFrame[pl.DataFrame]
    reveal_type(lf.with_columns(b=nw.col("a") * 2))  # R: LazyFrame[pl.LazyFrame] (same type as input!)
    reveal_type(lf.group_by("a").agg(nw.col("b").sum()))  # R: LazyFrame[...]
    reveal_type(lf.join(lf, on="a"))  # R: LazyFrame
    reveal_type(nw.to_native(lf))  # R: pl.LazyFrame
    reveal_type(df["a"])  # R: Series
    lf.amount  # E: no attribute-style column access (good)
    df.amount  # E: no attribute-style column access (good)
    nw.col("amout")  # E (ideal): typo in a column name -- a string, unchecked
    nw.col("s").str.to_uppercase() + 1  # E (ideal): str + int -- Expr has no dtype
    nw.col("a").dt.year()  # E (ideal) if a is not temporal
    lf.filter(nw.col("a") + 1)  # E (ideal): non-boolean predicate
    lf.with_columns(nw.col("a").fill_nul(0))  # E: typo in a method name (caught)
    lf.collect().to_native()  # ok


def from_native_inference(p: pl.DataFrame, pl_lazy: pl.LazyFrame, s: SparkDF) -> None:
    reveal_type(nw.from_native(p))  # R: DataFrame[pl.DataFrame]
    reveal_type(nw.from_native(pl_lazy))  # R: LazyFrame[pl.LazyFrame]
    reveal_type(nw.from_native(s))  # R: LazyFrame[SparkDF]
    reveal_type(nw.to_native(nw.from_native(s)))  # R: SparkDF


def native_polars(df: pl.DataFrame, lf: pl.LazyFrame) -> None:
    reveal_type(df.with_columns(b=pl.col("a") + 1))  # R: pl.DataFrame
    reveal_type(pl.col("a") + 1)  # R: pl.Expr (no dtype)
    df.amount  # E: polars has no attribute access
    pl.col("amout")  # E (ideal): typo -- unchecked
    lf.with_columns(pl.col("a").fill_nul(0))  # E: method typo (caught)


def native_pyspark(s: SparkDF) -> None:
    reveal_type(s.withColumn("b", F.col("a") + 1))  # R: DataFrame
    reveal_type(s.amount)  # R: Column via __getattr__ (typo passes)
    s.amout  # E (ideal): typo via __getattr__ -- accepted
    F.col("amout")  # E (ideal): unchecked
    reveal_type(F.col("a") + 1)  # R: Column
    reveal_type(F.sum("a"))  # R: Column
    s.withColumn("b", F.col("a").fill_nul(0))  # E: method typo (Column has __getattr__? check)
