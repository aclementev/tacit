"""T2 on narwhals: `DataFrame[S]` is a narwhals (stable.v2) LazyFrame subclass; `S` is a column namespace.

Runtime notes
- narwhals builds every result with `self.__class__(compliant, level=...)` (private `_with_compliant`).
  We override it to return a *plain* v2 LazyFrame, and re-wrap only the schema-preserving methods.
  Private narwhals API used: `_with_compliant`, `_compliant_frame`, `_level` (3 names).
- Column expressions are unbound in narwhals (`nw.col("x")`), so `Orders.amount` and `df.c.amount`
  are the same runtime value. `.c` exists for static typing of generic `S`.
"""

from __future__ import annotations

import inspect
import types
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field as dc_field
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, ClassVar, Generic, Literal, Protocol, Self, TypeVar, Union, dataclass_transform, get_args, get_origin, get_type_hints

import narwhals.stable.v2 as nw
from narwhals.group_by import LazyGroupBy

from ._column import Column
from ._validate import Issue, ValidationError, fused_validate

if TYPE_CHECKING:
    from ._lazy_api import LazyFrameAPI as _Base
else:
    _Base = nw.LazyFrame

S_co = TypeVar("S_co", bound="Schema", covariant=True)
Extra = Literal["ignore", "forbid"]

# ------------------------------------------------------------------ fields
_FAMILY: dict[type, tuple[str, Any]] = {
    int: ("integer", nw.Int64),
    float: ("float", nw.Float64),
    str: ("string", nw.String),
    bool: ("boolean", nw.Boolean),
    date: ("date", nw.Date),
    datetime: ("datetime", nw.Datetime),
    Decimal: ("decimal", nw.Decimal),
}


def family_of(dtype: Any) -> str:
    if dtype.is_integer():
        return "integer"
    if dtype.is_float():
        return "float"
    if dtype.is_decimal():
        return "decimal"
    for name, cls in (("string", nw.String), ("boolean", nw.Boolean), ("date", nw.Date), ("datetime", nw.Datetime)):
        if dtype == cls or isinstance(dtype, cls):
            return name
    return str(dtype)


@dataclass
class FieldSpec:
    attr: str
    name: str
    py: type
    nullable: bool
    family: str
    target: Any
    ge: float | None = None
    le: float | None = None
    gt: float | None = None
    lt: float | None = None
    isin: list[Any] | None = None
    pattern: str | None = None
    length: int | None = None
    unique: bool = False
    checks: list[Any] = dc_field(default_factory=list)  # pandera Check objects (narwhals builtins)


@dataclass
class FieldInfo:
    name: str | None = None
    kw: dict[str, Any] = dc_field(default_factory=dict)


def field(*, name: str | None = None, ge: float | None = None, le: float | None = None, gt: float | None = None,
          lt: float | None = None, isin: list[Any] | None = None, pattern: str | None = None, length: int | None = None,
          unique: bool = False, checks: list[Any] | None = None) -> Any:
    kw = {k: v for k, v in dict(ge=ge, le=le, gt=gt, lt=lt, isin=isin, pattern=pattern, length=length, unique=unique, checks=checks or []).items() if v is not None}
    return FieldInfo(name=name, kw=kw)


def _resolve(attr: str, hint: Any, info: Any, owner: str) -> FieldSpec:
    if get_origin(hint) is not Column:
        raise TypeError(f"{owner}.{attr}: annotate columns as Column[T], got {hint!r}")
    (t,) = get_args(hint)
    nullable = False
    if get_origin(t) in (Union, types.UnionType):
        parts = [a for a in get_args(t) if a is not type(None)]
        nullable = len(parts) < len(get_args(t))
        (t,) = parts
    fam, target = _FAMILY[t]
    fi = info if isinstance(info, FieldInfo) else FieldInfo()
    return FieldSpec(attr=attr, name=fi.name or attr, py=t, nullable=nullable, family=fam, target=target, **fi.kw)


class _Col:
    __slots__ = ("spec",)

    def __init__(self, spec: FieldSpec) -> None:
        self.spec = spec

    def __get__(self, obj: Any, owner: type) -> Any:
        # class access (Orders.amount) -> the column name; instance access (df.c.amount) -> nw.col
        return self.spec.name if obj is None else nw.col(self.spec.name)


