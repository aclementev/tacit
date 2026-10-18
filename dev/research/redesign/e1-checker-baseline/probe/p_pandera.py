from typing import Annotated, reveal_type
import tacit
import pandera.ibis as pa

reveal_type(pa)
reveal_type(tacit.Check)
reveal_type(tacit.Check.ge(0))
reveal_type(tacit.Nullable())

class O(tacit.Schema):
    a: Annotated[float, tacit.Check.ge(0)]
