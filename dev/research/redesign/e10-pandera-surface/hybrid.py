"""Hybrid executor: pandera is the spec + check library, tacit runs it in ONE aggregate query.

    report = validate(schema, table)          # pandera.ibis.DataFrameSchema, ibis.Table

* Structural part (dtype, strict/filter, ordered, required, column presence) is delegated to
  pandera itself under `config_context(validation_depth=SCHEMA_ONLY)` -> 0 data queries.
* Every data-scope item (nullable, unique, column checks, dataframe checks) is turned into an
  ibis boolean expression over the *same* base table by calling pandera's own check function
  (`check._check_fn(IbisData(t, key), **check._check_kwargs)`, i.e. what IbisCheckBackend does),
  then all of them are reduced in a single `t.aggregate(...)`.
* Only if something failed, one bounded UNION ALL query fetches samples.
* Check outputs we cannot fuse (python bool computed eagerly, tables that are not a projection
  of `t`, ...) fall back to pandera's own CheckBackend: one extra query each, counted in report.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Any

import ibis
import ibis.expr.operations as ops
import ibis.expr.types as ir
import ibis.selectors as s

import pandera.errors as pe
from pandera.api.checks import Check
from pandera.api.ibis.types import IbisData
from pandera.config import ValidationDepth, config_context

DEFAULT_SAMPLES = 5


@dataclass
class Item:
    column: str | None          # None = dataframe-level
    check: Any                  # Check | "not_nullable" | "unique" | "column_unique"
    check_index: int | None
    reason: str                 # pandera SchemaErrorReason name
    ok: ir.BooleanValue | None  # row-level "ok" predicate (NULL = pass, as pandera's .all())
    passed: ir.BooleanScalar | None = None  # scalar-level check
    const: bool | None = None   # check already evaluated (python bool / fallback)
    fallback: bool = False
    count_expr: ir.IntegerScalar | None = None  # custom failure-count expression (unique)
    sample_val: ir.Value | None = None
    error: str | None = None


@dataclass
class Failure:
    column: str | None
    check: str
    check_index: int | None
    reason: str
    count: int | None           # failing rows; None for scalar checks
    samples: list = field(default_factory=list)


@dataclass
class Report:
    failures: list[Failure]
    warnings: list[Failure]
    n_queries: int
    n_fallback: int
    table: ir.Table

    @property
    def ok(self) -> bool:
        return not self.failures


def _label(check) -> str:
    if isinstance(check, str):
        return check
    return check.error or check.name


def _is_over(expr: ir.Expr, t: ir.Table) -> bool:
    rels = expr.op().relations
    return rels <= {t.op()}


def _resolve_fn(check: Check):
    # Mirror Check.__call__: reload builtin dispatchers by the check fn's own name.
    fn = check._check_fn
    name = getattr(fn, "__name__", None)
    if name is not None and Check.is_builtin_check(name):
        fn = Check.get_builtin_check_fn(name)
    return fn


def _nw_dispatch(fn) -> bool:
    reg = getattr(fn, "_function_registry", None)
    return reg is not None and IbisData not in reg


def _normalize(out: Any, t: ir.Table) -> tuple[str, Any]:
    """-> ('const', bool) | ('scalar', BooleanScalar) | ('row'|'table', [BooleanColumn, ...]) | ('opaque', None)"""
    if isinstance(out, bool):
        return "const", out
    if isinstance(out, dict):
        out = list(out.values())
        return ("table", out) if all(_is_over(v, t) for v in out) else ("opaque", None)
    if isinstance(out, ir.Table):
        op = out.op()
        if isinstance(op, ops.Project) and op.parent == t.op():
            vals = [op.values[c].to_expr() for c in out.columns]
            if all(v.type().is_boolean() for v in vals):
                return "table", vals
        return "opaque", None
    if isinstance(out, ir.BooleanScalar) and _is_over(out, t):
        return "scalar", out
    if isinstance(out, ir.BooleanColumn) and _is_over(out, t):
        return "row", [out]
    return "opaque", None


def compile_check(check: Check, t: ir.Table, key: str | None, idx: int) -> Item:
    try:
        return _compile_check(check, t, key, idx)
    except Exception as e:  # noqa: BLE001  -- pandera reports any check exception as CHECK_ERROR
        return Item(key, check, idx, "CHECK_ERROR", None, const=False, error=f"{type(e).__name__}: {e}")


def _compile_check(check: Check, t: ir.Table, key: str | None, idx: int) -> Item:
    fn = _resolve_fn(check)
    kwargs = check._check_kwargs
    if check.element_wise:
        udf = ibis.udf.scalar.python(fn)
        cols = [key] if key is not None else list(t.columns)
        kind, out = "table", [udf(t[c], **kwargs) for c in cols]
    elif getattr(check, "native", True) is False and _nw_dispatch(fn):
        # pandera's narwhals backend is active: builtins are nw.Expr -> nw.Expr. Compile the
        # expression through narwhals back into an ibis projection of t, then unwrap as usual.
        import narwhals.stable.v1 as nw
        expr = fn(nw.col(key), **kwargs)
        kind, out = _normalize(nw.to_native(nw.from_native(t).select(expr.alias(key))), t)
    else:
        kind, out = _normalize(fn(IbisData(t, key), **kwargs), t)
    reason = "DATAFRAME_CHECK"
    if kind == "const":
        return Item(key, check, idx, reason, None, const=bool(out))
    if kind == "scalar":
        return Item(key, check, idx, reason, None, passed=out)
    if kind in ("row", "table"):
        if kind == "table" and key is None and check.ignore_na:
            out = [o | o.isnull() for o in out]       # pandera: per-column ignore_na for table output
        acc = ibis.literal(True)
        for o in out:
            acc = acc & o
        if check.ignore_na and key is not None:
            acc = acc | t[key].isnull()
        return Item(key, check, idx, reason, acc, sample_val=t[key] if key else None)
    # opaque: let pandera's own check backend run it (separate query)
    res = check(t, key)
    passed = res.check_passed.execute()
    return Item(key, check, idx, reason, None, const=bool(passed), fallback=True)


def _schema_only(schema, t: ir.Table) -> tuple[ir.Table, list[pe.SchemaError]]:
    with config_context(validation_depth=ValidationDepth.SCHEMA_ONLY):
        try:
            return schema.validate(t, lazy=True), []
        except pe.SchemaErrors as e:
            return t, list(e.schema_errors)


def _columns(schema, t: ir.Table):
    for name, col in schema.columns.items():
        if col.regex:
            for c in t.select(s.matches(col.selector)).columns:
                yield c, col
        elif name in t.columns:
            yield name, col


def validate(schema, t: ir.Table, *, n_samples: int = DEFAULT_SAMPLES,
             column_unique: bool = True) -> Report:
    t, structural = _schema_only(schema, t)
    failures: list[Failure] = [  # structural errors: reported, and data checks still run (pandera lazy=True)
        Failure(getattr(e.schema, "name", None) if e.schema is not schema else None, str(e.check), None,
                e.reason_code.name, None) for e in structural]

    items: list[Item] = []
    nq = 0
    for name, col in _columns(schema, t):
        c = t[name]
        if not col.nullable:
            isna = c.isnull()
            if c.type().is_floating() and t.get_backend().has_operation(ops.IsNan):
                isna = isna | c.isnan()
            items.append(Item(name, "not_nullable", None, "SERIES_CONTAINS_NULLS", ~isna, sample_val=c))
        if col.unique and column_unique:   # pandera's native ibis backend silently ignores this
            items.append(Item(name, "column_unique", None, "SERIES_CONTAINS_DUPLICATES", None,
                              count_expr=c.count() - c.nunique()))
        for i, ck in enumerate(col.checks):
            it = compile_check(ck, t, name, i)
            nq += it.fallback
            items.append(it)
    for i, ck in enumerate(schema.checks):
        it = compile_check(ck, t, None, i)
        nq += it.fallback
        items.append(it)
    if schema.unique:
        lists = [schema.unique] if all(isinstance(x, str) for x in schema.unique) else schema.unique
        for cols in lists:
            cols = [x for x in cols if x in t.columns]
            key = ibis.struct({x: t[x] for x in cols})       # struct: NULLs group together, like pandera's window
            items.append(Item(None, f"unique{tuple(cols)}", None, "DUPLICATES", None,
                              count_expr=t.count() - key.nunique()))

    # ---- THE query ----
    aggs = {}
    for k, it in enumerate(items):
        if it.ok is not None:
            aggs[f"f{k}"] = (~it.ok).cast("int64").sum()   # NULL ok -> not counted (pandera .all() skips NULL)
        elif it.passed is not None:
            aggs[f"p{k}"] = it.passed
        elif it.count_expr is not None:
            aggs[f"f{k}"] = it.count_expr
    row: dict = {}
    if aggs:
        nq += 1
        try:
            row = t.aggregate(**aggs).to_pyarrow().to_pylist()[0]
        except Exception:  # noqa: BLE001  -- one broken check must not hide the others: isolate
            for name, agg in aggs.items():
                nq += 1
                try:
                    row.update(t.aggregate(**{name: agg}).to_pyarrow().to_pylist()[0])
                except Exception as e:  # noqa: BLE001
                    it = items[int(name[1:])]
                    it.reason, it.const, it.ok, it.passed, it.count_expr = "CHECK_ERROR", False, None, None, None
                    it.error = f"{type(e).__name__}: {e}"

    warns, sample_parts = [], []
    for k, it in enumerate(items):
        if f"f{k}" in row:
            n = row[f"f{k}"] or 0
            failed, count = n > 0, n
        elif f"p{k}" in row:
            failed, count = row[f"p{k}"] is False, None
        else:
            failed, count = it.const is False, None
        if not failed:
            continue
        f = Failure(it.column, _label(it.check), it.check_index, it.reason, count)
        is_warn = isinstance(it.check, Check) and it.check.raise_warning
        (warns if is_warn else failures).append(f)
        if it.ok is not None and n_samples:
            lim = it.check.n_failure_cases if isinstance(it.check, Check) and it.check.n_failure_cases else n_samples
            val = it.sample_val if it.sample_val is not None else ibis.literal("<row>")
            bad = t.filter((~it.ok).fill_null(False))
            sample_parts.append((f, bad.select(__k=ibis.literal(len(sample_parts)), __v=val.cast("string")).limit(lim)))
    for f in warns:
        warnings.warn(f"{f.column}: {f.check} failed on {f.count} rows", pe.SchemaWarning)
    if sample_parts:
        parts = [p for _, p in sample_parts]
        rows = (ibis.union(*parts, distinct=False) if len(parts) > 1 else parts[0]).to_pyarrow().to_pylist()
        nq += 1
        for r in rows:
            sample_parts[r["__k"]][0].samples.append(r["__v"])
    return Report(failures, warns, nq, sum(it.fallback for it in items), t)


def drop_invalid_rows(schema, t: ir.Table) -> ir.Table:
    """Lazy: returns t filtered by the conjunction of every row-level predicate (no query)."""
    t, _ = _schema_only(schema, t)
    acc = ibis.literal(True)
    for name, col in _columns(schema, t):
        for i, ck in enumerate(col.checks):
            it = compile_check(ck, t, name, i)
            if it.ok is not None:
                acc = acc & it.ok.fill_null(True)
        if not col.nullable:
            acc = acc & t[name].notnull()
    return t.filter(acc)
