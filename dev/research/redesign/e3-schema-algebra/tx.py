"""Prototype of tacit primitives used by the e3 experiments.

Standalone (does not import tacit) so the DataFrame bound and extra methods can
be varied freely. Differences from tacit 0.2.0 that the experiments rely on:

- `DataFrame[S: SchemaLike]`: the bound is a Protocol, not the `Schema` class,
  so schema Protocols (structural "has at least these columns") are legal
  type arguments.
- Schema-preserving ibis methods (`filter`, `order_by`, `distinct`, `limit`,
  `head`, `cache`) are overridden to return `DataFrame[S]` instead of `Table`.
- `df.retag(table)` re-wraps a table produced from `df` under the same S,
  with a runtime column check (for generic same-schema-out steps).
- `Schema.cast(..., strict=False)` and `conforms(df, Proto)` support
  "at least these columns" checks at runtime.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, ClassVar, Literal, Protocol, Self, get_type_hints

import ibis
import ibis.expr.types as ir
import ibis.selectors as s
from ibis.common.deferred import Deferred
from ibis.selectors import IfAnyAll


class SchemaLike(Protocol):
    """Anything that declares tacit columns: Schema subclasses AND schema Protocols."""

    __tacit_schema__: ClassVar[bool]


def fields_of(schema: type) -> dict[str, Any]:
    """Columns declared by a Schema class or a schema Protocol (runtime)."""
    hints = get_type_hints(schema)
    return {
        k: v
        for k, v in hints.items()
        if not k.startswith("_") and getattr(v, "__origin__", None) is not ClassVar
    }


class DataFrame[S: SchemaLike](ir.Table):
    __slots__ = ("_tacit_schema",)
    _tacit_schema: type[S]  # declared so checkers don't route it through ibis __getattr__

    def __tacit_type_is_invariant__(self, x: S) -> S:  # forces invariance in S
        raise NotImplementedError

    @classmethod
    def _wrap(cls, table: ir.Table, schema: type[S]) -> DataFrame[S]:
        df = cls(table.op())
        object.__setattr__(df, "_tacit_schema", schema)
        return df

    @property
    def tacit_schema(self) -> type[S]:
        return self._tacit_schema

    def to_table(self) -> ir.Table:
        return self

    def extend_to[O: SchemaLike](
        self: Into[O], out: type[O], /, **exprs: ir.Value | Deferred
    ) -> DataFrame[O]:
        """mutate(**exprs) and cast to `out`, where `out` must subclass this frame's schema."""
        if not issubclass(out, getattr(self, "_tacit_schema")):
            raise TypeError(f"{out.__name__} must subclass the input schema")
        result = self.to_table().mutate(**exprs)
        _check(result, out, strict=True)
        return DataFrame._wrap(result, out)

    def retag(self, table: ir.Table) -> DataFrame[S]:
        """Re-wrap `table` under this frame's schema (runtime column check)."""
        schema = self._tacit_schema
        _check(table, schema, strict=isinstance(schema, type) and issubclass(schema, Schema))
        return DataFrame._wrap(table, schema)

    # --- schema-preserving overrides: same S in, same S out -------------------
    def filter(
        self,
        *predicates: ir.BooleanValue | bool | Sequence[ir.BooleanValue | bool] | IfAnyAll | Deferred,
    ) -> DataFrame[S]:
        return DataFrame._wrap(super().filter(*predicates), self._tacit_schema)

    def order_by(
        self,
        *by: str | ir.Column | s.Selector | Deferred | Sequence[str | ir.Column | s.Selector | Deferred],
    ) -> DataFrame[S]:
        return DataFrame._wrap(super().order_by(*by), self._tacit_schema)

    def distinct(
        self,
        *,
        on: str | Iterable[str] | s.Selector | None = None,
        keep: Literal["first", "last"] | None = "first",
    ) -> DataFrame[S]:
        return DataFrame._wrap(super().distinct(on=on, keep=keep), self._tacit_schema)

    def limit(self, n: int | None, /, *, offset: int = 0) -> DataFrame[S]:
        return DataFrame._wrap(super().limit(n, offset=offset), self._tacit_schema)

    def head(self, n: int = 5, /) -> DataFrame[S]:
        return DataFrame._wrap(super().head(n), self._tacit_schema)

    def cache(self) -> DataFrame[S]:
        return DataFrame._wrap(super().cache(), self._tacit_schema)


