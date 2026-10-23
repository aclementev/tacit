import abc
import ibis.expr.datatypes as dt
from ibis.common.annotations import attribute
from ibis.common.typing import VarTuple
from ibis.expr.operations.core import Column, Value
from ibis.expr.operations.relations import Relation
from ibis.expr.operations.sortkeys import SortKey
from typing import Literal

__all__ = ['Reduction', 'First', 'Last', 'ArrayCollect', 'GroupConcat', 'Count', 'CountStar', 'CountDistinctStar', 'Arbitrary', 'BitAnd', 'BitOr', 'BitXor', 'Sum', 'Mean', 'Median', 'ApproxMedian', 'Quantile', 'ApproxQuantile', 'MultiQuantile', 'ApproxMultiQuantile', 'StandardDev', 'Variance', 'Correlation', 'Covariance', 'Kurtosis', 'Mode', 'Max', 'Min', 'ArgMax', 'ArgMin', 'CountDistinct', 'ApproxCountDistinct', 'All', 'Any']

class Reduction(Value, metaclass=abc.ABCMeta):
    shape = ...

class Filterable(Value, metaclass=abc.ABCMeta):
    where: Value[dt.Boolean] | None = ...

class Orderable(Filterable, Reduction, metaclass=abc.ABCMeta):
    order_by: VarTuple[SortKey] = ...

class First(Orderable):
    arg: Column[dt.Any]
    include_null: bool = ...
    dtype = ...

class Last(Orderable):
    arg: Column[dt.Any]
    include_null: bool = ...
    dtype = ...

class ArrayCollect(Orderable):
    arg: Column
    include_null: bool = ...
    distinct: bool = ...
    def __init__(self, arg, order_by, distinct, **kwargs) -> None: ...
    @attribute
    def dtype(self): ...

class GroupConcat(Orderable):
    arg: Column
    sep: Value[dt.String]
    dtype = ...

class Count(Filterable, Reduction):
    arg: Column[dt.Any]
    dtype = ...

class CountStar(Filterable, Reduction):
    arg: Relation
    dtype = ...
    @attribute
    def relations(self): ...

class CountDistinctStar(Filterable, Reduction):
    arg: Relation
    dtype = ...
    @attribute
    def relations(self): ...

class Arbitrary(Filterable, Reduction):
    arg: Column[dt.Any]
    dtype = ...

class BitAnd(Filterable, Reduction):
    arg: Column[dt.Integer]
    dtype = ...

class BitOr(Filterable, Reduction):
    arg: Column[dt.Integer]
    dtype = ...

class BitXor(Filterable, Reduction):
    arg: Column[dt.Integer]
    dtype = ...

class Sum(Filterable, Reduction):
    arg: Column[dt.Numeric | dt.Boolean]
    @attribute
    def dtype(self): ...

class Mean(Filterable, Reduction):
    arg: Column[dt.Numeric | dt.Boolean]
    @attribute
    def dtype(self): ...

class QuantileBase(Filterable, Reduction):
    arg: Column
    @attribute
    def dtype(self): ...

class Median(QuantileBase): ...
class ApproxMedian(Median): ...

class Quantile(QuantileBase):
    quantile: Value[dt.Numeric]

class ApproxQuantile(Quantile):
    arg: Column[dt.Numeric]

class MultiQuantile(Filterable, Reduction):
    arg: Column
    quantile: Value[dt.Array[dt.Numeric]]
    @attribute
    def dtype(self): ...

class ApproxMultiQuantile(MultiQuantile):
    arg: Column[dt.Numeric]

class VarianceBase(Filterable, Reduction):
    arg: Column[dt.Numeric | dt.Boolean]
    how: Literal['sample', 'pop']
    @attribute
    def dtype(self): ...

class StandardDev(VarianceBase): ...
class Variance(VarianceBase): ...

class Correlation(Filterable, Reduction):
    left: Column[dt.Numeric | dt.Boolean]
    right: Column[dt.Numeric | dt.Boolean]
    how: Literal['sample', 'pop'] = ...
    dtype = ...

class Covariance(Filterable, Reduction):
    left: Column[dt.Numeric | dt.Boolean]
    right: Column[dt.Numeric | dt.Boolean]
    how: Literal['sample', 'pop']
    dtype = ...

class Kurtosis(Filterable, Reduction):
    arg: Column[dt.Numeric | dt.Boolean]
    how: Literal['sample', 'pop']
    @attribute
    def dtype(self): ...

class Mode(Filterable, Reduction):
    arg: Column
    dtype = ...

class Max(Filterable, Reduction):
    arg: Column
    dtype = ...

class Min(Filterable, Reduction):
    arg: Column
    dtype = ...

class ArgMax(Filterable, Reduction):
    arg: Column
    key: Column
    dtype = ...

class ArgMin(Filterable, Reduction):
    arg: Column
    key: Column
    dtype = ...

class CountDistinct(Filterable, Reduction):
    arg: Column
    dtype = ...

class ApproxCountDistinct(CountDistinct): ...

class All(Filterable, Reduction):
    arg: Column[dt.Boolean]
    dtype = ...

class Any(Filterable, Reduction):
    arg: Column[dt.Boolean]
    dtype = ...
