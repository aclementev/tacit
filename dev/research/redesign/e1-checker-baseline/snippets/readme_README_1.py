from typing import Annotated

class Order(tacit.Schema):
    amount: Annotated[float, tacit.Check.ge(0)]
    status: Annotated[str, tacit.Check.isin(["pending", "shipped"])]
    notes: Annotated[str, tacit.Nullable()]
