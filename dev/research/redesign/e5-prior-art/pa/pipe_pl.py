from typing import reveal_type

import pandera.polars as pa
import polars as pl
from pandera.typing.polars import DataFrame, Series


class Raw(pa.DataFrameModel):
    id: int
    amount: float = pa.Field(ge=0)
    status: str


class Enriched(Raw):
    amount_tax: float


@pa.check_types
def enrich(df: DataFrame[Raw]) -> DataFrame[Enriched]:
    return df.with_columns(amount_tax=pl.col("amount") * 1.2)  # type: ignore


@pa.check_types
def typo(df: DataFrame[Raw]) -> DataFrame[Enriched]:
    return df.with_columns(amount_tax=pl.col("amnt") * 1.2)  # type: ignore


def wrong_return(df: DataFrame[Raw]) -> DataFrame[Enriched]:
    return df


def _static() -> None:
    enrich(pl.DataFrame({"id": [1]}))  # plain frame
    raw = DataFrame[Raw](pl.DataFrame({"id": [1], "amount": [1.0], "status": ["a"]}))
    reveal_type(raw)
    reveal_type(Raw.amount)
    reveal_type(Raw.amnt)
    reveal_type(raw.with_columns(x=1))


raw = pl.DataFrame({"id": [1, 2], "amount": [1.0, 2.0], "status": ["a", "b"]})
print(enrich(raw))
try:
    enrich(pl.DataFrame({"id": [1], "amount": [-1.0], "status": ["a"]}))
except Exception as e:
    print("ERR", type(e).__name__, str(e)[:150])
try:
    typo(raw)
except Exception as e:
    print("ERR typo", type(e).__name__, str(e)[:150])
# lazy validation + soft failure info
try:
    Raw.validate(pl.DataFrame({"id": [1, 2], "amount": [-1.0, -2.0], "status": ["a", "b"]}), lazy=True)
except pa.errors.SchemaErrors as e:
    print("SchemaErrors", e.failure_cases)
