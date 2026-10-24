"""Structural checks (metadata only) and data checks (E10 hybrid: pandera checks, one fused query).

* coercion uses `try_cast`; a cell fails coercion when raw is not NULL but the cast is;
* NULLs (NaN counts as NULL for floats), uniqueness (count - nunique), and every pandera
  Check -- tacit's `field(ge=..)` lowered to `Check.ge(..)` plus `field(checks=[...])`
  passed through -- become one `sum` each in ONE `aggregate()` query. The check
  expressions are built by pandera's own ibis check functions (`_check_fn`), as E10's
  hybrid does; checks whose output cannot be fused fall back to pandera (1 query each);
* only if something failed, ONE bounded `UNION ALL` query fetches up to 5 samples per issue;
* file-backed sources (`con.read_csv` / `read_parquet` ...) are coerced and materialised
  into a temp table once, so the checks and the rest of the pipeline do not re-scan the file.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

import ibis
import ibis.expr.datatypes as dt
import ibis.expr.operations as ops
import ibis.expr.types as ir

from ._errors import SAMPLE_LIMIT, Issue, ValidationError
from ._fields import FieldSpec

Extra = Literal["ignore", "forbid"]
_SEQ = [0]


def structural_issues(fields: Mapping[str, FieldSpec], schema: ibis.Schema, *, extra: Extra) -> list[Issue]:
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


def _file_backed(t: ir.Table) -> bool:
    return any(n.name.startswith("ibis_read_") for n in t.op().find(ops.DatabaseTable))


def _materialize(t: ir.Table) -> ir.Table:
    _SEQ[0] += 1
    con: Any = t.get_backend()
    return con.create_table(f"tacit_parsed_{_SEQ[0]}", t, temp=True)


def _pandera_ok(check: Any, t: ir.Table, name: str) -> tuple[ir.BooleanValue | None, bool | None]:
    """(row-level ok predicate, None) or (None, already-evaluated result) for one pandera Check."""
    import pandera.backends.ibis.builtin_checks  # noqa: F401  (registers pandera's ibis check fns)
    from pandera.api.checks import Check
    from pandera.api.ibis.types import IbisData

    fn = check._check_fn
    if (fname := getattr(fn, "__name__", None)) and Check.is_builtin_check(fname):
        fn = Check.get_builtin_check_fn(fname)
    out = fn(IbisData(t, name), **check._check_kwargs)
    if isinstance(out, bool):
        return None, out
    if isinstance(out, ir.Table) and isinstance(out.op(), ops.Project) and out.op().parent == t.op():
        out = out.op().values[out.columns[0]].to_expr()  # the projected boolean expression over t
    if isinstance(out, ir.BooleanColumn) and out.op().relations <= {t.op()}:
        return (out | t[name].isnull()) if check.ignore_na else out, None
    return None, bool(check(t, name).check_passed.execute())  # opaque output: pandera runs it (1 query)


def check_label(c: Any) -> str:
    return repr(c) if not hasattr(c, "_check_fn") else (c.error or c.name)


def parse_table(
    schema_name: str, fields: Mapping[str, FieldSpec], table: ir.Table, *,
    extra: Extra, context: str, coerce: bool = True,
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
        if coerce and f.dtype is not None and not f.accepts(have[f.name]):
            out_cols[f.name] = src[f.name].try_cast(f.physical())
            coerced[f.name] = (str(have[f.name]), str(f.physical()))
        else:
            out_cols[f.name] = src[f.name]
    staged = src.select(**{f"__src_{n}": src[n] for n in coerced}, **out_cols)
    if coerce and _file_backed(table):
        staged = _materialize(staged)
    result = staged.select(*out_cols)

    fails: dict[str, Any] = {}  # key -> failing-row count expression
    preds: dict[str, tuple[ir.BooleanValue | None, Issue]] = {}
    consts: list[Issue] = []

    def add(key: str, bad: ir.BooleanValue, issue: Issue) -> None:
        fails[key] = bad.fill_null(False).cast("int64").sum()
        preds[key] = (bad, issue)

    for f in fields.values():
        c = staged[f.name]
        if f.name in coerced:
            frm, to = coerced[f.name]
            add(f"coerce:{f.name}", staged[f"__src_{f.name}"].notnull() & c.isnull(), Issue("coercion", f.name, to, frm))
        if not f.nullable:
            nulls = c.isnull()
            if f.dtype is not None and f.dtype.is_floating():
                nulls = nulls | c.isnan()
            if f.name in coerced:  # don't double-report rows that failed coercion
                nulls = nulls & staged[f"__src_{f.name}"].isnull()
            add(f"null:{f.name}", nulls, Issue("null", f.name))
        if f.unique:
            fails[f"unique:{f.name}"] = c.count() - c.nunique()
            preds[f"unique:{f.name}"] = (None, Issue("unique", f.name))
        for i, cons in enumerate((*f.constraints, *f.checks)):
            check = cons.to_pandera() if hasattr(cons, "to_pandera") else cons
            ok, const = _pandera_ok(check, staged, f.name)
            issue = Issue("constraint", f.name, expected=check_label(cons))
            if ok is not None:
                add(f"c{i}:{f.name}", ~ok, issue)
            elif const is False:
                consts.append(issue)
    if not fails and not consts:
        return result
    counts = staged.aggregate(**fails).to_pyarrow().to_pylist()[0] if fails else {}
    failing = {k: int(n) for k, n in counts.items() if n}  # SUM over an empty table is NULL
    if not failing and not consts:
        return result

    parts: list[ir.Table] = []
    for key in failing:
        pred, issue = preds[key]
        assert issue.column is not None
        if issue.code == "null":  # sampling NULLs tells nothing
            continue
        if pred is None:  # unique: sample duplicated values
            name = issue.column
            dups = staged.group_by(name).aggregate(__n=staged[name].count()).filter(ibis._["__n"] > 1)
            parts.append(dups.select(__key=ibis.literal(key), __val=dups[name].cast("string")).limit(SAMPLE_LIMIT))
            continue
        col = f"__src_{issue.column}" if issue.code == "coercion" else issue.column
        bad = staged.filter(pred.fill_null(False))
        parts.append(bad.select(__key=ibis.literal(key), __val=bad[col].cast("string")).limit(SAMPLE_LIMIT))
    samples: dict[str, list[object]] = {}
    if parts:
        rows = (ibis.union(*parts, distinct=False) if len(parts) > 1 else parts[0]).to_pyarrow().to_pylist()
        for r in rows:
            samples.setdefault(r["__key"], []).append(r["__val"])
    out = [Issue(preds[k][1].code, preds[k][1].column, preds[k][1].expected, preds[k][1].actual, n,
                 tuple(samples.get(k, ()))) for k, n in failing.items()]
    raise ValidationError(schema_name, context, out + consts)
