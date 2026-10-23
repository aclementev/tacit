from _typeshed import Incomplete
from ibis.expr.operations.relations import JoinKind
from ibis.expr.types.relations import Table
from typing import Any

__all__ = ['Join', 'JoinExpr']

class Join(Table):
    def __init__(self, arg, collisions=(), equalities=()) -> None: ...
    def join(self, right, /, predicates: Any = (), *, how: JoinKind = 'inner', lname: str = '', rname: str = '{name}_right'): ...
    def asof_join(self, right: Table, /, on, predicates=(), *, tolerance=None, lname: str = '', rname: str = '{name}_right'): ...
    def cross_join(self, right: Table, /, *rest: Table, lname: str = '', rname: str = '{name}_right'): ...
    def select(self, *args, **kwargs): ...
    @property
    def columns(self): ...
    aggregate: Incomplete
    alias: Incomplete
    cast: Incomplete
    compile: Incomplete
    count: Incomplete
    difference: Incomplete
    distinct: Incomplete
    drop: Incomplete
    dropna: Incomplete
    execute: Incomplete
    fill_null: Incomplete
    filter: Incomplete
    group_by: Incomplete
    intersect: Incomplete
    limit: Incomplete
    mutate: Incomplete
    nunique: Incomplete
    order_by: Incomplete
    sample: Incomplete
    schema: Incomplete
    sql: Incomplete
    unbind: Incomplete
    union: Incomplete
    view: Incomplete

# Names in __all__ with no definition:
#   JoinExpr
