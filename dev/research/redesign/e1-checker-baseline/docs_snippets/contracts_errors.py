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

@tacit.contract
def transform(df: tacit.DataFrame[Iris]) -> tacit.DataFrame[IrisFeatures]:
    return IrisFeatures.cast(df)

df = Iris.parse(table)
from tacit.errors import ValidationError, ValidationPhase

try:
    result = transform(df)
except ValidationError as exc:
    if exc.phase is ValidationPhase.CONTRACT_INPUT:
        ...
    elif exc.phase is ValidationPhase.CONTRACT_OUTPUT:
        ...
