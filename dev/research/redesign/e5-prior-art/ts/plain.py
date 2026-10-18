from pyspark.sql import DataFrame
from pyspark.sql.types import LongType
from typedspark import Column, DataSet, Schema
class A(Schema):
    x: Column[LongType]
def f(d: DataSet[A]) -> None: ...
def g(d: DataFrame) -> None:
    f(d)