class Into[S](Protocol):
    def __tacit_into__(self, x: S, /) -> object: ...


# ------------------------------------------------------------------ schema
@dataclass_transform(kw_only_default=True, field_specifiers=(field,))
class Schema:
    __tacit_fields__: ClassVar[dict[str, FieldSpec]] = {}

    def __init_subclass__(cls, **kw: Any) -> None:
        super().__init_subclass__(**kw)
        hints = get_type_hints(cls)
        order: list[str] = []

        def walk(c: type) -> None:
            for b in c.__bases__:
                if issubclass(b, Schema) and b is not Schema:
                    walk(b)
            for n in inspect.get_annotations(c):
                if n not in order and not n.startswith("_"):
                    order.append(n)

        walk(cls)
        fields: dict[str, FieldSpec] = {}
        for n in order:
            if n in _RESERVED:
                raise TypeError(f"{cls.__name__}.{n}: '{n}' is reserved; use field(name={n!r}) on another attribute name")
            raw = next((c.__dict__[n] for c in cls.__mro__ if c is not Schema and n in c.__dict__), None)
            spec = raw.spec if isinstance(raw, _Col) else _resolve(n, hints[n], raw, cls.__name__)
            fields[n] = spec
            setattr(cls, n, _Col(spec))
        cls.__tacit_fields__ = fields

    def __init__(self, **columns: Any) -> None:  # typed (synthesized) signature; use .build(frame, ...)
        raise TypeError(f"use {type(self).__name__}.build(frame, ...)")

    @classmethod
    def _bind(cls) -> Self:
        return object.__new__(cls)

    # ---- boundaries
    @classmethod
    def conform(cls, frame: Any, *, extra: Extra = "ignore") -> DataFrame[Self]:
        """Structural only (names + dtype families), no query. NOTE: narwhals schemas carry no
        nullability, so non-null declarations are NOT verified here (ibis-based conform could)."""
        lf = _lazy(frame)
        lf = cls._structural(lf, f"{cls.__name__}.conform", extra, coerce=False)
        return DataFrame._wrap(lf, cls)

    @classmethod
    def parse(cls, frame: Any, *, extra: Extra = "ignore", coerce: bool = False) -> DataFrame[Self]:
        """Structural check, optional coercion, then all data checks in ONE query (one Spark job)."""
        lf = cls._structural(_lazy(frame), f"{cls.__name__}.parse", extra, coerce=coerce)
        issues = fused_validate(lf, cls.__tacit_fields__)
        if issues:
            raise ValidationError(cls.__name__, f"{cls.__name__}.parse", issues)
        return DataFrame._wrap(lf, cls)

    @classmethod
    def _structural(cls, lf: nw.LazyFrame[Any], ctx: str, extra: Extra, *, coerce: bool) -> nw.LazyFrame[Any]:
        schema = lf.collect_schema()
        fields = cls.__tacit_fields__
        issues: list[Issue] = [Issue("missing_column", f.name) for f in fields.values() if f.name not in schema]
        if extra == "forbid":
            names = {f.name for f in fields.values()}
            issues += [Issue("extra_column", c) for c in schema if c not in names]
        casts: list[nw.Expr] = []
        for f in fields.values():
            if f.name not in schema:
                continue
            fam = family_of(schema[f.name])
            if fam == f.family:
                continue
            if coerce or (f.family == "float" and fam == "integer"):  # widen int -> float silently
                casts.append(nw.col(f.name).cast(f.target))
            else:
                issues.append(Issue("dtype", f.name, f"expected {f.family}, got {schema[f.name]}"))
        if issues:
            raise ValidationError(cls.__name__, ctx, issues)
        if casts:
            lf = lf.with_columns(*casts)
        return lf.select(*[f.name for f in fields.values()])

    # ---- construction
    @classmethod
    def build[**P, S: Schema](cls: Callable[P, S], frame: Any, /, *args: P.args, **kwargs: P.kwargs) -> DataFrame[S]:  # type: ignore[misc]
        """Checked projection: `Out.build(df, a=..., b=...)`; with `df.group_by(keys)` it aggregates.
        Key columns are passed as their plain column (`status=o.c.status`)."""
        sc: Any = cls
        fields = sc.__tacit_fields__
        ctx = f"{sc.__name__}.build"
        issues = [Issue("missing_column", a) for a in fields if a not in kwargs]
        issues += [Issue("extra_column", k) for k in kwargs if k not in fields]
        if issues or args:
            raise ValidationError(sc.__name__, ctx, issues or [Issue("positional")])
        exprs = {fields[a].name: (v if isinstance(v, nw.Expr) else nw.lit(v)) for a, v in kwargs.items()}
        if isinstance(frame, LazyGroupBy):
            keys = set(frame._keys)  # private: LazyGroupBy._keys (the key column names)
            out = frame.agg(**{k: e for k, e in exprs.items() if k not in keys})
            delta = None
        else:
            out = frame.select(**exprs)
            delta = exprs
        lf = sc._structural(out, ctx, "forbid", coerce=False)
        df = DataFrame._wrap(lf, sc)
        object.__setattr__(df, "_exprs", delta)
        return df

    @classmethod
    def extend(cls, base: Into[Self], delta: Into[Self], /, *more: Into[Self]) -> DataFrame[Self]:
        new: dict[str, nw.Expr] = {}
        for d in (delta, *more):
            if not isinstance(d, DataFrame) or d._exprs is None:
                raise TypeError("extend: deltas must be built with Delta.build(base, ...) (not aggregated)")
            new.update(d._exprs)
        assert isinstance(base, nw.LazyFrame)
        lf = base.with_columns(**new)
        return DataFrame._wrap(cls._structural(lf, f"{cls.__name__}.extend", "ignore", coerce=False), cls)