def _check(table: ir.Table, schema: type, *, strict: bool) -> None:
    want = ibis.schema(fields_of(schema))
    have = table.schema()
    want_names: list[str] = list(want.names)  # type: ignore  # ibis types .names as Attribute
    have_names: list[str] = list(have.names)  # type: ignore
    missing = [n for n in want_names if n not in have_names]
    extra = [n for n in have_names if n not in want_names] if strict else []
    wrong = [n for n in want_names if n in have_names and have[n] != want[n]]
    if missing or extra or wrong:
        raise TypeError(
            f"{schema.__name__}: missing={missing} extra={extra} wrong_type={wrong}"
        )


class Schema:
    __tacit_schema__: ClassVar[bool] = True

    # Output-schema-owned constructors: Self is fixed by the receiver, so no
    # TypeVar has to be inferred; Into[Self] demands Self <: each input schema.
    @classmethod
    def from_mutate(cls, df: Into[Self], /, **exprs: ir.Value | Deferred) -> DataFrame[Self]:
        if not issubclass(cls, getattr(df, "_tacit_schema")):
            raise TypeError(f"{cls.__name__} must subclass the input schema")
        return cls.cast(df.to_table().mutate(**exprs))

    @classmethod
    def from_join(
        cls,
        left: Into[Self],
        right: Into[Self],
        predicates: str | Sequence[str] = (),
        *,
        how: Literal["inner", "left", "right", "outer"] = "inner",
    ) -> DataFrame[Self]:
        return join(left, right, cls, predicates, how=how)

    # Runtime derivations (statically opaque without the mypy plugin / codegen).
    @classmethod
    def pick(cls, *names: str) -> type[Schema]:
        from derive import pick

        return pick(cls, *names).build(f"{cls.__name__}_pick")

    @classmethod
    def drop(cls, *names: str) -> type[Schema]:
        from derive import drop

        return drop(cls, *names).build(f"{cls.__name__}_drop")

    @classmethod
    def rename(cls, **mapping: str) -> type[Schema]:
        from derive import rename

        return rename(cls, **mapping).build(f"{cls.__name__}_rename")

    @classmethod
    def extend(cls, **cols: type) -> type[Schema]:
        from derive import extend

        return extend(cls, **cols).build(f"{cls.__name__}_extend")

    @classmethod
    def cast(cls, table: ir.Table) -> DataFrame[Self]:
        _check(table, cls, strict=True)
        return DataFrame._wrap(table, cls)


def conforms[P: SchemaLike](df: DataFrame[Any], proto: type[P]) -> DataFrame[P]:
    """Runtime-check that df has at least proto's columns; view it as DataFrame[P]."""
    _check(df, proto, strict=False)
    return DataFrame._wrap(df, proto)


class Into[S](Protocol):
    """Contravariant view of a DataFrame: `DataFrame[A]` is an `Into[O]` iff O <: A.

    Lets a signature say "O must be a subtype of the input schema" (`O: (S & X)`
    emulation) using one TypeVar: `def f[O: X](df: Into[O], out: type[O])`.
    """

    def __tacit_type_is_invariant__(self, x: S, /) -> object: ...
    def to_table(self) -> ir.Table: ...


def join[O: SchemaLike](
    left: Into[O],
    right: Into[O],
    out: type[O],
    predicates: str | Sequence[str] = (),
    *,
    how: Literal["inner", "left", "right", "outer"] = "inner",
) -> DataFrame[O]:
    """Typed join: `out` must subclass BOTH input schemas (checked statically via
    Into's contravariance and at runtime), and the result is cast to `out`."""
    for side in (left, right):
        schema = getattr(side, "_tacit_schema")
        if not issubclass(out, schema):
            raise TypeError(f"{out.__name__} must subclass {schema.__name__}")
    result = left.to_table().join(right.to_table(), predicates, how=how)
    _check(result, out, strict=True)
    return DataFrame._wrap(result, out)
