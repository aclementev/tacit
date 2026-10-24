"""Field metadata: constraints, physical dtype overrides, column-name overrides.

Two spellings carry the same metadata (both tested in tests/typecheck):

    amount: Column[float] = tc.field(ge=0, description="gross amount")
    amount: Annotated[Column[float], tc.ge(0)]
"""

from __future__ import annotations

import types
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, time
from decimal import Decimal
from typing import Annotated, Any, Union, get_args, get_origin

import ibis.expr.datatypes as dt

from ._column import Column


@dataclass(frozen=True)
class Constraint:
    """A data check. `kind` names it in errors: `ge(0)`, `isin(['a', 'b'])`, ..."""

    kind: str
    value: Any

    def __repr__(self) -> str:
        if self.kind == "check":
            return f"check({self.value[1]})"
        return f"{self.kind}({self.value!r})"


def ge(v: float | Decimal | date) -> Constraint:
    return Constraint("ge", v)


def gt(v: float | Decimal | date) -> Constraint:
    return Constraint("gt", v)


def le(v: float | Decimal | date) -> Constraint:
    return Constraint("le", v)


def lt(v: float | Decimal | date) -> Constraint:
    return Constraint("lt", v)


def between(lower: float | Decimal | date, upper: float | Decimal | date) -> Constraint:
    return Constraint("between", (lower, upper))


def isin(values: Sequence[object]) -> Constraint:
    return Constraint("isin", list(values))


def notin(values: Sequence[object]) -> Constraint:
    return Constraint("notin", list(values))


def str_matches(regex: str) -> Constraint:
    """Whole-value regex match (anchored at the start, like pandera's str_matches)."""
    return Constraint("str_matches", regex if regex.startswith("^") else "^" + regex)


def check(fn: Callable[[Column[Any]], Column[bool]], /, name: str | None = None) -> Constraint:
    """Custom check: a function from the column to a boolean column (TRUE = valid, NULL = ignored).

    Typed `Column[Any]` -> `Column[bool]` (not generic): an unsolved TypeVar breaks lambdas
    (`tc.check(lambda c: c > 0)` failed on pyright and mypy).

        def positive(c: Column[float]) -> Column[bool]:
            return c > 0
        amount: Column[float] = tc.field(checks=[tc.check(positive)])
    """
    return Constraint("check", (fn, name or getattr(fn, "__name__", "check")))


def pattern(regex: str) -> Constraint:
    return Constraint("pattern", regex)


def length(exact: int | None = None, *, min: int | None = None, max: int | None = None) -> Constraint:
    return Constraint("length", (exact, min, max))


def unique() -> Constraint:
    return Constraint("unique", True)


@dataclass(frozen=True)
class DType:
    """Physical dtype override, e.g. `tc.dtype("decimal(12, 2)")` / `"float32"` / `"timestamp('UTC')"`."""

    dtype: dt.DataType


def dtype(spec: str | dt.DataType) -> DType:
    return DType(dt.dtype(spec))


@dataclass(frozen=True)
class FieldInfo:
    constraints: tuple[Constraint, ...] = ()
    dtype: dt.DataType | None = None
    name: str | None = None  # physical column name if it differs from the attribute
    description: str | None = None

    def merge(self, other: FieldInfo) -> FieldInfo:
        return replace(
            self,
            constraints=self.constraints + other.constraints,
            dtype=other.dtype or self.dtype,
            name=other.name or self.name,
            description=other.description or self.description,
        )


def field(
    *,
    ge: float | Decimal | date | None = None,
    gt: float | Decimal | date | None = None,
    le: float | Decimal | date | None = None,
    lt: float | Decimal | date | None = None,
    isin: Sequence[object] | None = None,
    pattern: str | None = None,
    length: int | None = None,
    min_length: int | None = None,
    max_length: int | None = None,
    unique: bool = False,
    checks: Sequence[Constraint] = (),
    dtype: str | dt.DataType | None = None,
    name: str | None = None,
    description: str | None = None,
) -> Any:
    """Field specifier (listed in Frame's `dataclass_transform(field_specifiers=...)`).

    Has no `default` parameter on purpose: every column stays a required
    constructor argument. Returns `Any` statically so `x: Column[float] = field(...)`
    type-checks; at runtime the Frame replaces it with a column descriptor.
    """
    cs: list[Constraint] = []
    for kind, v in (("ge", ge), ("gt", gt), ("le", le), ("lt", lt)):
        if v is not None:
            cs.append(Constraint(kind, v))
    if isin is not None:
        cs.append(Constraint("isin", list(isin)))
    if pattern is not None:
        cs.append(Constraint("pattern", pattern))
    if length is not None or min_length is not None or max_length is not None:
        cs.append(Constraint("length", (length, min_length, max_length)))
    if unique:
        cs.append(Constraint("unique", True))
    cs.extend(checks)
    return FieldInfo(tuple(cs), dt.dtype(dtype) if dtype is not None else None, name, description)


# ---------------------------------------------------------------------------
# Python value type -> ibis dtype

