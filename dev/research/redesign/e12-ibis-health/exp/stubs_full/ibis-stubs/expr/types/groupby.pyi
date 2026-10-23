import ibis.expr.datatypes as dt
import ibis.expr.operations as ops
import ibis.expr.types as ir
from _typeshed import Incomplete
from collections.abc import Sequence
from ibis.common.grounds import Concrete
from ibis.common.typing import VarTuple
from typing import Annotated

__all__ = ['GroupedTable', 'GroupedArray', 'GroupedNumbers']

class GroupedTable(Concrete):
    table: ops.Relation
    groupings: Annotated[VarTuple[ops.Value], None]
    orderings: VarTuple[ops.SortKey] = ...
    havings: VarTuple[ops.Value[dt.Boolean]] = ...
    def __getitem__(self, args): ...
    def __getattr__(self, attr): ...
    def aggregate(self, *metrics, **kwds) -> ir.Table: ...
    agg = aggregate
    def having(self, *predicates: ir.BooleanScalar) -> GroupedTable: ...
    def order_by(self, *by: ir.Value) -> GroupedTable: ...
    def mutate(self, *exprs: ir.Value | Sequence[ir.Value], **kwexprs: ir.Value) -> ir.Table: ...
    def select(self, *exprs, **kwexprs) -> ir.Table: ...
    projection = select
    def over(self, window=None, *, rows=None, range=None, group_by=None, order_by=None) -> GroupedTable: ...
    def count(self) -> ir.Table: ...
    size = count

class GroupedArray:
    arr: Incomplete
    parent: Incomplete
    def __init__(self, arr, parent) -> None: ...
    count: Incomplete
    size = count
    min: Incomplete
    max: Incomplete
    approx_nunique: Incomplete
    approx_median: Incomplete
    group_concat: Incomplete

class GroupedNumbers(GroupedArray):
    mean: Incomplete
    sum: Incomplete
