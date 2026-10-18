from typing import reveal_type

import ibis
import pandera.ibis as pa
from pandera.typing import FieldType
from pandera.typing.ibis import Table


class Raw(pa.DataFrameModel):
    id: FieldType[int]
    amount: FieldType[float] = pa.Field(ge=0)
    status: FieldType[str]


class Enriched(Raw):
    amount_tax: FieldType[float]


@pa.check_types
def enrich(t: Table[Raw]) -> Table[Enriched]:
    return t.mutate(amount_tax=t.amount * 1.2)  # type: ignore


def _static(t: Table[Raw]) -> None:
    reveal_type(Raw.amount)
    reveal_type(t.amount)
    reveal_type(t.amnt)
    reveal_type(t.mutate(x=1))
    t.select(Raw.amount)


con = ibis.duckdb.connect()
raw = ibis.memtable({"id": [1, 2], "amount": [1.0, -2.0], "status": ["a", "b"]})
try:
    print(enrich(Raw.validate(raw)).execute())
except Exception as e:
    print("ERR", type(e).__name__, str(e)[:300])
