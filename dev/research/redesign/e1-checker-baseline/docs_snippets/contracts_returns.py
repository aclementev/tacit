import ibis
import ibis.expr.types as ir
import tacit


class Iris(tacit.Schema):
    sepal_length: float
    sepal_width: float
    petal_length: float
    petal_width: float
    species: str


class IrisFeatures(Iris):
    sepal_ratio: float
    petal_ratio: float
    petal_area: float


class RawIris(tacit.Schema):
    sepal_length: float
    species: str


con = ibis.duckdb.connect()
table = con.read_csv("iris.csv")

@tacit.contract(returns=IrisFeatures)
def engineer_features(df: tacit.DataFrame[Iris]) -> ir.Table:
    return df.mutate(
        sepal_ratio=df.sepal_length / df.sepal_width,
        petal_ratio=df.petal_length / df.petal_width,
        petal_area=df.petal_length * df.petal_width,
    )