_RESERVED = frozenset(n for n in vars(Schema) if not n.startswith("_"))


def _lazy(frame: Any) -> nw.LazyFrame[Any]:
    if isinstance(frame, nw.LazyFrame):
        return nw.LazyFrame(frame._compliant_frame, level=frame._level) if isinstance(frame, DataFrame) else frame
    f = nw.from_native(frame)
    return f.lazy() if isinstance(f, nw.DataFrame) else f


# ------------------------------------------------------------------ frame
class DataFrame(_Base, Generic[S_co]):
    """A narwhals LazyFrame (runtime subclass) tagged with its schema; typed columns via `.c`."""

    if TYPE_CHECKING:
        _schema: type[Schema]
        _exprs: dict[str, nw.Expr] | None

        def __tacit_into__(self, x: S_co, /) -> object: ...  # type: ignore[misc]

    @classmethod
    def _wrap(cls, lf: nw.LazyFrame[Any], schema: type[Any]) -> DataFrame[Any]:
        obj = cls(lf._compliant_frame, level=lf._level)
        object.__setattr__(obj, "_schema", schema)
        object.__setattr__(obj, "_exprs", None)
        return obj

    def _with_compliant(self, df: Any) -> Any:  # every narwhals op -> plain LazyFrame
        return nw.LazyFrame(df, level=self._level)

    @property
    def c(self) -> S_co:
        return self._schema._bind()  # type: ignore[return-value]

    def _re(self, lf: Any) -> Self:
        return DataFrame._wrap(lf, self._schema)  # type: ignore[return-value]

    if not TYPE_CHECKING:  # statically these keep narwhals' own signatures (returning Self)
        # schema-preserving methods keep DataFrame[S]
        def filter(self, *a: Any, **k: Any) -> Self:  # type: ignore[override]
            return self._re(super().filter(*a, **k))

        def sort(self, *a: Any, **k: Any) -> Self:  # type: ignore[override]
            return self._re(super().sort(*a, **k))

        def head(self, n: int = 5) -> Self:  # type: ignore[override]
            return self._re(super().head(n))

        def tail(self, n: int = 5) -> Self:  # type: ignore[override]
            return self._re(super().tail(n))

        def unique(self, *a: Any, **k: Any) -> Self:  # type: ignore[override]
            return self._re(super().unique(*a, **k))

        def drop_nulls(self, *a: Any, **k: Any) -> Self:  # type: ignore[override]
            return self._re(super().drop_nulls(*a, **k))

        def top_k(self, *a: Any, **k: Any) -> Self:  # type: ignore[override]
            return self._re(super().top_k(*a, **k))


    def __repr__(self) -> str:
        return f"DataFrame[{self._schema.__name__}]({self.implementation})"


_ = Mapping
