from __future__ import annotations

import functools
from typing import Any, Callable, ParamSpec, TypeVar, get_type_hints, overload

import ibis.expr.types as ir

from .schema import DataFrame, Schema

P = ParamSpec("P")
R = TypeVar("R")
S = TypeVar("S", bound=Schema)


def _get_schema_type(annotation: Any) -> type[Schema] | None:
    """Extract the Schema type S from a DataFrame[S] annotation, or None."""
    origin = getattr(annotation, "__origin__", None)
    if origin is not DataFrame:
        return None
    args = getattr(annotation, "__args__", None)
    if not args:
        return None
    schema_type = args[0]
    if isinstance(schema_type, type) and issubclass(schema_type, Schema):
        return schema_type
    return None


def _enforce(
    value: Any,
    schema_type: type[Schema],
    *,
    validate: bool,
    label: str,
) -> DataFrame:
    """Apply contract enforcement to a single value.

    Args:
        value: The value to enforce.
        schema_type: The Schema subclass to enforce against.
        validate: If True, use parse() (full validation). Otherwise, use cast().
        label: Human-readable label for error messages (e.g. "parameter 'df'",
               "return value").

    Raises:
        TypeError: If value is not an ibis Table expression.
        ValueError/TypeError: Re-raised from cast()/parse() with context about
            which parameter and schema failed.
    """
    if not isinstance(value, ir.Table):
        raise TypeError(
            f"Contract violation on {label}: "
            f"expected an ibis Table for {schema_type.__name__}, "
            f"got {type(value).__name__}"
        )
    try:
        if validate:
            return schema_type.parse(value)
        return schema_type.cast(value)
    except (TypeError, ValueError) as exc:
        raise type(exc)(
            f"Contract violation on {label} "
            f"[{schema_type.__name__}]: {exc}"
        ) from exc


@overload
def contract(fn: Callable[P, R], /) -> Callable[P, R]: ...
@overload
def contract(
    *, returns: type[S], validate: bool = ...
) -> Callable[[Callable[P, ir.Table]], Callable[P, DataFrame[S]]]: ...
@overload
def contract(
    *, validate: bool = ...
) -> Callable[[Callable[P, R]], Callable[P, R]]: ...


def contract(fn=None, /, *, validate=False, returns=None) -> Any:
    """Decorator that enforces DataFrame schema contracts at function boundaries.

    Inspects type annotations to find DataFrame[S] parameters and return type.
    Calls Schema.cast() on inputs and outputs by default (structural checks only,
    zero execution cost). With validate=True, calls Schema.parse() instead (full
    pandera validation, executes queries).

    Non-DataFrame parameters and return values are passed through unchanged.

    The ``returns`` parameter lets the decorator own the output schema so the
    function body can return a plain ``ir.Table`` without a type error::

        @tacit.contract(returns=IrisFeatures)
        def transform(df: DataFrame[Iris]) -> ir.Table:
            return df.mutate(sepal_ratio=df.sepal_length / df.sepal_width)

    Call sites still see ``DataFrame[IrisFeatures]`` as the return type.

    Usage:
        @tacit.contract
        def transform(df: DataFrame[Iris]) -> DataFrame[IrisFeatures]:
            return IrisFeatures.cast(df.mutate(...))

        @tacit.contract(validate=True)
        def ingest(df: DataFrame[Iris]) -> DataFrame[IrisFeatures]:
            return IrisFeatures.cast(df.mutate(...))

        @tacit.contract(returns=IrisFeatures)
        def transform(df: DataFrame[Iris]) -> ir.Table:
            return df.mutate(...)
    """
    if fn is not None:
        return _wrap(fn, validate=validate, returns=returns)
    return lambda f: _wrap(f, validate=validate, returns=returns)


def _wrap(fn, *, validate, returns=None):
    hints = get_type_hints(fn)
    return_hint = hints.pop("return", None)

    param_schemas: dict[str, type[Schema]] = {}
    for name, hint in hints.items():
        schema = _get_schema_type(hint)
        if schema is not None:
            param_schemas[name] = schema

    if returns is not None:
        return_schema = returns
    else:
        return_schema = _get_schema_type(return_hint) if return_hint else None

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        import inspect

        sig = inspect.signature(fn)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()

        for param_name, schema_type in param_schemas.items():
            if param_name in bound.arguments:
                bound.arguments[param_name] = _enforce(
                    bound.arguments[param_name],
                    schema_type,
                    validate=validate,
                    label=f"parameter '{param_name}'",
                )

        result = fn(*bound.args, **bound.kwargs)

        if return_schema is not None:
            result = _enforce(
                result,
                return_schema,
                validate=validate,
                label="return value",
            )

        return result

    return wrapper
