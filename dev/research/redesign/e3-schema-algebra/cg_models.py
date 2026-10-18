"""Hand-written source schemas (owned by some team)."""

from datetime import datetime
from typing import Annotated

from tx import Schema


class Iris(Schema):
    sepal_length: Annotated[float, "check: ge(0)"]  # stands in for tacit.Check metadata
    sepal_width: float
    petal_length: float
    petal_width: float
    species: str
    measured_at: datetime
