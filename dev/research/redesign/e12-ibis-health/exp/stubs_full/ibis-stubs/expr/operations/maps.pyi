import ibis.expr.datatypes as dt
from ibis.common.annotations import attribute
from ibis.expr.operations.core import Unary, Value

__all__ = ['Map', 'MapLength', 'MapGet', 'MapContains', 'MapKeys', 'MapValues', 'MapMerge', 'MapValueForKey', 'MapValueOrDefaultForKey', 'MapConcat']

class Map(Value):
    keys: Value[dt.Array]
    values: Value[dt.Array]
    shape = ...
    @attribute
    def dtype(self): ...

class MapLength(Unary):
    arg: Value[dt.Map]
    dtype = ...

class MapGet(Value):
    arg: Value[dt.Map]
    key: Value
    default: Value = ...
    shape = ...
    @attribute
    def dtype(self): ...

class MapContains(Value):
    arg: Value[dt.Map]
    key: Value
    shape = ...
    dtype = ...

class MapKeys(Unary):
    arg: Value[dt.Map]
    @attribute
    def dtype(self): ...

class MapValues(Unary):
    arg: Value[dt.Map]
    @attribute
    def dtype(self): ...

class MapMerge(Value):
    left: Value[dt.Map]
    right: Value[dt.Map]
    shape = ...
    dtype = ...

# Names in __all__ with no definition:
#   MapConcat
#   MapValueForKey
#   MapValueOrDefaultForKey
