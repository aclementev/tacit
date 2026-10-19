"""Structural checks (metadata only) and data checks (one aggregate query).

Ibis-native validator following E4's design (e4-runtime/ibisval.py), replacing
the pandera path of tacit 0.2 (16-30 queries per parse, ~2 s import):

* coercion uses `try_cast`; a cell fails coercion when raw is not NULL but the cast is;
* every check (coercion failures, NULLs -- NaN counts as NULL for floats --,
  constraints, uniqueness as count - nunique) is one `sum` in a single
  `aggregate()` query;
* only if something failed, ONE bounded `UNION ALL` query fetches up to 5
  sample values per failing check. Happy path: 1 query; failure path: 2.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

import ibis
import ibis.expr.datatypes as dt
import ibis.expr.types as ir

from ._errors import SAMPLE_LIMIT, Issue, ValidationError
from ._fields import FieldSpec

Extra = Literal["ignore", "forbid"]


def structural_issues(
    fields: Mapping[str, FieldSpec], schema: ibis.Schema, *, extra: Extra
) -> list[Issue]:
    have: dict[str, dt.DataType] = dict(schema.items())
    issues: list[Issue] = []
    for f in fields.values():
        if f.name not in have:
            issues.append(Issue("missing_column", f.name, expected=str(f.dtype or "any")))
        elif not f.accepts(have[f.name]):
            issues.append(Issue("dtype", f.name, expected=str(f.dtype), actual=str(have[f.name])))
    if extra == "forbid":
        declared = {f.name for f in fields.values()}
        issues += [Issue("extra_column", n, actual=str(d)) for n, d in have.items() if n not in declared]
    return issues


def project(fields: Mapping[str, FieldSpec], table: ir.Table) -> ir.Table:
    """Select the declared columns, in declaration order (drops extras)."""
    return table.select(*[f.name for f in fields.values()])


def _check_expr(f: FieldSpec, col: ir.Value, kind: str, value: Any) -> ir.BooleanValue:
    """Boolean expression that is TRUE for a failing row (NULL rows never fail a constraint)."""
    c: Any = col
    if kind == "ge":
        return c < value
    if kind == "gt":
        return c <= value
    if kind == "le":
        return c > value
    if kind == "lt":
        return c >= value
    if kind == "between":
        return (c < value[0]) | (c > value[1])
    if kind == "isin":
        return c.notin(value)
    if kind == "notin":
        return c.isin(value)
    if kind in ("pattern", "str_matches"):
        return ~c.re_search(value)
    if kind == "check":
        return ~value[0](c)
    if kind == "length":
        exact, lo, hi = value
        n = c.length()
        conds = []
        if exact is not None:
            conds.append(n != exact)
        if lo is not None:
            conds.append(n < lo)
        if hi is not None:
            conds.append(n > hi)
        out = conds[0]
        for x in conds[1:]:
            out = out | x
        return out
    raise ValueError(f"unknown constraint {kind}")


def _constraint_label(kind: str, value: Any) -> str:
    if kind == "check":
        return f"check({value[1]})"
    if kind == "length":
        exact, lo, hi = value
        args = [repr(exact)] if exact is not None else []
        args += [f"min={lo}"] if lo is not None else []
        args += [f"max={hi}"] if hi is not None else []
        return f"length({', '.join(args)})"
    return f"{kind}({value!r})"


def parse_table(
    schema_name: str,
    fields: Mapping[str, FieldSpec],
    table: ir.Table,
    *,
    extra: Extra,
    context: str,
    coerce: bool = True,
) -> ir.Table:
    """Coerce + validate. Returns the projected, coerced table or raises ValidationError."""
    have: dict[str, dt.DataType] = dict(table.schema().items())
    issues = [i for i in structural_issues(fields, table.schema(), extra=extra) if i.code != "dtype" or not coerce]
    if issues:
        raise ValidationError(schema_name, context, issues)

    src = project(fields, table)
    out_cols: dict[str, ir.Value] = {}
    coerced: dict[str, tuple[str, str]] = {}  # name -> (from, to)
    for f in fields.values():
        col = src[f.name]
        if f.dtype is not None and not f.accepts(have[f.name]):
            target = f.physical()
            out_cols[f.name] = col.try_cast(target)
            coerced[f.name] = (str(have[f.name]), str(target))
        else:
            out_cols[f.name] = col
    result = src.select(**out_cols)

    # One aggregate query: count failing rows per check.
    metrics: dict[str, ir.Scalar] = {}
    preds: dict[str, tuple[ir.BooleanValue, Issue]] = {}

    def add(key: str, pred: ir.BooleanValue, issue: Issue) -> None:
        metrics[key] = pred.fill_null(False).cast("int64").sum()
        preds[key] = (pred, issue)

    staged = src.select(**{f"__src_{n}": src[n] for n in coerced}, **out_cols)
    for f in fields.values():
        c = staged[f.name]
        if f.name in coerced:
            frm, to = coerced[f.name]
            add(
                f"coerce:{f.name}",
                staged[f"__src_{f.name}"].notnull() & c.isnull(),
                Issue("coercion", f.name, expected=to, actual=frm),
            )
        if not f.nullable:
            nulls = c.isnull()
            if f.dtype is not None and f.dtype.is_floating():
                nulls = nulls | c.isnan()
            if f.name in coerced:  # don't double-report rows that failed coercion
                nulls = nulls & staged[f"__src_{f.name}"].isnull()
            add(f"null:{f.name}", nulls, Issue("null", f.name))
        for i, cons in enumerate(f.constraints):
            if cons.kind == "unique":
                metrics[f"unique:{f.name}"] = c.count() - c.nunique()
                continue
            add(
                f"c{i}:{f.name}",
                _check_expr(f, c, cons.kind, cons.value),
                Issue("constraint", f.name, expected=_constraint_label(cons.kind, cons.value)),
            )
    if not metrics:
        return result
    counts = staged.aggregate(**metrics).to_pyarrow().to_pylist()[0]
    failing = {k: int(n) for k, n in counts.items() if n}  # SUM over an empty table is NULL
    if not failing:
        return result

    # Second (and last) query: bounded samples for every failing check, one UNION ALL.
    parts: list[ir.Table] = []
    for key in failing:
        if key.startswith("unique:"):
            name = key.split(":", 1)[1]
            dups = staged.group_by(name).aggregate(__n=staged[name].count()).filter(ibis._["__n"] > 1)
            parts.append(dups.select(__key=ibis.literal(key), __val=dups[name].cast("string")).limit(SAMPLE_LIMIT))
            continue
        pred, issue = preds[key]
        assert issue.column is not None
        col = f"__src_{issue.column}" if issue.code == "coercion" else issue.column
        bad = staged.filter(pred.fill_null(False))
        parts.append(bad.select(__key=ibis.literal(key), __val=bad[col].cast("string")).limit(SAMPLE_LIMIT))
    rows = (ibis.union(*parts, distinct=False) if len(parts) > 1 else parts[0]).to_pyarrow().to_pylist()
    samples: dict[str, list[object]] = {}
    for r in rows:
        samples.setdefault(r["__key"], []).append(r["__val"])

    failures: list[Issue] = []
    for key, n in failing.items():
        if key.startswith("unique:"):
            name = key.split(":", 1)[1]
            failures.append(Issue("unique", name, count=n, samples=tuple(samples.get(key, ()))))
        else:
            _, issue = preds[key]
            failures.append(Issue(issue.code, issue.column, issue.expected, issue.actual, n, tuple(samples.get(key, ()))))
    raise ValidationError(schema_name, context, failures)
