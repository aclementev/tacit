"""Frame: the schema class is the typed frame -- a thin `ir.Table` SUBCLASS at runtime.

Statically, `Frame`'s base is the generated clean mirror `_ibis_api.Table` (all of
ibis's Table methods, no `__getattr__`, no Unknown/Any base); at runtime it is
`ibis.expr.types.Table` itself, so a frame IS an ibis table: every ibis method works,
ibis functions accept it, and every ibis method returns a plain `ir.Table` (schema
dropped). Re-enter with a constructor, `.extend`, `.conform` or `.parse`.

    class Orders(tc.Frame):
        order_id: Column[int]
        amount: Column[float] = tc.field(ge=0)
        discount: Column[float | None]

    orders = Orders.parse(raw_table)        # coerce + validate -> Orders
    orders.mutate(x=orders.amount * 2)      # plain ibis: -> Table
    orders.amount                           # Column[float] statically, ibis column at runtime
    Net(net=orders.amount - orders.discount.fill_null(0.0))   # checked projection
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping, Sequence
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Literal,
    Protocol,
    Self,
    dataclass_transform,
    get_origin,
    get_type_hints,
)

import ibis
import ibis.expr.types as ir
from ibis import Deferred
from ibis.common.exceptions import IbisError

from ._column import Column
from ._ibis_api import TableAPI as _TableBase  # runtime: ir.Table; static: clean generated mirror
from ._errors import Issue, ValidationError
from ._fields import FieldInfo, FieldSpec, field, resolve_field
from ._validate import Extra, parse_table, project, structural_issues

if TYPE_CHECKING:
    import pandas as pd
    import polars as pl
    import pyarrow as pa


class Into[S](Protocol):
    """Contravariant view of a frame: an `X` instance is an `Into[O]` iff `O` subclasses `X`.

    `Out.extend(base: Into[Self], ...)` therefore only type-checks when `Out`
    is a subclass of `type(base)`. Generic additive steps use the same trick:
    `def add_score[O: Scored](df: Into[O], ..., out: type[O]) -> O`.
    """

    def __tacit_into__(self, x: S, /) -> object: ...


class _ColumnDescriptor:
    """Installed for every column. Instance access -> ibis column; class access -> `ibis._[name]`."""

    __slots__ = ("info", "spec")

    def __init__(self, spec: FieldSpec, info: FieldInfo | None) -> None:
        self.spec = spec
        self.info = info

    def __get__(self, obj: Frame | None, owner: type) -> Any:
        if obj is None:
            return ibis._[self.spec.name]
        names = obj._names
        return ir.Table.__getitem__(obj, names[self.spec.attr] if names else self.spec.name)

    def __set__(self, obj: Frame, value: object) -> None:
        raise AttributeError(f"frame columns are read-only ({type(obj).__name__}.{self.spec.attr})")


def _relations(e: ir.Value) -> frozenset[Any]:
    return frozenset(e.op().relations)  # type: ignore[attr-defined]


def _is_reduction(e: ir.Value) -> bool:
    return isinstance(e, ir.Scalar) and bool(_relations(e))


def _plain(t: Any) -> ir.Table:
    """The same relation as a plain `ir.Table` (no Frame subclass, no overrides)."""
    return t.op().to_expr()


@dataclass_transform(kw_only_default=True, field_specifiers=(field,))
class Frame(_TableBase):
    """Base class of all tacit frames. Subclass it and declare `Column[T]` fields."""

    __slots__ = ("_exprs", "_names")
    __tacit_fields__: ClassVar[dict[str, FieldSpec]] = {}
    if TYPE_CHECKING:
        _names: dict[str, str] | None
        _exprs: dict[str, ir.Value] | None

        def __tacit_into__(self, x: Self, /) -> object: ...

    # -- class creation ------------------------------------------------------
    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        hints = get_type_hints(cls, include_extras=True)
        order: list[str] = []

        def walk(c: type) -> None:
            for b in c.__bases__:
                if issubclass(b, Frame) and b is not Frame:
                    walk(b)
            for name in inspect.get_annotations(c):
                if name not in order and not name.startswith("_"):
                    order.append(name)

        walk(cls)
        fields: dict[str, FieldSpec] = {}
        for name in order:
            hint = hints[name]
            if get_origin(hint) is ClassVar or hint is ClassVar:
                continue
            if name in _RESERVED:
                raise TypeError(
                    f"{cls.__name__}.{name}: '{name}' is an ibis Table / Frame member. Rename the attribute and "
                    f"map it to the physical column: `{name}_: Column[...] = tc.field(name={name!r})` "
                    f"(or read it untyped with frame[{name!r}])"
                )
            raw = next((c.__dict__[name] for c in cls.__mro__ if c is not Frame and name in c.__dict__), None)
            info = raw.info if isinstance(raw, _ColumnDescriptor) else raw
            spec = resolve_field(name, hint, info, cls.__name__)
            for b in cls.__bases__:
                other = getattr(b, "__tacit_fields__", {}).get(name)
                if other is not None and (other.pytype, other.dtype) != (spec.pytype, spec.dtype):
                    raise TypeError(
                        f"{cls.__name__}.{name}: conflicting declarations {other.pytype!r} "
                        f"(from {b.__name__}) vs {spec.pytype!r}"
                    )
            fields[name] = spec
            setattr(cls, name, _ColumnDescriptor(spec, info if isinstance(info, FieldInfo) else None))
        cls.__tacit_fields__ = fields

    # -- construction: a checked projection ----------------------------------
    def __init__(self, **columns: Any) -> None:
        """Build this frame from one expression per column (synthesized, typed signature).

        * all column expressions must come from ONE table (use `tc.join` for two);
        * Python literals become typed literals; class-level refs (`Orders.amount`) resolve
          against that table;
        * if any value is a reduction (`x.sum()`), the column-valued arguments become the
          GROUP BY keys (implicit grouping, like SQL);
        * strict: exactly the declared columns, compatible dtypes (lossless int->float
          widening is applied).
        """
        self._construct(columns, by=None, context=f"{type(self).__name__}(...)")

    def _construct(self, columns: Mapping[str, Any], *, by: Sequence[ir.Value] | None, context: str) -> None:
        cls = type(self)
        fields = cls.__tacit_fields__
        issues = [Issue("missing_column", a) for a in fields if a not in columns]
        issues += [Issue("extra_column", k) for k in columns if k not in fields]
        if issues:
            raise ValidationError(cls.__name__, context, issues)

        exprs: dict[str, ir.Value] = {}
        deferred: dict[str, Deferred] = {}
        for attr, v in columns.items():
            spec = fields[attr]
            if isinstance(v, Frame):
                raise TypeError(f"{context}: {attr}= got a frame, expected a column expression")
            if isinstance(v, Deferred):
                deferred[attr] = v
            elif isinstance(v, ir.Value):
                exprs[attr] = v
            else:
                exprs[attr] = ibis.literal(v, type=spec.dtype)
        rels = frozenset().union(*(_relations(e) for e in exprs.values()))
        if len(rels) != 1:
            detail = (
                "no column expression to select from"
                if not rels
                else f"column expressions come from {len(rels)} different tables; combine them with tc.join(...)"
            )
            raise ValidationError(cls.__name__, context, [Issue("relation", detail=detail)])
        src: ir.Table = next(iter(rels)).to_expr()
        if deferred:
            bound = src.bind(**deferred)
            exprs.update(dict(zip(deferred, bound, strict=True)))

        aggs = {a: e for a, e in exprs.items() if _is_reduction(e)}
        keys = {a: e for a, e in exprs.items() if a not in aggs and isinstance(e, ir.Column)}
        consts = {a: e for a, e in exprs.items() if a not in aggs and a not in keys}
        if by is not None:
            by_ops = [b.op() for b in by]
            bad = [a for a, e in keys.items() if e.op() not in by_ops]
            if bad:
                detail = "neither one of the by=[...] keys nor a reduction (.sum(), .count(), ...)"
                raise ValidationError(cls.__name__, context, [Issue("not_a_reduction", a, detail=detail) for a in bad])
        names = {a: fields[a].name for a in exprs}
        try:
            if aggs or by is not None:
                metrics = {names[a]: e for a, e in aggs.items()}
                grouped = src.group_by(**{names[a]: e for a, e in keys.items()}) if keys else None
                table = grouped.aggregate(**metrics) if grouped is not None else src.aggregate(**metrics)
                if consts:
                    table = table.mutate(**{names[a]: e for a, e in consts.items()})
                object.__setattr__(self, "_exprs", None)  # aggregated frames cannot be extend() deltas
            else:
                table = src.select(**{names[a]: e for a, e in exprs.items()})
                object.__setattr__(self, "_exprs", {names[a]: e for a, e in exprs.items()})
        except IbisError as exc:
            raise ValidationError(cls.__name__, context, [Issue("relation", detail=str(exc))]) from None
        object.__setattr__(self, "_arg", cls._checked(table, context=context, extra="forbid").op())
        object.__setattr__(self, "_names", None)

    @classmethod
    def _checked(cls, table: ir.Table, *, context: str, extra: Extra) -> ir.Table:
        """Structural check + lossless widening + projection to declared order.

        Memoised per (class, ibis schema, extra): repeated casts of same-shaped tables
        cost a dict lookup (E4: rebuilding the target schema dominated cast() cost).
        """
        fields = cls.__tacit_fields__
        schema = table.schema()
        memo_key = (schema, extra)
        memo = cls.__dict__.get("_tacit_memo")
        if memo is None:
            memo = {}
            setattr(cls, "_tacit_memo", memo)
        if memo_key not in memo:
            widen: dict[str, Any] = {}
            found: list[Issue] = []
            for i in structural_issues(fields, schema, extra=extra):
                spec = next((f for f in fields.values() if f.name == i.column), None)
                target = spec.widening_target(schema[spec.name]) if (spec and i.code == "dtype") else None
                if target is not None and spec is not None:
                    widen[spec.name] = target
                else:
                    found.append(i)
            memo[memo_key] = (found, widen)
        issues, widen = memo[memo_key]
        if issues:
            raise ValidationError(cls.__name__, context, issues)
        if widen:
            table = table.cast(widen)
        return project(fields, table)

    @classmethod
    def _wrap(cls, table: ir.Table, names: dict[str, str] | None = None) -> Self:
        obj = object.__new__(cls)
        object.__setattr__(obj, "_arg", table.op())
        object.__setattr__(obj, "_names", names)
        object.__setattr__(obj, "_exprs", None)
        return obj

    def __reduce__(self) -> Any:  # ibis pickles as cls(arg); our __init__ is the typed constructor
        return (_rewrap_op, (type(self), self.op(), self._names))

    # -- boundaries -----------------------------------------------------------
    @classmethod
    def conform(cls, table: ir.Table | _TableBase, *, extra: Extra = "ignore") -> Self:
        """Structural check only (no query): names + dtype families, NOT NULL-aware.

        (E8's `Orders.cast(t)`; renamed because `cast` is an ibis Table method.)
        Input-boundary semantics: the table needs *at least* the declared columns;
        extras are dropped (projection) unless `extra="forbid"`.
        """
        t = as_table(table)
        return cls._wrap(cls._checked(t, context=f"{cls.__name__}.conform", extra=extra))

    @classmethod
    def parse(cls, table: ir.Table | _TableBase, *, extra: Extra = "ignore") -> Self:
        """Coerce + validate (one aggregate query; samples fetched only on failure)."""
        t = as_table(table)
        out = parse_table(cls.__name__, cls.__tacit_fields__, t, extra=extra, context=f"{cls.__name__}.parse")
        return cls._wrap(out)

    @classmethod
    def extend(cls, base: Into[Self], delta: Into[Self], /, *more: Into[Self]) -> Self:
        """`base`'s columns + the columns of constructor-built delta frames -> `cls`.

        Statically, `Into[Self]` requires `cls` to subclass `type(base)` and every
        delta's class. At runtime the result is strictly checked against `cls`.
        """
        ctx = f"{cls.__name__}.extend"
        if not isinstance(base, Frame):
            raise TypeError(f"{ctx}: base must be a tacit Frame, got {type(base).__name__}")
        if base._names:
            raise TypeError(f"{ctx}: base is a join view; build the output with the constructor instead")
        new: dict[str, ir.Value] = {}
        for d in (delta, *more):
            if not isinstance(d, Frame) or d._exprs is None:
                raise TypeError(f"{ctx}: deltas must be frames built with their constructor (not aggregated)")
            new.update(d._exprs)
        try:
            table = _plain(base).mutate(**new) if new else _plain(base)
        except IbisError as exc:
            detail = f"a delta column is not derived from the base frame ({type(base).__name__}): {exc}"
            raise ValidationError(cls.__name__, ctx, [Issue("relation", detail=detail)]) from None
        return cls._wrap(cls._checked(table, context=ctx, extra="ignore"))

    @classmethod
    def aggregate_by[**P, R](cls: Callable[P, R], by: Sequence[Column[Any]], /) -> Callable[P, R]:  # type: ignore[misc]  # pyrefly: cls must be type[...]
        """Explicit grouping: `Stats.aggregate_by([o.country])(country=o.country, total=o.amount.sum())`.

        (E8's `Stats.aggregate(by=...)`; renamed because `aggregate` is an ibis Table method.)

        The returned callable has exactly the constructor's (typed) signature. At
        runtime every non-key value must be a reduction and every column-valued
        argument must be one of `by`.
        """
        frame_cls: Any = cls

        def build(*args: P.args, **kwargs: P.kwargs) -> R:
            if args:
                raise TypeError("frame constructors are keyword-only")
            obj = object.__new__(frame_cls)
            obj._construct(kwargs, by=list(by), context=f"{frame_cls.__name__}.aggregate_by(...)")  # type: ignore[arg-type]
            return obj  # type: ignore[no-any-return]

        return build

    # -- schema-preserving overrides of ibis methods (return Self) --------------
    # Everything else is ibis's own method, inherited at runtime, returning ir.Table.
    def filter(self, *predicates: Column[bool | None] | ir.BooleanValue | Deferred) -> Self:  # type: ignore[override]
        return self._guard("filter", lambda: _plain(self).filter(*predicates))  # type: ignore[arg-type]

    def order_by(self, *keys: Column[Any] | ir.Column | Deferred | str) -> Self:  # type: ignore[override]
        return self._guard("order_by", lambda: _plain(self).order_by(*keys))  # type: ignore[arg-type]

    def limit(self, n: int | None, /, *, offset: int = 0) -> Self:  # type: ignore[override]
        return self._rewrap(_plain(self).limit(n, offset=offset))

    def head(self, n: int = 5, /) -> Self:  # type: ignore[override]
        return self._rewrap(_plain(self).head(n))

    def distinct(  # type: ignore[override]
        self,
        *,
        on: Column[Any] | str | Sequence[Column[Any] | str] | None = None,
        keep: Literal["first", "last"] | None = "first",
    ) -> Self:
        if on is None:
            return self._rewrap(_plain(self).distinct())
        keys = [on] if isinstance(on, ir.Value | str) else list(on)
        names = [k if isinstance(k, str) else k.get_name() for k in keys]  # type: ignore[attr-defined]
        return self._guard("distinct", lambda: _plain(self).distinct(on=names, keep=keep))

    def cache(self) -> Self:  # type: ignore[override]
        return self._rewrap(_plain(self).cache())

    def _guard(self, op: str, build: Callable[[], ir.Table]) -> Self:
        """Run an ibis op; a column handle bound to another table becomes a tacit error."""
        try:
            return self._rewrap(build())
        except IbisError as exc:
            detail = f"a column expression passed to .{op}() is not derived from this frame ({exc})"
            raise ValidationError(type(self).__name__, f"{type(self).__name__}.{op}", [Issue("relation", detail=detail)]) from None

    def _rewrap(self, table: ir.Table) -> Self:
        return type(self)._wrap(table, self._names)

    if not TYPE_CHECKING:  # runtime only: checkers must not see a __getattr__ (it would hide typos)

        def __getattr__(self, key: str) -> Any:
            import difflib

            if key.startswith("__"):
                raise AttributeError(key)
            close = difflib.get_close_matches(key, list(type(self).__tacit_fields__), n=1)
            hint = f"; did you mean {close[0]!r}?" if close else ""
            raise AttributeError(f"{type(self).__name__} has no column or attribute {key!r}{hint}")


def _rewrap_op(cls: type[Frame], op: Any, names: dict[str, str] | None) -> Frame:
    return cls._wrap(op.to_expr(), names)


def as_table(frame: ir.Table | _TableBase, /) -> ir.Table:
    """A frame (or any table) as a plain `ir.Table` -- for ibis APIs typed `ir.Table`.

    A frame already IS an `ir.Table` at runtime; this exists for the static side,
    where a frame's base is the clean mirror rather than `ir.Table`.
    """
    if isinstance(frame, Frame) and frame._names:
        t = _plain(frame)
        return t.select(**{a: t[n] for a, n in frame._names.items()})
    return _plain(frame)


# every public ibis Table member + Frame's own public names (columns may not shadow them:
# ibis's own methods call e.g. self.select(...) internally)
IBIS_TABLE_MEMBERS = frozenset(n for n in dir(ir.Table) if not n.startswith("_"))
_RESERVED = IBIS_TABLE_MEMBERS | frozenset(n for n in vars(Frame) if not n.startswith("_"))


def fields(frame: type[Frame] | Frame) -> dict[str, FieldSpec]:
    """Resolved column specs of a frame class (free function: no name collisions)."""
    cls = frame if isinstance(frame, type) else type(frame)
    return dict(cls.__tacit_fields__)


def schema(frame: type[Frame] | Frame) -> ibis.Schema:
    """ibis schema of the declared columns (physical names and dtypes)."""
    return ibis.schema({f.name: (f.dtype if f.dtype is not None else "unknown") for f in fields(frame).values()})
