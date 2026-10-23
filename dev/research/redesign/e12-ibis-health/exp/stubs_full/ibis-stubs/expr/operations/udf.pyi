import abc
import enum
import ibis.expr.datatypes as dt
import ibis.expr.operations as ops
import ibis.expr.types as ir
from collections.abc import Callable
from ibis.common.annotations import attribute
from typing import Any, TypeVar, overload

__all__ = ['ScalarUDF', 'AggUDF', 'scalar', 'agg']

class InputType(enum.Enum):
    BUILTIN = ...
    PANDAS = ...
    PYARROW = ...
    PYTHON = ...

class ScalarUDF(ops.Impure, metaclass=abc.ABCMeta):
    @attribute
    def shape(self): ...

class AggUDF(ops.Reduction, ops.Impure, metaclass=abc.ABCMeta):
    where: ops.Value[dt.Boolean] | None = ...
S = TypeVar('S', bound=ops.Value)
B = TypeVar('B', bound=ops.Value)

class _UDF(abc.ABC, metaclass=abc.ABCMeta): ...

class scalar(_UDF):
    @overload
    @classmethod
    def builtin(cls, fn: Callable) -> Callable[..., ir.Value]: ...
    @overload
    @classmethod
    def builtin(cls, *, name: str | None = None, database: str | None = None, catalog: str | None = None, signature: tuple[tuple[Any, ...], Any] | None = None, **kwargs: Any) -> Callable[[Callable], Callable[..., ir.Value]]: ...
    @overload
    @classmethod
    def python(cls, fn: Callable) -> Callable[..., ir.Value]: ...
    @overload
    @classmethod
    def python(cls, *, name: str | None = None, database: str | None = None, catalog: str | None = None, signature: tuple[tuple[Any, ...], Any] | None = None, **kwargs: Any) -> Callable[[Callable], Callable[..., ir.Value]]: ...
    @overload
    @classmethod
    def pandas(cls, fn: Callable) -> Callable[..., ir.Value]: ...
    @overload
    @classmethod
    def pandas(cls, *, name: str | None = None, database: str | None = None, catalog: str | None = None, signature: tuple[tuple[Any, ...], Any] | None = None, **kwargs: Any) -> Callable[[Callable], Callable[..., ir.Value]]: ...
    @overload
    @classmethod
    def pyarrow(cls, fn: Callable) -> Callable[..., ir.Value]: ...
    @overload
    @classmethod
    def pyarrow(cls, *, name: str | None = None, database: str | None = None, catalog: str | None = None, signature: tuple[tuple[Any, ...], Any] | None = None, **kwargs: Any) -> Callable[[Callable], Callable[..., ir.Value]]: ...

class agg(_UDF):
    @overload
    @classmethod
    def builtin(cls, fn: Callable) -> Callable[..., ir.Value]: ...
    @overload
    @classmethod
    def builtin(cls, *, name: str | None = None, database: str | None = None, catalog: str | None = None, signature: tuple[tuple[Any, ...], Any] | None = None, **kwargs: Any) -> Callable[[Callable], Callable[..., ir.Value]]: ...
