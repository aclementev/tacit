from typing import reveal_type

from pyspark.sql import SparkSession
from pyspark.sql.types import LongType, StringType, DoubleType
from typedspark import Column, DataSet, Schema, transform_to_schema, create_partially_filled_dataset


class Raw(Schema):
    id: Column[LongType]
    amount: Column[DoubleType]
    status: Column[StringType]


class Enriched(Raw):
    amount_tax: Column[DoubleType]


def enrich(df: DataSet[Raw]) -> DataSet[Enriched]:
    return transform_to_schema(df, Enriched, {Enriched.amount_tax: Raw.amount * 1.2})


def typo(df: DataSet[Raw]) -> DataSet[Enriched]:
    return transform_to_schema(df, Enriched, {Enriched.amount_tax: Raw.amnt * 1.2})  # typo: static


def typo_str(df: DataSet[Raw]) -> DataSet[Enriched]:
    return transform_to_schema(df, Enriched, {Enriched.amount_tax: df["amnt"] * 1.2})  # str: runtime only


def wrong_return(df: DataSet[Raw]) -> DataSet[Enriched]:
    return df


def wrong_arg(df: DataSet[Enriched]) -> DataSet[Raw]:
    return df  # Enriched -> Raw: ok? (invariant?)


def use(df: DataSet[Enriched], r: DataSet[Raw]) -> None:
    enrich(r)
    enrich(df)  # subclass schema passed
    wrong_arg(r)  # Raw passed where Enriched required
    reveal_type(df)
    reveal_type(Raw.amount)
    reveal_type(df.amount)
    reveal_type(df.filter(df.amount > 1))
    reveal_type(df.withColumn("x", df.amount))
    reveal_type(df.join(r, "id"))
    reveal_type(df.select(df.id))
