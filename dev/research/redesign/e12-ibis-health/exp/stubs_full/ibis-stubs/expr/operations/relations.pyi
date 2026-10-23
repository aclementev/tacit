import abc
import ibis.expr.datatypes as dt
import typing
from abc import abstractmethod
from ibis.common.annotations import attribute
from ibis.common.collections import FrozenDict, FrozenOrderedDict
from ibis.common.grounds import Concrete
from ibis.common.typing import Coercible, VarTuple
from ibis.expr.operations.core import Column, Node, Scalar, Value
from ibis.expr.operations.sortkeys import SortKey
from ibis.expr.schema import Schema
from ibis.formats import TableProxy
from typing import Annotated, Any, TypeVar

__all__ = ['Relation', 'Field', 'Project', 'DropColumns', 'Reference', 'SelfReference', 'JoinReference', 'JoinLink', 'JoinChain', 'Sort', 'Filter', 'Limit', 'Aggregate', 'Set', 'Union', 'Intersection', 'Difference', 'PhysicalTable', 'Namespace', 'UnboundTable', 'DatabaseTable', 'InMemoryTable', 'SQLQueryResult', 'AliasedRelation', 'SQLStringView', 'DummyTable', 'FillNull', 'DropNull', 'Sample', 'Distinct', 'TableUnnest']

T = TypeVar('T')

class Relation(Node, Coercible, metaclass=abc.ABCMeta):
    @classmethod
    def __coerce__(cls, value): ...
    @property
    @abstractmethod
    def values(self) -> FrozenOrderedDict[str, Value]: ...
    @property
    @abstractmethod
    def schema(self) -> Schema: ...
    @property
    def fields(self) -> FrozenOrderedDict[str, Column]: ...
    def to_expr(self): ...

class Field(Value):
    rel: Relation
    name: str
    shape = ...
    def __init__(self, rel, name) -> None: ...
    @attribute
    def dtype(self): ...
    @attribute
    def relations(self): ...

class Project(Relation):
    parent: Relation
    values: FrozenOrderedDict[str, NonSortKey[Unaliased[Value]]]
    def __init__(self, parent, values) -> None: ...
    @attribute
    def schema(self): ...

class Simple(Relation):
    parent: Relation
    @attribute
    def values(self): ...
    @attribute
    def schema(self): ...

class DropColumns(Relation):
    parent: Relation
    columns_to_drop: frozenset[str]
    @attribute
    def schema(self): ...
    @attribute
    def values(self): ...

class Reference(Relation, metaclass=abc.ABCMeta):
    parent: Relation
    identifier: int | None = ...
    def __init__(self, parent, identifier) -> None: ...
    @attribute
    def schema(self): ...

class SelfReference(Reference):
    values = ...

class JoinReference(Reference):
    @attribute
    def values(self): ...

class JoinLink(Node):
    how: JoinKind
    table: Reference
    predicates: VarTuple[Value[dt.Boolean]]

class JoinChain(Relation):
    first: Reference
    rest: VarTuple[JoinLink]
    values: FrozenOrderedDict[str, Unaliased[Value]]
    def __init__(self, first, rest, values) -> None: ...
    @property
    def tables(self): ...
    @property
    def length(self): ...
    @attribute
    def schema(self): ...
    def to_expr(self): ...

class Sort(Simple):
    keys: VarTuple[SortKey]
    def __init__(self, parent, keys) -> None: ...

class Filter(Simple):
    predicates: VarTuple[Value[dt.Boolean]]
    def __init__(self, parent, predicates) -> None: ...

class Limit(Simple):
    n: int | Scalar[dt.Integer] | None = ...
    offset: int | Scalar[dt.Integer] = ...

class Aggregate(Relation):
    parent: Relation
    groups: FrozenOrderedDict[str, Unaliased[Value]]
    metrics: FrozenOrderedDict[str, Unaliased[Scalar]]
    def __init__(self, parent, groups, metrics) -> None: ...
    @attribute
    def values(self): ...
    @attribute
    def schema(self): ...

class Set(Relation):
    left: Relation
    right: Relation
    distinct: bool = ...
    values = ...
    def __init__(self, left, right, **kwargs) -> None: ...
    @attribute
    def schema(self): ...

class Union(Set): ...
class Intersection(Set): ...
class Difference(Set): ...

class PhysicalTable(Relation, metaclass=abc.ABCMeta):
    name: str
    values = ...

class Namespace(Concrete):
    catalog: str | None = ...
    database: str | None = ...

class UnboundTable(PhysicalTable):
    schema: Schema
    namespace: Namespace = ...

class DatabaseTable(PhysicalTable):
    schema: Schema
    source: Any
    namespace: Namespace = ...

class InMemoryTable(PhysicalTable):
    schema: Schema
    data: TableProxy

class SQLQueryResult(Relation):
    query: str
    schema: Schema
    source: Any
    values = ...

class AliasedRelation(PhysicalTable):
    parent: Relation
    @attribute
    def schema(self): ...

class SQLStringView(Relation):
    parent: Relation
    query: str
    schema: Schema
    values = ...

class DummyTable(Relation):
    values: FrozenOrderedDict[str, Annotated[Value, None]]
    @attribute
    def schema(self): ...

class FillNull(Simple):
    replacements: Value[dt.Numeric | dt.String] | FrozenDict[str, Any]

class DropNull(Simple):
    how: typing.Literal['any', 'all']
    subset: VarTuple[Column] | None = ...

class Sample(Simple):
    fraction: Annotated[float, None]
    method: typing.Literal['row', 'block']
    seed: int | None = ...

class Distinct(Simple): ...

class TableUnnest(Relation):
    parent: Relation
    column: Value[dt.Array]
    column_name: str
    offset: str | None
    keep_empty: bool
    @attribute
    def values(self): ...
    @attribute
    def schema(self): ...
