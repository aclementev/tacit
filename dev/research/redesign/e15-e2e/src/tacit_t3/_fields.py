"""Field metadata: constraints (pandera checks), dtype overrides, column-name overrides.

    amount: Column[float] = tacit.field(ge=0, description="gross, EUR")
    email: Column[str] = tacit.field(checks=[pa.Check.str_contains("@")])   # any pandera Check

Constraints are kept as tacit `Constraint`s and turned into pandera `Check`s only
when data is validated, so `import tacit` does not import pandera (~0.7-2 s).
"""

from __future__ import annotations

import types
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Union, get_args, get_origin

import ibis.expr.datatypes as dt

from ._column import Column

if TYPE_CHECKING:
    from pandera.api.checks import Check


@dataclass(frozen=True)
class Constraint:
    """A tacit-spelled data check; `to_pandera()` gives the equivalent pandera Check."""

    kind: str
    value: Any

    def __repr__(self) -> str:
        return f"{self.kind}({self.value!r})"

    def to_pandera(self) -> Check:
        from pandera.api.checks import Check

        k, v = self.kind, self.value
        if k == "length":
            lo, hi = v
            return Check.str_length(lo, hi)
        if k == "pattern":
            return Check.str_contains(v)
        return {"ge": Check.ge, "gt": Check.gt, "le": Check.le, "lt": Check.lt,
                "isin": Check.isin, "notin": Check.notin}[k](v)


def field(
    *,
    ge: float | Decimal | date | None = None,
    gt: float | Decimal | date | None = None,
    le: float | Decimal | date | None = None,
    lt: float | Decimal | date | None = None,
    isin: Sequence[object] | None = None,
    notin: Sequence[object] | None = None,
    pattern: str | None = None,
    min_length: int | None = None,
    max_length: int | None = None,
    unique: bool = False,
    checks: Sequence[Check] = (),
    dtype: str | dt.DataType | None = None,
    name: str | None = None,
    description: str | None = None,
) -> Any:
    """Field specifier (listed in Schema's `dataclass_transform(field_specifiers=...)`).

    No `default`: every column stays a required `build()` argument. Returns `Any`
    statically so `x: Column[float] = field(...)` type-checks.
    """
    cs: list[Constraint] = []
    for kind, v in (("ge", ge), ("gt", gt), ("le", le), ("lt", lt), ("pattern", pattern)):
        if v is not None:
            cs.append(Constraint(kind, v))
    if isin is not None:
        cs.append(Constraint("isin", list(isin)))
    if notin is not None:
        cs.append(Constraint("notin", list(notin)))
    if min_length is not None or max_length is not None:
        cs.append(Constraint("length", (min_length, max_length)))
    return FieldInfo(tuple(cs), tuple(checks), unique, dt.dtype(dtype) if dtype is not None else None, name, description)


@dataclass(frozen=True)
class FieldInfo:
    constraints: tuple[Constraint, ...] = ()
    checks: tuple[Any, ...] = ()  # pandera Check objects, passed through
    unique: bool = False
    dtype: dt.DataType | None = None
    name: str | None = None
    description: str | None = None


_DEFAULT_DTYPES: dict[type, dt.DataType] = {
    bool: dt.boolean, int: dt.int64, float: dt.float64, Decimal: dt.Decimal(), str: dt.string,
    datetime: dt.timestamp, date: dt.date, time: dt.time, bytes: dt.binary,
}


def _family(d: dt.DataType) -> str:
    for fam in ("boolean", "integer", "floating", "decimal", "string", "timestamp", "date", "time", "binary"):
        if getattr(d, f"is_{fam}")():
            return fam
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
    checks: tuple[Any, ...]
    unique: bool
    description: str | None

    def accepts(self, actual: dt.DataType) -> bool:
        """Structural compatibility, ignoring nullability (per family unless dtype= pins it)."""
        if self.dtype is None:
            return True
        want, have = self.dtype.copy(nullable=True), actual.copy(nullable=True)
        if want.is_timestamp() and have.is_timestamp():  # duckdb reports timestamp(6) (E4 bug)
            if want.timezone is not None and want.timezone != have.timezone:  # type: ignore[attr-defined]
                return False
            return want.scale is None or want.scale == have.scale  # type: ignore[attr-defined]
        return want == have if self.explicit_dtype else _family(want) == _family(have)

    def widening_target(self, actual: dt.DataType) -> dt.DataType | None:
        """Lossless cast applied by construction (int -> float, int32 -> int64, ...), else None."""
        if self.dtype is None:
            return None
        fam_w, fam_h = _family(self.dtype), _family(actual)
        if fam_h == "integer" and fam_w in ("floating", "decimal"):
            return self.dtype
        if self.explicit_dtype and fam_w == fam_h and fam_w in ("integer", "floating"):
            if getattr(actual, "nbytes", 0) <= getattr(self.dtype, "nbytes", 0):
                return self.dtype
        return None

    def physical(self) -> dt.DataType:
        """dtype used when parse() has to coerce a column."""
        if self.dtype is None:
            raise TypeError("no dtype")
        if self.dtype.is_decimal() and self.dtype.precision is None:  # type: ignore[attr-defined]
            return dt.Decimal(38, 9)
        return self.dtype

    def describe(self) -> str:
        t = getattr(self.pytype, "__name__", None) or str(self.pytype).replace("datetime.", "")
        extra = [repr(c) for c in self.constraints] + [getattr(c, "error", None) or str(c) for c in self.checks]
        extra += ["unique"] if self.unique else []
        extra += [f"name={self.name!r}"] if self.name != self.attr else []
        out = f"{self.attr}: Column[{t}]" + (f"  [{', '.join(extra)}]" if extra else "")
        return out + (f"  # {self.description}" if self.description else "")


def resolve_field(attr: str, hint: Any, default: Any, owner: str) -> FieldSpec:
    info = default if isinstance(default, FieldInfo) else FieldInfo()
    if default is not None and not isinstance(default, FieldInfo):
        raise TypeError(f"{owner}.{attr}: columns cannot have defaults; use tacit.field(...) for metadata")
    if get_origin(hint) is not Column:
        raise TypeError(f"{owner}.{attr}: annotate columns as Column[T] (e.g. Column[float], Column[str | None]); got {hint!r}")
    (value_type,) = get_args(hint) or (Any,)
    inner, nullable = value_type, False
    if get_origin(value_type) in (Union, types.UnionType):
        args = [a for a in get_args(value_type) if a is not type(None)]
        if len(args) != 1:
            raise TypeError(f"{owner}.{attr}: unsupported column value type {value_type!r} (only `T | None` unions)")
        inner, nullable = args[0], True
    if inner is Any:
        base_dtype = None
    elif inner in _DEFAULT_DTYPES:
        base_dtype = _DEFAULT_DTYPES[inner]
    else:
        raise TypeError(f"{owner}.{attr}: unsupported column value type {inner!r}")
    if info.dtype is not None and base_dtype is not None and _family(info.dtype) != _family(base_dtype):
        if not (inner is float and info.dtype.is_decimal()):
            raise TypeError(f"{owner}.{attr}: dtype {info.dtype} does not match Column[{inner.__name__}]")
    return FieldSpec(attr, info.name or attr, value_type, info.dtype or base_dtype, info.dtype is not None,
                     nullable, info.constraints, info.checks, info.unique, info.description)
