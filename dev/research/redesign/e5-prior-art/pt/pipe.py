from typing import reveal_type
from typing import reveal_type

import patito as pt
import polars as pl


class Raw(pt.Model):
    id: int
    amount: float = pt.Field(ge=0)
    status: str


class Enriched(Raw):
    amount_tax: float


def enrich(df: pt.DataFrame[Raw]) -> pt.DataFrame[Enriched]:  # may not be generic
    return Enriched.validate(df.with_columns(amount_tax=pl.col("amount") * 1.2))


def wrong_return(df: pt.DataFrame) -> pt.DataFrame:
    return df


raw = Raw.DataFrame({"id": [1, 2], "amount": [1.0, 2.0], "status": ["a", "b"]})
_ = None  # reveal_type(raw)
_ = None  # reveal_type(Raw.amount)
_ = None  # reveal_type(Raw.columns)
try:
    Raw.validate(pl.DataFrame({"id": [1], "amount": [-1.0], "status": ["a"]}))
except Exception as e:
    print("ERR", type(e).__name__, str(e)[:200])
print(Raw.examples({"id": [1, 2]}))
print(Raw.DataFrame({"id":[1],"amount":[1.0],"status":["a"]}).validate())
