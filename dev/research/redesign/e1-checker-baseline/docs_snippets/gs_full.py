from typing import Annotated

import ibis
import tacit


class Iris(tacit.Schema):  # (1)
    sepal_length: float
    sepal_width: Annotated[float, tacit.Check.gt(0)]  # (2)
    petal_length: float
    petal_width: float
    species: str


class IrisFeatures(Iris):  # (3)
    sepal_ratio: float
    petal_ratio: float
    petal_area: float


@tacit.contract  # (4)
def engineer_features(df: tacit.DataFrame[Iris]) -> tacit.DataFrame[IrisFeatures]:
    return df.mutate(
        sepal_ratio=df.sepal_length / df.sepal_width,
        petal_ratio=df.petal_length / df.petal_width,
        petal_area=df.petal_length * df.petal_width,
    )


con = ibis.duckdb.connect()
raw = con.read_csv("iris.csv")

iris = Iris.parse(raw)  # (5)
features = engineer_features(iris)  # (6)
