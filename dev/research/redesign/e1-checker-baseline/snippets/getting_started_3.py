from typing import Annotated

class Iris(tacit.Schema):
    sepal_length: float
    sepal_width: Annotated[float, tacit.Check.gt(0)]
    petal_length: float
    petal_width: float
    species: str
