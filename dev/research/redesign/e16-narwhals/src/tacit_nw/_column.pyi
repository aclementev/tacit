# Hand-written facade subset (E16 prototype). A real one would be derived from narwhals by
# execution, as E11 did for ibis. Statically Column[T] is a narwhals Expr, so it can be passed to
# every narwhals API (select, with_columns, filter, group_by ...) with narwhals' own signatures.
from collections.abc import Sequence
from datetime import date, datetime
from typing import Any, Generic, Literal, Self, TypeVar, overload

import narwhals.stable.v2 as nw

T_co = TypeVar("T_co", covariant=True)
V = TypeVar("V")

class Column(nw.Expr, Generic[T_co]):
    # descriptor protocol: drives the dataclass_transform constructor (build(**kw)) types
    @overload
    def __get__(self, obj: None, owner: Any, /) -> str: ...  # Orders.amount -> "amount"
    @overload
    def __get__(self, obj: object, owner: Any, /) -> Self: ...  # df.c.amount -> Column[T]
    def __set__(self, obj: object, value: Column[T_co] | T_co, /) -> None: ...  # type: ignore[misc]
    def alias(self, name: str) -> Self: ...
    # nulls
    def is_null(self) -> Column[bool]: ...  # type: ignore[override]
    def is_not_null(self) -> Column[bool]: ...  # type: ignore[override]
    def fill_null(self: Column[V | None], value: V | Column[V]) -> Column[V]: ...  # type: ignore[override]
    # comparisons: concrete per-family overloads so nullability propagates (a TypeVar V would absorb None)
    @overload  # type: ignore[override]
    def __eq__(self: Column[int], other: int | Column[int]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __eq__(self: Column[int | None], other: int | Column[int] | Column[int | None]) -> Column[bool | None]: ...
    @overload
    def __eq__(self: Column[float], other: float | Column[float]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __eq__(self: Column[float | None], other: float | Column[float] | Column[float | None]) -> Column[bool | None]: ...
    @overload
    def __eq__(self: Column[str], other: str | Column[str]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __eq__(self: Column[str | None], other: str | Column[str] | Column[str | None]) -> Column[bool | None]: ...
    @overload
    def __eq__(self: Column[bool], other: bool | Column[bool]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __eq__(self: Column[bool | None], other: bool | Column[bool] | Column[bool | None]) -> Column[bool | None]: ...
    @overload
    def __eq__(self: Column[date], other: date | Column[date]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __eq__(self: Column[date | None], other: date | Column[date] | Column[date | None]) -> Column[bool | None]: ...
    @overload
    def __eq__(self: Column[datetime], other: datetime | Column[datetime]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __eq__(self: Column[datetime | None], other: datetime | Column[datetime] | Column[datetime | None]) -> Column[bool | None]: ...
    @overload  # type: ignore[override]
    def __ne__(self: Column[int], other: int | Column[int]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __ne__(self: Column[int | None], other: int | Column[int] | Column[int | None]) -> Column[bool | None]: ...
    @overload
    def __ne__(self: Column[float], other: float | Column[float]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __ne__(self: Column[float | None], other: float | Column[float] | Column[float | None]) -> Column[bool | None]: ...
    @overload
    def __ne__(self: Column[str], other: str | Column[str]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __ne__(self: Column[str | None], other: str | Column[str] | Column[str | None]) -> Column[bool | None]: ...
    @overload
    def __ne__(self: Column[bool], other: bool | Column[bool]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __ne__(self: Column[bool | None], other: bool | Column[bool] | Column[bool | None]) -> Column[bool | None]: ...
    @overload
    def __ne__(self: Column[date], other: date | Column[date]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __ne__(self: Column[date | None], other: date | Column[date] | Column[date | None]) -> Column[bool | None]: ...
    @overload
    def __ne__(self: Column[datetime], other: datetime | Column[datetime]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __ne__(self: Column[datetime | None], other: datetime | Column[datetime] | Column[datetime | None]) -> Column[bool | None]: ...
    @overload  # type: ignore[override]
    def __gt__(self: Column[int], other: int | Column[int]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __gt__(self: Column[int | None], other: int | Column[int] | Column[int | None]) -> Column[bool | None]: ...
    @overload
    def __gt__(self: Column[float], other: float | Column[float]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __gt__(self: Column[float | None], other: float | Column[float] | Column[float | None]) -> Column[bool | None]: ...
    @overload
    def __gt__(self: Column[str], other: str | Column[str]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __gt__(self: Column[str | None], other: str | Column[str] | Column[str | None]) -> Column[bool | None]: ...
    @overload
    def __gt__(self: Column[bool], other: bool | Column[bool]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __gt__(self: Column[bool | None], other: bool | Column[bool] | Column[bool | None]) -> Column[bool | None]: ...
    @overload
    def __gt__(self: Column[date], other: date | Column[date]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __gt__(self: Column[date | None], other: date | Column[date] | Column[date | None]) -> Column[bool | None]: ...
    @overload
    def __gt__(self: Column[datetime], other: datetime | Column[datetime]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __gt__(self: Column[datetime | None], other: datetime | Column[datetime] | Column[datetime | None]) -> Column[bool | None]: ...
    @overload  # type: ignore[override]
    def __ge__(self: Column[int], other: int | Column[int]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __ge__(self: Column[int | None], other: int | Column[int] | Column[int | None]) -> Column[bool | None]: ...
    @overload
    def __ge__(self: Column[float], other: float | Column[float]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __ge__(self: Column[float | None], other: float | Column[float] | Column[float | None]) -> Column[bool | None]: ...
    @overload
    def __ge__(self: Column[str], other: str | Column[str]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __ge__(self: Column[str | None], other: str | Column[str] | Column[str | None]) -> Column[bool | None]: ...
    @overload
    def __ge__(self: Column[bool], other: bool | Column[bool]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __ge__(self: Column[bool | None], other: bool | Column[bool] | Column[bool | None]) -> Column[bool | None]: ...
    @overload
    def __ge__(self: Column[date], other: date | Column[date]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __ge__(self: Column[date | None], other: date | Column[date] | Column[date | None]) -> Column[bool | None]: ...
    @overload
    def __ge__(self: Column[datetime], other: datetime | Column[datetime]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __ge__(self: Column[datetime | None], other: datetime | Column[datetime] | Column[datetime | None]) -> Column[bool | None]: ...
    @overload  # type: ignore[override]
    def __lt__(self: Column[int], other: int | Column[int]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __lt__(self: Column[int | None], other: int | Column[int] | Column[int | None]) -> Column[bool | None]: ...
    @overload
    def __lt__(self: Column[float], other: float | Column[float]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __lt__(self: Column[float | None], other: float | Column[float] | Column[float | None]) -> Column[bool | None]: ...
    @overload
    def __lt__(self: Column[str], other: str | Column[str]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __lt__(self: Column[str | None], other: str | Column[str] | Column[str | None]) -> Column[bool | None]: ...
    @overload
    def __lt__(self: Column[bool], other: bool | Column[bool]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __lt__(self: Column[bool | None], other: bool | Column[bool] | Column[bool | None]) -> Column[bool | None]: ...
    @overload
    def __lt__(self: Column[date], other: date | Column[date]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __lt__(self: Column[date | None], other: date | Column[date] | Column[date | None]) -> Column[bool | None]: ...
    @overload
    def __lt__(self: Column[datetime], other: datetime | Column[datetime]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __lt__(self: Column[datetime | None], other: datetime | Column[datetime] | Column[datetime | None]) -> Column[bool | None]: ...
    @overload  # type: ignore[override]
    def __le__(self: Column[int], other: int | Column[int]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __le__(self: Column[int | None], other: int | Column[int] | Column[int | None]) -> Column[bool | None]: ...
    @overload
    def __le__(self: Column[float], other: float | Column[float]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __le__(self: Column[float | None], other: float | Column[float] | Column[float | None]) -> Column[bool | None]: ...
    @overload
    def __le__(self: Column[str], other: str | Column[str]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __le__(self: Column[str | None], other: str | Column[str] | Column[str | None]) -> Column[bool | None]: ...
    @overload
    def __le__(self: Column[bool], other: bool | Column[bool]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __le__(self: Column[bool | None], other: bool | Column[bool] | Column[bool | None]) -> Column[bool | None]: ...
    @overload
    def __le__(self: Column[date], other: date | Column[date]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __le__(self: Column[date | None], other: date | Column[date] | Column[date | None]) -> Column[bool | None]: ...
    @overload
    def __le__(self: Column[datetime], other: datetime | Column[datetime]) -> Column[bool]: ...  # type: ignore[overload-overlap]
    @overload
    def __le__(self: Column[datetime | None], other: datetime | Column[datetime] | Column[datetime | None]) -> Column[bool | None]: ...
    def is_in(self: Column[V | None], other: Sequence[V]) -> Column[bool]: ...  # type: ignore[override]
    def is_between(self: Column[V], lower_bound: V, upper_bound: V) -> Column[bool]: ...  # type: ignore[override]
    # boolean algebra
    def __and__(self: Column[bool | None], other: Column[bool] | Column[bool | None] | bool) -> Column[bool]: ...  # type: ignore[override]
    def __or__(self: Column[bool | None], other: Column[bool] | Column[bool | None] | bool) -> Column[bool]: ...  # type: ignore[override]
    def __invert__(self: Column[bool | None]) -> Self: ...  # type: ignore[override]
    # arithmetic
    @overload  # type: ignore[override]
    def __add__(self: Column[int], other: int | Column[int]) -> Column[int]: ...  # type: ignore[overload-overlap]
    @overload
    def __add__(self: Column[float], other: float | Column[float]) -> Column[float]: ...  # type: ignore[overload-overlap]
    @overload
    def __add__(self: Column[float | None], other: float | Column[float] | Column[float | None]) -> Column[float | None]: ...
    @overload  # type: ignore[override]
    def __sub__(self: Column[int], other: int | Column[int]) -> Column[int]: ...  # type: ignore[overload-overlap]
    @overload
    def __sub__(self: Column[float], other: float | Column[float]) -> Column[float]: ...  # type: ignore[overload-overlap]
    @overload
    def __sub__(self: Column[float | None], other: float | Column[float] | Column[float | None]) -> Column[float | None]: ...
    @overload  # type: ignore[override]
    def __mul__(self: Column[int], other: int | Column[int]) -> Column[int]: ...  # type: ignore[overload-overlap]
    @overload
    def __mul__(self: Column[float], other: float | Column[float]) -> Column[float]: ...  # type: ignore[overload-overlap]
    @overload
    def __mul__(self: Column[float | None], other: float | Column[float] | Column[float | None]) -> Column[float | None]: ...
    @overload  # type: ignore[override]
    def __truediv__(self: Column[float], other: float | Column[float]) -> Column[float]: ...  # type: ignore[overload-overlap]
    @overload
    def __truediv__(self: Column[float | None], other: float | Column[float] | Column[float | None]) -> Column[float | None]: ...
    @overload  # type: ignore[override]
    def __rsub__(self: Column[float], other: float) -> Column[float]: ...  # type: ignore[overload-overlap]
    @overload
    def __rsub__(self: Column[float | None], other: float) -> Column[float | None]: ...
    @overload  # type: ignore[override]
    def __radd__(self: Column[float], other: float) -> Column[float]: ...  # type: ignore[overload-overlap]
    @overload
    def __radd__(self: Column[float | None], other: float) -> Column[float | None]: ...
    def abs(self: Column[V]) -> Column[V]: ...  # type: ignore[override]
    def round(self: Column[float], decimals: int = 0) -> Column[float]: ...  # type: ignore[override]
    # reductions (SQL semantics: nulls skipped)
    @overload  # type: ignore[override]
    def sum(self: Column[int | None]) -> Column[int]: ...
    @overload
    def sum(self: Column[float | None]) -> Column[float]: ...
    def mean(self: Column[float | None]) -> Column[float]: ...  # type: ignore[override]
    def median(self: Column[float | None]) -> Column[float]: ...  # type: ignore[override]
    def std(self: Column[float | None], *, ddof: int = 1) -> Column[float]: ...  # type: ignore[override]
    def min(self: Column[V | None]) -> Column[V]: ...  # type: ignore[override]
    def max(self: Column[V | None]) -> Column[V]: ...  # type: ignore[override]
    def count(self) -> Column[int]: ...  # type: ignore[override]
    def n_unique(self) -> Column[int]: ...  # type: ignore[override]
    # windows
    def over(self, *partition_by: str | Sequence[str], order_by: str | Sequence[str] | None = None) -> Self: ...  # type: ignore[override]
    @overload  # type: ignore[override]
    def rank(self, method: Literal["min", "max", "dense", "ordinal"] = ..., *, descending: bool = False) -> Column[int]: ...
    @overload
    def rank(self, method: Literal["average"], *, descending: bool = False) -> Column[float]: ...
    def cum_sum(self: Column[V], *, reverse: bool = False) -> Column[V]: ...  # type: ignore[override]
    def shift(self: Column[V | None], n: int) -> Column[V | None]: ...  # type: ignore[override]
    # namespaces
    @property
    def str(self) -> StrNamespace[T_co]: ...  # type: ignore[override]
    @property
    def dt(self) -> DtNamespace[T_co]: ...  # type: ignore[override]
    # untyped casts: re-declare through a schema
    def cast(self, dtype: Any) -> Column[Any]: ...  # type: ignore[override]

class StrNamespace(Generic[T_co]):
    @overload
    def to_uppercase(self: StrNamespace[str]) -> Column[str]: ...
    @overload
    def to_uppercase(self: StrNamespace[str | None]) -> Column[str | None]: ...
    @overload
    def to_lowercase(self: StrNamespace[str]) -> Column[str]: ...
    @overload
    def to_lowercase(self: StrNamespace[str | None]) -> Column[str | None]: ...
    @overload
    def len_chars(self: StrNamespace[str]) -> Column[int]: ...
    @overload
    def len_chars(self: StrNamespace[str | None]) -> Column[int | None]: ...
    @overload
    def contains(self: StrNamespace[str], pattern: str, *, literal: bool = False) -> Column[bool]: ...
    @overload
    def contains(self: StrNamespace[str | None], pattern: str, *, literal: bool = False) -> Column[bool | None]: ...
    @overload
    def starts_with(self: StrNamespace[str], prefix: str) -> Column[bool]: ...
    @overload
    def starts_with(self: StrNamespace[str | None], prefix: str) -> Column[bool | None]: ...
    @overload
    def slice(self: StrNamespace[str], offset: int, length: int | None = None) -> Column[str]: ...
    @overload
    def slice(self: StrNamespace[str | None], offset: int, length: int | None = None) -> Column[str | None]: ...

class DtNamespace(Generic[T_co]):
    @overload
    def year(self: DtNamespace[date]) -> Column[int]: ...
    @overload
    def year(self: DtNamespace[date | None]) -> Column[int | None]: ...
    @overload
    def month(self: DtNamespace[date]) -> Column[int]: ...
    @overload
    def month(self: DtNamespace[date | None]) -> Column[int | None]: ...
    @overload
    def truncate(self: DtNamespace[datetime], every: str) -> Column[datetime]: ...
    @overload
    def truncate(self: DtNamespace[datetime | None], every: str) -> Column[datetime | None]: ...
    @overload
    def date(self: DtNamespace[datetime]) -> Column[date]: ...
    @overload
    def date(self: DtNamespace[datetime | None]) -> Column[date | None]: ...

def lit(value: V) -> Column[V]: ...
def expr(e: nw.Expr) -> Column[Any]: ...

class _When:
    def then(self, value: V | Column[V]) -> _Then[V]: ...

class _WhenV(Generic[V]):
    def then(self, value: V | Column[V]) -> _Then[V]: ...

class _Then(Generic[V]):
    def when(self, cond: Column[bool] | Column[bool | None]) -> _WhenV[V]: ...
    def otherwise(self, value: V | Column[V]) -> Column[V]: ...

def when(cond: Column[bool] | Column[bool | None]) -> _When: ...
