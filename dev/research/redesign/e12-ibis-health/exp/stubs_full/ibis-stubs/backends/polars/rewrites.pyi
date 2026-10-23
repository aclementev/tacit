import ibis.expr.operations as ops
from ibis.common.annotations import attribute
from ibis.common.collections import FrozenDict
from ibis.common.typing import VarTuple

__all__ = ['PandasRename', 'PandasJoin', 'PandasAsofJoin']

class PandasRename(ops.Relation):
    parent: ops.Relation
    mapping: FrozenDict[str, str]
    @classmethod
    def from_prefix(cls, parent, prefix): ...
    @attribute
    def values(self): ...
    @attribute
    def schema(self): ...

class PandasJoin(ops.Relation):
    left: ops.Relation
    right: ops.Relation
    left_on: VarTuple[ops.Value]
    right_on: VarTuple[ops.Value]
    how: str
    @attribute
    def values(self): ...
    @attribute
    def schema(self): ...

class PandasAsofJoin(PandasJoin):
    left_by: VarTuple[ops.Value]
    right_by: VarTuple[ops.Value]
    operator: type
