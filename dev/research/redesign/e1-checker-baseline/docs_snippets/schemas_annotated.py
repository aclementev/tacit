import tacit
from typing import Annotated

class Iris(tacit.Schema):
    sepal_length: float
    sepal_width: Annotated[float, tacit.Check.gt(0)]
    species: str
