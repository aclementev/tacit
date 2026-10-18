"""Schema-polymorphic helper using tacit as-is: bounded TypeVar on an invariant DataFrame[S]."""
from typing import reveal_type
import ibis, tacit

class HasAmount(tacit.Schema):
    amount: float

class Orders(HasAmount):
    id: int

class Other(tacit.Schema):
    name: str

def only_positive[S: HasAmount](df: tacit.DataFrame[S]) -> tacit.DataFrame[S]:
    return df  # real impl would filter + re-wrap with type(df)._tacit_schema

def use(o: tacit.DataFrame[Orders], x: tacit.DataFrame[Other], h: tacit.DataFrame[HasAmount]) -> None:
    reveal_type(only_positive(o))   # DataFrame[Orders]
    reveal_type(only_positive(h))   # DataFrame[HasAmount]
    only_positive(x)                # error: Other lacks `amount`
