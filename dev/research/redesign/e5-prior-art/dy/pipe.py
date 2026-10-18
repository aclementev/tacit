from typing import reveal_type
import dataframely as dy
import polars as pl


class Raw(dy.Schema):
    id = dy.Int64(primary_key=True)
    amount = dy.Float64(nullable=False)
    status = dy.String(nullable=False)

    @dy.rule()
    def positive(cls) -> pl.Expr:
        return pl.col("amount") >= 0


class Enriched(Raw):
    amount_tax = dy.Float64()


def enrich(df: dy.DataFrame[Raw]) -> dy.DataFrame[Enriched]:
    out = df.with_columns(amount_tax=pl.col("amount") * 1.2)
    return Enriched.validate(out)


def typo(df: dy.DataFrame[Raw]) -> dy.DataFrame[Enriched]:
    out = df.with_columns(amount_tax=pl.col("amnt") * 1.2)  # typo only at runtime
    return Enriched.validate(out)


def wrong_return(df: dy.DataFrame[Raw]) -> dy.DataFrame[Enriched]:
    return df  # should be flagged statically


raw = Raw.validate(pl.DataFrame({"id": [1, 2], "amount": [1.0, 2.0], "status": ["a", "b"]}))
enrich(raw)
def _static_only() -> None:
    enrich(pl.DataFrame({"id": [1]}))  # plain DataFrame passed: flagged?

enrich(Enriched.validate(pl.DataFrame({"id": [1], "amount": [1.0], "status": ["a"], "amount_tax": [1.0]})))  # subclass schema: ok? (contravariance)
reveal_type(raw)
reveal_type(Raw.amount)
reveal_type(raw["amount"])
good, fail = Raw.filter(pl.DataFrame({"id": [1, 2], "amount": [1.0, -2.0], "status": ["a", "b"]}))
reveal_type(good)
reveal_type(fail)
print(good, fail.counts(), fail.invalid())
print(Raw.sample(3))
