import abc
import ibis.expr.types as ir
from collections.abc import Sequence
from ibis.common.bases import Abstract as Abstract
from ibis.common.grounds import Concrete as Concrete
from ibis.common.typing import VarTuple as VarTuple

class Expandable(Abstract, metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def expand(self, table: ir.Table) -> Sequence[ir.Value]: ...

class Selector(Concrete, Expandable, metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def expand_names(self, table: ir.Table) -> frozenset[str]: ...
    def expand(self, table: ir.Table) -> Sequence[ir.Value]: ...
    def __and__(self, other: Selector) -> Selector: ...
    def __or__(self, other: Selector) -> Selector: ...
    def __invert__(self) -> Selector: ...

class Or(Selector):
    left: Selector
    right: Selector
    def expand_names(self, table: ir.Table) -> frozenset[str]: ...

class And(Selector):
    left: Selector
    right: Selector
    def expand_names(self, table: ir.Table) -> frozenset[str]: ...

class Any(Selector):
    selectors: VarTuple[Selector]
    def expand_names(self, table: ir.Table) -> frozenset[str]: ...

class All(Selector):
    selectors: VarTuple[Selector]
    def expand_names(self, table: ir.Table) -> frozenset[str]: ...

class Not(Selector):
    selector: Selector
    def expand_names(self, table: ir.Table) -> frozenset[str]: ...
