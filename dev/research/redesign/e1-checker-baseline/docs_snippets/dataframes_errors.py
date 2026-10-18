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


class Order(tacit.Schema):
    amount: float

raw = table
from tacit.errors import CoercionError, ConstraintError, StructuralError

try:
    orders = Order.parse(raw)
except StructuralError:
    # Missing columns, extra columns, wrong dtypes in structural validation
    ...
except CoercionError:
    # Data couldn't be cast into the schema's target types
    ...
except ConstraintError:
    # Data has the right shape but violates checks/nullability
    ...
