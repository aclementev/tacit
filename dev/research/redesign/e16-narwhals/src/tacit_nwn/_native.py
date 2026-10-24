"""The native-frame story: users keep writing native polars / PySpark; tacit tags and validates.

- `PolarsFrame[S]`, `PolarsLazyFrame[S]`, `SparkFrame[S]` are *static* subclasses of the native
  frame classes (tags). At runtime the value is the plain native object.
  polars and PySpark annotate their methods as returning the concrete class (not Self), so every
  native operation drops the tag: forgetting to re-validate is a type error for free.
- `tag(Orders, native)` validates (one query) and returns the same native type, tagged.
- Class access `Orders.amount` is the column NAME (a str), so `pl.col(Orders.amount)` /
  `F.col(Orders.amount)` / `df[Orders.amount]` get typo checking in native code.
- `@step` validates tagged parameters and the tagged return value at runtime.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Generic, TypeVar, get_args, get_origin, get_type_hints, overload

import narwhals.stable.v2 as nw

from ._frame import DataFrame, Schema
from ._validate import ValidationError

S = TypeVar("S", bound=Schema, covariant=True)
S2 = TypeVar("S2", bound=Schema)
N = TypeVar("N")

if TYPE_CHECKING:
    import polars as pl
    from pyspark.sql import DataFrame as _SparkDF

    class PolarsFrame(pl.DataFrame, Generic[S]): ...

    class PolarsLazyFrame(pl.LazyFrame, Generic[S]): ...

    class SparkFrame(_SparkDF, Generic[S]): ...
else:

    class _Tag(Generic[S]):
        """Runtime placeholder: never instantiated; `PolarsFrame[Orders]` is only read by @step."""

    class PolarsFrame(_Tag[S]): ...

    class PolarsLazyFrame(_Tag[S]): ...

    class SparkFrame(_Tag[S]): ...


NativeFrame = (PolarsFrame, PolarsLazyFrame, SparkFrame)


if TYPE_CHECKING:

    @overload
    def tag(schema: type[S2], frame: pl.DataFrame, /, *, validate: bool = True) -> PolarsFrame[S2]: ...
    @overload
    def tag(schema: type[S2], frame: pl.LazyFrame, /, *, validate: bool = True) -> PolarsLazyFrame[S2]: ...
    @overload
    def tag(schema: type[S2], frame: _SparkDF, /, *, validate: bool = True) -> SparkFrame[S2]: ...


def tag(schema: type[Any], frame: Any, /, *, validate: bool = True) -> Any:
    """Validate a native frame against `schema` and return it (projected, same native type)."""
    eager = isinstance(nw.from_native(frame), nw.DataFrame)
    df = schema.parse(frame) if validate else schema.conform(frame)
    out = nw.LazyFrame(df._compliant_frame, level=df._level)
    return nw.to_native(out.collect()) if eager else nw.to_native(out)


def names(schema: type[S2]) -> type[S2]:
    """Identity, for readability: `n = tc.names(Orders); pl.col(n.amount)`."""
    return schema


def _schema_of(ann: Any) -> type[Schema] | None:
    if get_origin(ann) in (DataFrame, PolarsFrame, PolarsLazyFrame, SparkFrame):
        (s,) = get_args(ann)
        return s if isinstance(s, type) and issubclass(s, Schema) else None
    return None


def step[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
    """Runtime contract from annotations: tagged inputs are conformed (structural, no query), the
    tagged output is parsed (one query). Errors name the step."""
    hints = get_type_hints(fn)
    ins = {k: s for k, v in hints.items() if k != "return" and (s := _schema_of(v))}
    out = _schema_of(hints.get("return"))

    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        import inspect

        bound = inspect.signature(fn).bind(*args, **kwargs)
        for name, sch in ins.items():
            if name in bound.arguments:
                try:
                    sch.conform(bound.arguments[name])
                except ValidationError as e:
                    raise ValidationError(e.schema, f"step {fn.__name__}: argument {name!r}", e.issues) from None
        res = fn(*args, **kwargs)
        if out is not None:
            try:
                out.parse(res)
            except ValidationError as e:
                raise ValidationError(e.schema, f"step {fn.__name__}: return value", e.issues) from None
        return res

    return wrapper
