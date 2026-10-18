import ibis, pandera.ibis as pa
from pandera.typing import FieldType
from pandera.typing.ibis import Table

class Raw(pa.DataFrameModel):
    id: FieldType[int]
    amount: FieldType[float] = pa.Field(ge=0)
    class Config:
        drop_invalid_rows = True
        coerce = False

class Enriched(Raw):
    amount_tax: FieldType[float]

@pa.check_types
def enrich(t: Table[Raw]) -> Table[Enriched]:
    return t.mutate(amount_tax=t.amount * 1.2)

good = ibis.memtable({"id": [1, 2], "amount": [1.0, 2.0]})
print(enrich(good).execute().shape)
try:
    enrich(ibis.memtable({"id": [1], "amount": [1.0]}).drop("amount"))
except Exception as e:
    print("ERR", type(e).__name__, str(e)[:120])
bad = ibis.memtable({"id": [1, 2], "amount": [1.0, -2.0]})
try:
    print(Raw.validate(bad, lazy=True).execute())
except Exception as e:
    print("lazy:", type(e).__name__, str(e)[:200])
