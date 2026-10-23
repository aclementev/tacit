"""T2 runtime: `DataFrame[S]` is an `ir.Table` subclass; `S` is a column-namespace class."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Any, ClassVar, Generic, Literal, Protocol, Self, TypeVar, dataclass_transform, get_type_hints

import ibis
import ibis.expr.types as ir
from ibis import Deferred
from ibis.common.exceptions import IbisError

from tacit_thin._column import Column
from tacit_thin._errors import Issue, ValidationError
from tacit_thin._fields import FieldInfo, FieldSpec, field, resolve_field
from tacit_thin._ibis_api import TableAPI as _TableBase
from tacit_thin._validate import Extra, parse_table, project, structural_issues

S_co = TypeVar("S_co", bound="Schema", covariant=True)


class Into[S](Protocol):
    """`DataFrame[X]` is an `Into[O]` iff `O` subclasses `X` (contravariant in the method parameter)."""

    def __tacit_into__(self, x: S, /) -> object: ...


class _Col:
    __slots__ = ("spec",)

    def __init__(self, spec: FieldSpec) -> None:
        self.spec = spec

    def __get__(self, obj: Schema | None, owner: type) -> Any:
        if obj is None:
            return ibis._[self.spec.name]
        return ir.Table.__getitem__(obj._df, self.spec.name)


def _plain(t: Any) -> ir.Table:
    return t.op().to_expr()


def _relations(e: Any) -> frozenset[Any]:
    return frozenset(e.op().relations)


@dataclass_transform(kw_only_default=True, field_specifiers=(field,))
class Schema:
    """Column namespace. Instances are bound to a table: `df.c` is a `S` bound to `df`."""

    __slots__ = ("_df",)
    __tacit_fields__: ClassVar[dict[str, FieldSpec]] = {}
    if TYPE_CHECKING:
        _df: ir.Table

    def __init_subclass__(cls, **kw: Any) -> None:
        super().__init_subclass__(**kw)
        hints = get_type_hints(cls, include_extras=True)
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
                raise TypeError(f"{cls.__name__}.{n}: '{n}' is a Schema classmethod name; use tc.field(name={n!r})")
            raw = next((c.__dict__[n] for c in cls.__mro__ if c is not Schema and n in c.__dict__), None)
            info = raw.spec if isinstance(raw, _Col) else raw
            spec = info if isinstance(info, FieldSpec) else resolve_field(n, hints[n], info, cls.__name__)
            fields[n] = spec
            setattr(cls, n, _Col(spec))
        cls.__tacit_fields__ = fields

    def __init__(self, **columns: Any) -> None:  # the typed (synthesized) signature; use .build(...)
        raise TypeError(f"use {type(self).__name__}.build(...) to construct a DataFrame[{type(self).__name__}]")

    @classmethod
    def _bind(cls, df: ir.Table) -> Self:
        obj = object.__new__(cls)
        object.__setattr__(obj, "_df", df)
        return obj

    @classmethod
    def build[**P, S: Schema](cls: Callable[P, S], *args: P.args, **kwargs: P.kwargs) -> DataFrame[S]:  # type: ignore[misc]
        """Checked projection / implicit GROUP BY: `Out.build(a=df.c.x, n=df.c.y.count())`."""
        sc: Any = cls
        if args:
            raise TypeError("build() is keyword-only")
        table, exprs = sc._construct(kwargs)
        df = DataFrame._wrap(table, sc)
        object.__setattr__(df, "_exprs", exprs)
        return df

    @classmethod
    def _construct(cls, columns: Mapping[str, Any]) -> tuple[ir.Table, dict[str, ir.Value] | None]:
        fields = cls.__tacit_fields__
        ctx = f"{cls.__name__}.build"
        issues = [Issue("missing_column", a) for a in fields if a not in columns]
        issues += [Issue("extra_column", k) for k in columns if k not in fields]
        if issues:
            raise ValidationError(cls.__name__, ctx, issues)
        exprs: dict[str, ir.Value] = {}
        deferred: dict[str, Deferred] = {}
        for a, v in columns.items():
            if isinstance(v, Deferred):
                deferred[a] = v
            elif isinstance(v, ir.Value):
                exprs[a] = v
            else:
                exprs[a] = ibis.literal(v, type=fields[a].dtype)
        rels = frozenset().union(*(_relations(e) for e in exprs.values()))
        if len(rels) != 1:
            raise ValidationError(cls.__name__, ctx, [Issue("relation", detail=f"{len(rels)} relations")])
        src: ir.Table = next(iter(rels)).to_expr()
        if deferred:
            exprs.update(dict(zip(deferred, src.bind(**deferred), strict=True)))
        aggs = {a: e for a, e in exprs.items() if isinstance(e, ir.Scalar) and _relations(e)}
        keys = {a: e for a, e in exprs.items() if a not in aggs and isinstance(e, ir.Column)}
        consts = {a: e for a, e in exprs.items() if a not in aggs and a not in keys}
        n = {a: fields[a].name for a in exprs}
        try:
            if aggs:
                g = src.group_by(**{n[a]: e for a, e in keys.items()}) if keys else None
                m = {n[a]: e for a, e in aggs.items()}
                table = g.aggregate(**m) if g is not None else src.aggregate(**m)
                if consts:
                    table = table.mutate(**{n[a]: e for a, e in consts.items()})
                delta = None
            else:
                table = src.select(**{n[a]: e for a, e in exprs.items()})
                delta = {n[a]: e for a, e in exprs.items()}
        except IbisError as exc:
            raise ValidationError(cls.__name__, ctx, [Issue("relation", detail=str(exc))]) from None
        return cls._checked(table, ctx, "forbid"), delta

    @classmethod
    def _checked(cls, table: ir.Table, ctx: str, extra: Extra) -> ir.Table:
        fields = cls.__tacit_fields__
        schema = table.schema()
        widen: dict[str, Any] = {}
        found: list[Issue] = []
        for i in structural_issues(fields, schema, extra=extra):
            spec = next((f for f in fields.values() if f.name == i.column), None)
            target = spec.widening_target(schema[spec.name]) if (spec and i.code == "dtype") else None
            if target is not None and spec is not None:
                widen[spec.name] = target
            else:
                found.append(i)
        if found:
            raise ValidationError(cls.__name__, ctx, found)
        if widen:
            table = table.cast(widen)
        return project(fields, table)

    @classmethod
    def conform(cls, table: ir.Table | _TableBase, *, extra: Extra = "ignore") -> DataFrame[Self]:
        return DataFrame._wrap(cls._checked(_plain(table), f"{cls.__name__}.conform", extra), cls)

    @classmethod
    def parse(cls, table: ir.Table | _TableBase, *, extra: Extra = "ignore") -> DataFrame[Self]:
        out = parse_table(cls.__name__, cls.__tacit_fields__, _plain(table), extra=extra, context=f"{cls.__name__}.parse")
        return DataFrame._wrap(out, cls)

    @classmethod
    def extend(cls, base: Into[Self], delta: Into[Self], /, *more: Into[Self]) -> DataFrame[Self]:
        """base's columns + the new columns of `Delta.build(...)` frames derived from base."""
        assert isinstance(base, DataFrame)
        new: dict[str, ir.Value] = {}
        for d in (delta, *more):
            if not isinstance(d, DataFrame) or d._exprs is None:
                raise TypeError("extend: deltas must be built with Delta.build(...) (not aggregated)")
            new.update(d._exprs)
        return DataFrame._wrap(cls._checked(_plain(base).mutate(**new), f"{cls.__name__}.extend", "ignore"), cls)


