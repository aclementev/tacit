"""Prototype: ibis-native validator that runs ALL checks in ONE aggregate query.

Pandera `Check` objects are used purely as declarative specs (name + statistics);
pandera's ibis *backend* is not used. Predicates are plain ibis column expressions.

    plan = build_plan(Customer)                    # pure metadata
    report = validate(Customer, table)             # 1 query (+1 only when something fails)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import ibis
import ibis.expr.types as ir

# check name (pandera Check.name) -> predicate(col, **statistics) -> boolean column ("True = ok")
BUILTIN: dict[str, Callable[..., Any]] = {
    "equal_to": lambda c, value: c == value,
    "not_equal_to": lambda c, value: c != value,
    "greater_than": lambda c, min_value: c > min_value,
    "greater_than_or_equal_to": lambda c, min_value: c >= min_value,
    "less_than": lambda c, max_value: c < max_value,
    "less_than_or_equal_to": lambda c, max_value: c <= max_value,
    "in_range": lambda c, min_value, max_value, include_min=True, include_max=True: (
        ((c >= min_value) if include_min else (c > min_value))
        & ((c <= max_value) if include_max else (c < max_value))
    ),
    "isin": lambda c, allowed_values: c.isin(list(allowed_values)),
    "notin": lambda c, forbidden_values: ~c.isin(list(forbidden_values)),
    "str_matches": lambda c, pattern: c.re_search(getattr(pattern, "pattern", pattern) if str(getattr(pattern, "pattern", pattern)).startswith("^") else "^" + str(getattr(pattern, "pattern", pattern))),
    "str_contains": lambda c, pattern: c.re_search(getattr(pattern, "pattern", pattern)),
    "str_startswith": lambda c, string: c.startswith(string),
    "str_endswith": lambda c, string: c.endswith(string),
    "str_length": lambda c, min_value=None, max_value=None, exact_value=None: (
        c.length() == exact_value if exact_value is not None
        else c.length().between(min_value, max_value) if min_value is not None and max_value is not None
        else c.length() >= min_value if min_value is not None
        else c.length() <= max_value
    ),
}


@dataclass
class Item:
    column: str
    name: str                    # human-readable check name
    pred: Callable[[ir.Table], ir.BooleanValue]   # table -> boolean "ok" expr (NULL = ignored)


@dataclass
class Plan:
    nullable: dict[str, bool]
    items: list[Item]
    unique: list[str] = field(default_factory=list)


def build_plan(schema_cls, unique: list[str] = ()) -> Plan:
    items: list[Item] = []
    for col, checks in schema_cls._field_checks.items():
        for ck in checks:
            fn = BUILTIN[ck.name]  # KeyError => custom check: needs the pandera-extraction fallback
            stats = dict(ck.statistics)
            items.append(Item(col, f"{ck.name}({', '.join(f'{k}={v!r}' for k, v in stats.items())})",
                              lambda t, col=col, fn=fn, stats=stats: fn(t[col], **stats)))
    nullable = {c: schema_cls._field_nullable.get(c, False) for c in schema_cls._fields}
    return Plan(nullable, items, list(unique))


@dataclass
class Report:
    null_counts: dict[str, int]
    check_failures: dict[str, int]      # "col: check" -> n failing rows
    coercion_failures: dict[str, int]
    duplicates: dict[str, int]
    samples: list[tuple[str, str, str]] | None = None   # (column, check, value)
    n_queries: int = 1

    @property
    def ok(self):
        return not (self.null_counts or self.check_failures or self.coercion_failures or self.duplicates)


def _prepare(schema_cls, t: ir.Table, coerce: bool):
    """Return (table with target dtypes, set of columns coerced from string with try_cast).

    String-sourced columns keep their raw value in `__raw_<col>` so coercion failures
    (raw not null but try_cast is null) are countable in the same aggregate query.
    """
    target = schema_cls._ibis_schema()
    raw, plain = {}, {}
    for col, tt in target.items():
        src = t[col].type()
        if src != tt:
            if src.is_string() and coerce:
                raw[f"__raw_{col}"] = t[col]
            else:
                plain[col] = t[col].cast(tt)          # same as tacit parse(): strict cast
    tc = t.mutate(**raw, **plain) if (raw or plain) else t
    tc = tc.mutate(**{c: tc[f"__raw_{c}"].try_cast(target[c]) for c in (k[6:] for k in raw)}) if raw else tc
    return tc, {k[6:] for k in raw}


def validate(schema_cls, t: ir.Table, plan: Plan | None = None, *, coerce: bool = False,
             n_samples: int = 5, unique: list[str] = ()) -> Report:
    plan = plan or build_plan(schema_cls, unique)
    tc, coerced = _prepare(schema_cls, t, coerce)

    aggs: dict[str, ir.Scalar] = {}
    for col, tt in schema_cls._ibis_schema().items():
        if col in coerced:
            aggs[f"coerce::{col}"] = (tc[f"__raw_{col}"].notnull() & tc[col].isnull()).cast("int64").sum()
        if not plan.nullable[col]:
            isna = tc[col].isnull()
            if tt.is_floating():
                isna = isna | tc[col].isnan()
            aggs[f"null::{col}"] = isna.cast("int64").sum()
    for i, it in enumerate(plan.items):
        ok = it.pred(tc)
        aggs[f"check::{i}"] = (~ok).cast("int64").sum()        # NULL ok => ignored (pandera ignore_na=True)
    for col in plan.unique:
        aggs[f"dup::{col}"] = tc.count() - tc[col].nunique()    # rows beyond the first of each value
    row = tc.aggregate(**aggs).to_pyarrow().to_pylist()[0]       # <-- THE query
    g = lambda k: row[k] or 0                                    # SUM over empty table is NULL
    rep = Report(
        null_counts={k[6:]: g(k) for k in row if k.startswith("null::") and g(k)},
        check_failures={f"{plan.items[int(k[7:])].column}: {plan.items[int(k[7:])].name}": g(k)
                        for k in row if k.startswith("check::") and g(k)},
        coercion_failures={k[8:]: g(k) for k in row if k.startswith("coerce::") and g(k)},
        duplicates={k[5:]: g(k) for k in row if k.startswith("dup::") and g(k)},
    )
    if rep.ok or not n_samples:
        return rep
    # second (and last) query: samples of offending values, only for failing items, one UNION ALL
    parts = []
    for k in row:
        if not g(k):
            continue
        kind, key = k.split("::")
        if kind == "check":
            it = plan.items[int(key)]
            bad, col, name, val = ~it.pred(tc), it.column, it.name, tc[it.column]
        elif kind == "null":
            bad, col, name, val = tc[key].isnull(), key, "not_nullable", tc[key]
        elif kind == "coerce":
            bad, col, name, val = tc[f"__raw_{key}"].notnull() & tc[key].isnull(), key, "coercion", tc[f"__raw_{key}"]
        else:
            continue
        parts.append(tc.filter(bad.fill_null(False)).select(
            column=ibis.literal(col), check=ibis.literal(name), value=val.cast("string")).limit(n_samples))
    if parts:
        s = ibis.union(*parts, distinct=False) if len(parts) > 1 else parts[0]
        rep.samples = [(r["column"], r["check"], r["value"]) for r in s.to_pyarrow().to_pylist()]
        rep.n_queries = 2
    return rep
