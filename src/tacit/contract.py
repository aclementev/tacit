from __future__ import annotations

import functools
from typing import Any, get_type_hints

import ibis.expr.types as ir

from .schema import DataFrame, Schema


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


def contract(fn=None, /, *, validate: bool = False):
    """Decorator that enforces DataFrame schema contracts at function boundaries.

    Inspects type annotations to find DataFrame[S] parameters and return type.
    Calls Schema.cast() on inputs and outputs by default (structural checks only,
    zero execution cost). With validate=True, calls Schema.parse() instead (full
    pandera validation, executes queries).

    Non-DataFrame parameters and return values are passed through unchanged.

    Usage:
        @tacit.contract
        def transform(df: DataFrame[Iris]) -> DataFrame[IrisFeatures]: ...

        @tacit.contract(validate=True)
        def ingest(df: DataFrame[Iris]) -> DataFrame[IrisFeatures]: ...
    """
    if fn is not None:
        return _wrap(fn, validate=validate)
    return lambda f: _wrap(f, validate=validate)


def _wrap(fn, *, validate: bool):
    hints = get_type_hints(fn)
    return_hint = hints.pop("return", None)

    param_schemas: dict[str, type[Schema]] = {}
    for name, hint in hints.items():
        schema = _get_schema_type(hint)
        if schema is not None:
            param_schemas[name] = schema

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
