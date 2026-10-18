from typing import reveal_type

import ibis
import tacit


class Raw(tacit.Schema):
    id: int
    amount: float
    status: str


class Enriched(Raw):
    amount_tax: float


@tacit.contract
def enrich(df: tacit.DataFrame[Raw]) -> tacit.DataFrame[Enriched]:
    return df.mutate(amount_tax=df.amount * 1.2)


@tacit.contract
def typo(df: tacit.DataFrame[Raw]) -> tacit.DataFrame[Enriched]:
    return df.mutate(amount_tax=df.amnt * 1.2)  # typo


def wrong_return(df: tacit.DataFrame[Raw]) -> tacit.DataFrame[Enriched]:
    return df


def static(df: tacit.DataFrame[Raw], e: tacit.DataFrame[Enriched], plain: ibis.Table) -> None:
    enrich(e)  # subclass schema passed
    enrich(plain)  # untyped table passed
    reveal_type(df)
    reveal_type(Raw.amount)
    reveal_type(df.amount)
    reveal_type(df.amnt)
    reveal_type(df.mutate(x=df.amount))
    reveal_type(Raw.parse(plain))


t = ibis.memtable({"id": [1], "amount": [1.0], "status": ["a"]})
print(enrich(Raw.parse(t)).execute())
try:
    typo(Raw.parse(t))
except Exception as e:
    print("ERR typo", type(e).__name__, str(e)[:150])
try:
    wrong_return(Raw.parse(t))
except Exception as e:
    print("ERR", type(e).__name__)