_RESERVED = frozenset(n for n in vars(Schema) if not n.startswith("_"))


class DataFrame(_TableBase, Generic[S_co]):
    """An ibis Table (runtime subclass) tagged with its schema; typed columns via `.c`."""

    __slots__ = ("_exprs", "_schema")
    if TYPE_CHECKING:
        _schema: type[Schema]
        _exprs: dict[str, ir.Value] | None

        def __tacit_into__(self, x: S_co, /) -> object: ...  # type: ignore[misc]

    @classmethod
    def _wrap(cls, table: ir.Table, schema: type[Any]) -> DataFrame[Any]:
        obj = object.__new__(cls)
        object.__setattr__(obj, "_arg", table.op())
        object.__setattr__(obj, "_schema", schema)
        object.__setattr__(obj, "_exprs", None)
        return obj

    def __reduce__(self) -> Any:
        return (_rewrap, (self.op(), self._schema))

    @property
    def c(self) -> S_co:
        """Typed column namespace: `df.c.amount` is `Column[float]`."""
        return self._schema._bind(self)  # type: ignore[return-value]

    def _re(self, t: ir.Table) -> Self:
        return DataFrame._wrap(t, self._schema)  # type: ignore[return-value]

    def filter(self, *predicates: Column[bool | None] | ir.BooleanValue | Deferred) -> Self:  # type: ignore[override]
        return self._re(_plain(self).filter(*predicates))  # type: ignore[arg-type]

    def order_by(self, *keys: Column[Any] | ir.Column | Deferred | str) -> Self:  # type: ignore[override]
        return self._re(_plain(self).order_by(*keys))  # type: ignore[arg-type]

    def limit(self, n: int | None, /, *, offset: int = 0) -> Self:  # type: ignore[override]
        return self._re(_plain(self).limit(n, offset=offset))

    def head(self, n: int = 5, /) -> Self:  # type: ignore[override]
        return self._re(_plain(self).head(n))

    def distinct(  # type: ignore[override]
        self, *, on: Column[Any] | str | Sequence[Column[Any] | str] | None = None,
        keep: Literal["first", "last"] | None = "first",
    ) -> Self:
        if on is None:
            return self._re(_plain(self).distinct())
        keys = [on] if isinstance(on, ir.Value | str) else list(on)
        return self._re(_plain(self).distinct(on=[k if isinstance(k, str) else k.get_name() for k in keys], keep=keep))  # type: ignore[attr-defined]

    def cache(self) -> Self:  # type: ignore[override]
        return self._re(_plain(self).cache())


def _rewrap(op: Any, schema: type[Any]) -> DataFrame[Any]:
    return DataFrame._wrap(op.to_expr(), schema)
