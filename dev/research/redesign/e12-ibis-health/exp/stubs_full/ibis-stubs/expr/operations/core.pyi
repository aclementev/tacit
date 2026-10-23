import abc
import ibis.expr.datashape as ds
import ibis.expr.datatypes as dt
from abc import abstractmethod
from ibis.common.annotations import attribute
from ibis.common.graph import Node as Traversable
from ibis.common.grounds import Concrete
from ibis.common.patterns import Coercible
from ibis.common.typing import DefaultTypeVars
from typing import Generic
from typing_extensions import Any, Self, TypeVar

__all__ = ['Node', 'Value', 'Alias', 'Unary', 'Binary', 'Argument', 'ValueOp', 'UnaryOp', 'BinaryOp', 'Scalar', 'Column']

class Node(Concrete, Traversable):
    def equals(self, other) -> bool: ...
T = TypeVar('T', bound=dt.DataType, covariant=True)
S = TypeVar('S', bound=ds.DataShape, default=ds.Any, covariant=True)

class Value(Node, Coercible, DefaultTypeVars, Generic[T, S], metaclass=abc.ABCMeta):
    @classmethod
    def __coerce__(cls, value: Any, T: type | None = None, S: type | None = None) -> Self: ...
    @property
    def name(self) -> str: ...
    @property
    @abstractmethod
    def dtype(self) -> T: ...
    @property
    @abstractmethod
    def shape(self) -> S: ...
    @attribute
    def relations(self): ...
    def to_expr(self): ...
Scalar = Value[T, ds.Scalar]
Column = Value[T, ds.Columnar]

class Alias(Value):
    arg: Value
    name: str
    shape = ...
    dtype = ...

class Unary(Value, metaclass=abc.ABCMeta):
    arg: Value
    @attribute
    def shape(self) -> ds.DataShape: ...
    @attribute
    def relations(self): ...

class Binary(Value, metaclass=abc.ABCMeta):
    left: Value
    right: Value
    @attribute
    def shape(self) -> ds.DataShape: ...
    @attribute
    def relations(self): ...

class Argument(Value):
    name: str
    shape: ds.DataShape
    dtype: dt.DataType
    @attribute
    def param(self) -> str: ...

# Names in __all__ with no definition:
#   BinaryOp
#   UnaryOp
#   ValueOp
