"""One-query validation over narwhals expressions (E10's hybrid, narwhals flavour).

Every check becomes `failing_mask.cast(Int64).sum()`; all of them go into ONE `select`, collected
once. Booleans are cast before summing because narwhals' `bool.sum()` fails on Spark and Postgres.
Only when something fails, a second bounded query fetches sample values.
pandera Checks in `field(checks=[...])` run through pandera's narwhals builtin implementations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import narwhals.stable.v2 as nw

STATS = {"queries": 0}


@dataclass
class Issue:
    code: str
    column: str | None = None
    detail: str = ""
    count: int | None = None
    samples: list[Any] | None = None

    def __str__(self) -> str:
        s = f"{self.column}: {self.code}" + (f" {self.detail}" if self.detail else "")
        if self.count is not None:
            s += f"; {self.count} rows"
        if self.samples:
            s += f"; e.g. {self.samples}"
        return s


class ValidationError(Exception):
    def __init__(self, schema: str, context: str, issues: list[Issue]) -> None:
        self.schema, self.context, self.issues = schema, context, issues
        super().__init__(f"{context}: {len(issues)} issue(s) for {schema}\n" + "\n".join(f"  - {i}" for i in issues))


def _masks(fields: dict[str, Any]) -> list[tuple[str, str, nw.Expr]]:
    """(column, check-name, FAILING-row mask) for every declared check."""
    out: list[tuple[str, str, nw.Expr]] = []
    for f in fields.values():
        c = nw.col(f.name)
        if not f.nullable:
            out.append((f.name, "not_null", c.is_null()))
        ok = c.is_null()  # checks ignore nulls (pandera's ignore_na=True default)
        if f.ge is not None:
            out.append((f.name, f"ge({f.ge})", ~(ok | (c >= f.ge))))
        if f.le is not None:
            out.append((f.name, f"le({f.le})", ~(ok | (c <= f.le))))
        if f.gt is not None:
            out.append((f.name, f"gt({f.gt})", ~(ok | (c > f.gt))))
        if f.lt is not None:
            out.append((f.name, f"lt({f.lt})", ~(ok | (c < f.lt))))
        if f.isin is not None:
            out.append((f.name, f"isin({f.isin})", ~(ok | c.is_in(f.isin))))
        if f.pattern is not None:
            out.append((f.name, f"pattern({f.pattern!r})", ~(ok | c.str.contains(f.pattern))))
        if f.length is not None:
            out.append((f.name, f"length({f.length})", ~(ok | (c.str.len_chars() == f.length))))
        for ck in f.checks:  # pandera Check -> pandera's narwhals builtin (nw.Expr -> nw.Expr)
            from pandera.api.checks import Check

            import pandera.backends.narwhals.builtin_checks  # noqa: F401

            fn = Check.get_builtin_check_fn(ck._check_fn.__name__)  # private: _check_fn/_check_kwargs (as E10)
            out.append((f.name, str(ck.error or ck.name), ~(ok | fn(c, **ck._check_kwargs))))
    return out


def _rows(lf: nw.LazyFrame[Any]) -> list[dict[str, Any]]:
    try:
        return lf.collect().rows(named=True)
    except NotImplementedError:  # sqlframe engines without Arrow (postgres): native row API
        return [r.asDict() for r in nw.to_native(lf).collect()]


def fused_validate(lf: nw.LazyFrame[Any], fields: dict[str, Any], n_samples: int = 3) -> list[Issue]:
    masks = _masks(fields)
    # when/then/otherwise rather than cast(Int64): ibis-postgres cannot cast boolean to bigint
    aggs = [nw.when(m).then(nw.lit(1)).otherwise(nw.lit(0)).sum().alias(f"k{i}") for i, (_c, _n, m) in enumerate(masks)]
    for f in fields.values():
        if f.unique:
            aggs.append((nw.len() - nw.col(f.name).n_unique()).alias(f"u_{f.name}"))
    if not aggs:
        return []
    STATS["queries"] += 1
    row = _rows(lf.select(*aggs))[0]
    issues: list[Issue] = []
    for i, (col, name, m) in enumerate(masks):
        n = row[f"k{i}"] or 0
        if n:
            STATS["queries"] += 1
            samples = [r[col] for r in _rows(lf.filter(m).select(col).head(n_samples))]
            issues.append(Issue(name, col, count=int(n), samples=samples))
    for f in fields.values():
        if f.unique and row.get(f"u_{f.name}"):
            issues.append(Issue("unique", f.name, count=int(row[f"u_{f.name}"])))
    return issues
