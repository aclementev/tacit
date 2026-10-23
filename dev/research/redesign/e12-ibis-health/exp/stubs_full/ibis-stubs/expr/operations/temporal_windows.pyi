import ibis.expr.datatypes as dt
from ibis.common.annotations import attribute
from ibis.common.collections import FrozenOrderedDict
from ibis.expr.operations.core import Column, Scalar
from ibis.expr.operations.relations import Relation, Unaliased
from typing import Literal

__all__ = ['WindowAggregate']

class WindowAggregate(Relation):
    parent: Relation
    window_type: Literal['tumble', 'hop']
    time_col: Unaliased[Column]
    groups: FrozenOrderedDict[str, Unaliased[Column]]
    metrics: FrozenOrderedDict[str, Unaliased[Scalar]]
    window_size: Scalar[dt.Interval]
    window_slide: Scalar[dt.Interval] | None = ...
    window_offset: Scalar[dt.Interval] | None = ...
    @attribute
    def values(self): ...
    @attribute
    def schema(self): ...