_DEFAULT_DTYPES: dict[type, dt.DataType] = {
    bool: dt.boolean,
    int: dt.int64,
    float: dt.float64,
    Decimal: dt.Decimal(),  # unparameterized: any precision/scale is accepted
    str: dt.string,
    datetime: dt.timestamp,
    date: dt.date,
    time: dt.time,
    bytes: dt.binary,
}


def _family(d: dt.DataType) -> str:
    if d.is_boolean():
        return "boolean"
    if d.is_integer():
        return "integer"
    if d.is_floating():
        return "floating"
    if d.is_decimal():
        return "decimal"
    if d.is_string():
        return "string"
    if d.is_timestamp():
        return "timestamp"
    if d.is_date():
        return "date"
    if d.is_time():
        return "time"
    if d.is_binary():
        return "binary"
    return d.name.lower()


@dataclass(frozen=True)
class FieldSpec:
    """Resolved column: attribute name, physical name, value type, dtype, nullability, checks."""

    attr: str
    name: str
    pytype: Any
    dtype: dt.DataType | None  # None => any dtype (Column[Any])
    explicit_dtype: bool
    nullable: bool
    constraints: tuple[Constraint, ...]
    description: str | None

    def accepts(self, actual: dt.DataType) -> bool:
        """Structural compatibility, ignoring nullability (a NOT NULL column satisfies anything).

        Without an explicit dtype the check is per family (`Column[int]` accepts
        int8..int64); with `tc.field(dtype=...)` parameters must match exactly.
        """
        if self.dtype is None:
            return True
        want = self.dtype.copy(nullable=True)
        have = actual.copy(nullable=True)
        if want.is_timestamp() and have.is_timestamp():
            # duckdb reports timestamp(6); only compare what the declaration pins down (E4 bug).
            if want.timezone is not None and want.timezone != have.timezone:  # type: ignore[attr-defined]
                return False
            return want.scale is None or want.scale == have.scale  # type: ignore[attr-defined]
        if self.explicit_dtype:
            return want == have
        if _family(want) != _family(have):
            return False
        return True

    def widening_target(self, actual: dt.DataType) -> dt.DataType | None:
        """Lossless cast applied by construction (int -> float, int32 -> int64, ...), else None."""
        if self.dtype is None:
            return None
        fam_w, fam_h = _family(self.dtype), _family(actual)
        if fam_h == "integer" and fam_w in ("floating", "decimal"):
            return self.dtype
        if self.explicit_dtype and fam_w == fam_h and fam_w in ("integer", "floating"):
            want_bits = getattr(self.dtype, "nbytes", 0)
            if getattr(actual, "nbytes", 0) <= want_bits:
                return self.dtype
        return None

    def physical(self) -> dt.DataType:
        """dtype used when parse() has to coerce a column."""
        if self.dtype is None:
            raise TypeError("no dtype")
        if self.dtype.is_decimal() and self.dtype.precision is None:  # type: ignore[attr-defined]
            return dt.Decimal(38, 9)
        return self.dtype


def _strip_optional(tp: Any) -> tuple[Any, bool]:
    origin = get_origin(tp)
    if origin is Union or origin is types.UnionType:
        args = [a for a in get_args(tp) if a is not type(None)]
        nullable = len(args) != len(get_args(tp))
        if len(args) != 1:
            raise TypeError(f"unsupported column value type {tp!r} (unions other than `T | None`)")
        return args[0], nullable
    return tp, False


def resolve_field(attr: str, hint: Any, default: Any, owner: str) -> FieldSpec:
    info = FieldInfo()
    if get_origin(hint) is Annotated:
        base, *meta = get_args(hint)
        for m in meta:
            if isinstance(m, Constraint):
                info = info.merge(FieldInfo(constraints=(m,)))
            elif isinstance(m, DType):
                info = info.merge(FieldInfo(dtype=m.dtype))
            elif isinstance(m, FieldInfo):
                info = info.merge(m)
        hint = base
    if isinstance(default, FieldInfo):
        info = info.merge(default)
    elif default is not None and not isinstance(default, type(None)):
        raise TypeError(f"{owner}.{attr}: columns cannot have defaults; use tc.field(...) for metadata")
    if get_origin(hint) is not Column:
        raise TypeError(
            f"{owner}.{attr}: annotate frame columns as Column[T] (e.g. Column[float], Column[str | None]); got {hint!r}"
        )
    (value_type,) = get_args(hint) or (Any,)
    inner, nullable = _strip_optional(value_type)
    if inner is Any:
        base_dtype = None
    elif inner in _DEFAULT_DTYPES:
        base_dtype = _DEFAULT_DTYPES[inner]
    else:
        raise TypeError(f"{owner}.{attr}: unsupported column value type {inner!r}")
    explicit = info.dtype is not None
    if info.dtype is not None and base_dtype is not None:
        if _family(info.dtype) != _family(base_dtype) and not (
            inner is float and info.dtype.is_decimal()
        ):
            raise TypeError(f"{owner}.{attr}: dtype {info.dtype} does not match Column[{inner.__name__}]")
    return FieldSpec(
        attr=attr,
        name=info.name or attr,
        pytype=value_type,
        dtype=info.dtype or base_dtype,
        explicit_dtype=explicit,
        nullable=nullable,
        constraints=info.constraints,
        description=info.description,
    )
