import ibis.expr.datatypes as dt
from ibis.common.annotations import attribute
from ibis.common.typing import VarTuple
from ibis.expr.operations.core import Value

__all__ = ['StructField', 'StructColumn']

class StructField(Value):
    arg: Value[dt.Struct]
    field: str
    shape = ...
    @attribute
    def dtype(self) -> dt.DataType: ...
    @property
    def name(self) -> str: ...

class StructColumn(Value):
    names: VarTuple[str]
    values: VarTuple[Value]
    shape = ...
    def __init__(self, names, values) -> None: ...
    @property
    def name(self) -> str: ...
    @attribute
    def dtype(self) -> dt.DataType: ...
