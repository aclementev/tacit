import ibis.expr.datatypes as dt
from ibis.common.annotations import attribute
from ibis.common.typing import VarTuple
from ibis.expr.operations.core import Argument, Unary, Value

__all__ = ['Array', 'ArrayLength', 'ArraySlice', 'ArrayIndex', 'ArrayConcat', 'ArrayRepeat', 'ArrayMap', 'ArrayFilter', 'Unnest', 'ArrayContains', 'ArrayPosition', 'ArrayRemove', 'ArrayDistinct', 'ArraySort', 'ArrayUnion', 'ArrayIntersect', 'ArrayZip', 'ArrayFlatten', 'IntegerRange', 'TimestampRange', 'ArrayAgg', 'ArrayMin', 'ArrayMax', 'ArrayMode', 'ArraySum', 'ArrayMean', 'ArrayAny', 'ArrayAll']

class Array(Value):
    exprs: VarTuple[Value]
    @attribute
    def shape(self): ...
    @attribute
    def dtype(self): ...

class ArrayLength(Unary):
    arg: Value[dt.Array]
    dtype = ...
    shape = ...

class ArraySlice(Value):
    arg: Value[dt.Array]
    start: Value[dt.Integer]
    stop: Value[dt.Integer] | None = ...
    dtype = ...
    shape = ...

class ArrayIndex(Value):
    arg: Value[dt.Array]
    index: Value[dt.Integer]
    shape = ...
    @attribute
    def dtype(self): ...

class ArrayConcat(Value):
    arg: VarTuple[Value[dt.Array]]
    shape = ...
    @attribute
    def dtype(self): ...

class ArrayRepeat(Value):
    arg: Value[dt.Array]
    times: Value[dt.Integer]
    dtype = ...
    shape = ...

class ArrayMap(Value):
    arg: Value[dt.Array]
    body: Value
    param: Argument
    index: Argument | None
    shape = ...
    @attribute
    def dtype(self) -> dt.DataType: ...

class ArrayFilter(Value):
    arg: Value[dt.Array]
    body: Value[dt.Boolean]
    param: Argument
    index: Argument | None
    shape = ...
    dtype = ...

class Unnest(Value):
    arg: Value[dt.Array]
    shape = ...
    @attribute
    def dtype(self): ...

class ArrayContains(Value):
    arg: Value[dt.Array]
    other: Value
    dtype = ...
    shape = ...

class ArrayPosition(Value):
    arg: Value[dt.Array]
    other: Value
    dtype = ...
    shape = ...

class ArrayRemove(Value):
    arg: Value[dt.Array]
    other: Value
    dtype = ...
    shape = ...

class ArrayDistinct(Value):
    arg: Value[dt.Array]
    dtype = ...
    shape = ...

class ArraySort(Value):
    arg: Value[dt.Array]
    dtype = ...
    shape = ...

class ArrayUnion(Value):
    left: Value[dt.Array]
    right: Value[dt.Array]
    dtype = ...
    shape = ...

class ArrayIntersect(Value):
    left: Value[dt.Array]
    right: Value[dt.Array]
    dtype = ...
    shape = ...

class ArrayZip(Value):
    arg: VarTuple[Value[dt.Array]]
    shape = ...
    @attribute
    def dtype(self): ...

class ArrayFlatten(Value):
    arg: Value[dt.Array[dt.Array]]
    shape = ...
    @property
    def dtype(self): ...

class Range(Value):
    shape = ...
    @attribute
    def dtype(self) -> dt.DataType: ...

class IntegerRange(Range):
    start: Value[dt.Integer]
    stop: Value[dt.Integer]
    step: Value[dt.Integer]

class TimestampRange(Range):
    start: Value[dt.Timestamp]
    stop: Value[dt.Timestamp]
    step: Value[dt.Interval]

class ArrayAgg(Value):
    arg: Value[dt.Array]
    shape = ...
    @attribute
    def dtype(self) -> dt.DataType: ...

class ArrayMin(ArrayAgg): ...
class ArrayMax(ArrayAgg): ...
class ArrayMode(ArrayAgg): ...

class ArraySum(ArrayAgg):
    arg: Value[dt.Array[dt.Numeric]]

class ArrayMean(ArrayAgg):
    arg: Value[dt.Array[dt.Numeric]]
    @attribute
    def dtype(self) -> dt.DataType: ...

class ArrayAny(ArrayAgg):
    arg: Value[dt.Array[dt.Boolean]]

class ArrayAll(ArrayAgg):
    arg: Value[dt.Array[dt.Boolean]]
