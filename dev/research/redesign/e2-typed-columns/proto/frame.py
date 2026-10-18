"""Prototype: "the schema class is the typed frame" (wrapper, not ir.Table subclass).

    class Iris(Frame):
        sepal_length: Float64
        species: String

    iris = Iris.parse(raw)            # -> Iris (wraps an ibis Table)
    iris.sepal_length                 # -> ir.FloatingColumn (statically)
    Iris.sepal_length                 # -> Deferred (`_.sepal_length`) at runtime
    IrisFeatures(sepal_length=..., ...)   # typed projection (dataclass_transform)

Column aliases live in aliases_ann.py (A3: Annotated[ir.XColumn, dtype]) and
aliases_desc.py (A1: Annotated[Col[Get, Set], dtype], a typed descriptor).
The runtime is shared: __init_subclass__ installs a Col descriptor per field.
"""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    ClassVar,
    Self,
    dataclass_transform,
    get_args,
    get_origin,
    get_type_hints,
    overload,
)

import ibis
import ibis.expr.datatypes as dt
import ibis.expr.types as ir
from ibis import Deferred, _


class Col[G, S]:
    """Typed column descriptor. G: instance-access type, S: accepted value type."""

    def __init__(self, dtype: dt.DataType | None = None) -> None:
        self.dtype = dtype
        self.name = ""

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name

    @overload
    def __get__(self, obj: None, owner: type) -> Deferred: ...
    @overload
    def __get__(self, obj: Frame, owner: type) -> G: ...
    def __get__(self, obj: Frame | None, owner: type) -> Any:
        if obj is None:
            return _[self.name]  # class access: unbound column reference
        return obj._table[self.name]

    # Only used statically: dataclass_transform takes the __init__ parameter
    # type of a descriptor-typed field from __set__'s value parameter.
    def __set__(self, obj: Frame, value: S) -> None:
        raise AttributeError("Frame columns are read-only")


def column() -> Any:
    """Field specifier (no default => required in the synthesized __init__)."""
    return None


def _dtype_of(hint: Any) -> dt.DataType:
    if get_origin(hint) is Annotated:
        for meta in get_args(hint)[1:]:
            if isinstance(meta, dt.DataType):
                return meta
    raise TypeError(f"column annotation {hint!r} carries no ibis dtype")


@dataclass_transform(kw_only_default=True, field_specifiers=(column,))
class Frame:
    """Base class: a schema whose instances wrap an ibis Table."""

    __tacit_fields__: ClassVar[dict[str, dt.DataType]] = {}
    __slots__ = ("_table", "_exprs")
    if TYPE_CHECKING:  # slot types; the decorated base's own annotations are not fields
        _table: ir.Table
        _exprs: dict[str, ir.Value]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        fields: dict[str, dt.DataType] = {}
        for name, hint in get_type_hints(cls, include_extras=True).items():
            if get_origin(hint) is ClassVar or name.startswith("_"):
                continue
            fields[name] = _dtype_of(hint)
            if not isinstance(cls.__dict__.get(name), Col):
                col: Col[Any, Any] = Col(fields[name])
                col.__set_name__(cls, name)
                setattr(cls, name, col)
        cls.__tacit_fields__ = fields

    # ---- construction -----------------------------------------------------
    def __init__(self, **columns: Any) -> None:
        """Typed projection: build this frame from one column expression per field.

        Column-shaped values are projected; if any value is a reduction (a scalar
        derived from the table), the column-shaped ones become group keys
        (SQL's implicit GROUP BY), e.g. PricingSummary(l_returnflag=li.l_returnflag,
        sum_qty=li.l_quantity.sum(), ...).
        """
        exprs = {k: ibis.literal(v) if not isinstance(v, ir.Value) else v for k, v in columns.items()}
        rels = {r for e in exprs.values() for r in e.op().relations}  # type: ignore
        if len(rels) != 1:
            raise ValueError(f"expected expressions over exactly one table, got {len(rels)}")
        src = next(iter(rels)).to_expr()
        aggs = {k: e for k, e in exprs.items() if isinstance(e, ir.Scalar) and e.op().relations}  # type: ignore
        if aggs:
            keys = {k: e for k, e in exprs.items() if k not in aggs}
            table = src.group_by(**keys).aggregate(**aggs) if keys else src.aggregate(**aggs)
        else:
            table = src.select(**exprs)
        self._set(self._checked(table))
        object.__setattr__(self, "_exprs", exprs)

    @classmethod
    def extend(cls, base: Frame, *parts: Frame) -> Self:
        """base + constructor-checked delta frames -> cls (coverage checked at runtime)."""
        new = {k: v for p in parts for k, v in p._exprs.items()}
        return cls.cast(base._table.mutate(**new))

    @classmethod
    def _wrap(cls, table: ir.Table) -> Self:
        obj = object.__new__(cls)
        obj._set(table)
        object.__setattr__(obj, "_exprs", {})
        return obj

    def _set(self, table: ir.Table) -> None:
        object.__setattr__(self, "_table", table)

    @classmethod
    def _checked(cls, table: ir.Table) -> ir.Table:
        want = cls.__tacit_fields__
        have = dict(table.schema().items())
        missing, extra = sorted(want.keys() - have.keys()), sorted(have.keys() - want.keys())
        wrong = {k: (want[k], have[k]) for k in want.keys() & have.keys() if want[k] != have[k]}
        if missing or extra or wrong:
            raise TypeError(f"{cls.__name__}: missing={missing} extra={extra} wrong={wrong}")
        return table.select(*want)  # canonical column order

    @classmethod
    def cast(cls, table: ir.Table) -> Self:
        """Metadata-only structural check (names + dtypes), strict."""
        return cls._wrap(cls._checked(table))

    @classmethod
    def parse(cls, table: ir.Table) -> Self:
        """Coerce dtypes, then structural check (pandera validation omitted in the spike)."""
        casts = {k: v for k, v in cls.__tacit_fields__.items() if k in table.columns}
        return cls.cast(table.cast(casts))

    # ---- reaching the ibis API (variant B2: explicit escape hatch) ---------
    @property
    def t(self) -> ir.Table:
        return self._table

    # ---- variant B4: typed subset of delegated methods ----------------------
    def filter(self, *predicates: ir.BooleanValue | Deferred) -> Self:
        """Row filter preserves the schema, so it can return Self."""
        return self._wrap(self._table.filter(*predicates))

    def order_by(self, *keys: str | ir.Column | Deferred) -> Self:
        return self._wrap(self._table.order_by(*keys))

    def limit(self, n: int) -> Self:
        return self._wrap(self._table.limit(n))

    def mutate(self, **exprs: ir.Value | Deferred | int | float | str) -> ir.Table:
        return self._table.mutate(**exprs)  # type: ignore  # ibis Issue 2 (literals)

    def group_by(self, *keys: str | ir.Value | Deferred) -> ir.GroupedTable:
        return self._table.group_by(*keys)

    def execute(self) -> Any:
        return self._table.execute()

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._table.schema()})"
