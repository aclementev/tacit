"""Q5: lazy validation embedded in the expression graph (duckdb `error()` inside a filter predicate).

guard(tc, plan) returns  tc.filter(CASE WHEN <bad1> THEN error('..') WHEN <bad2> THEN error('..') ... ELSE TRUE END)
so validation runs *fused with whatever query the user eventually runs* -- no separate pass, no extra query.
"""
import ibis, ibis.expr.types as ir
from ibisval import build_plan, _prepare

@ibis.udf.scalar.builtin(name="error")
def _error(msg: str) -> bool: ...          # DuckDB error(msg): aborts the query with msg


def guard(schema_cls, t: ir.Table, plan=None, *, unique=(), coerce=False) -> ir.Table:
    plan = plan or build_plan(schema_cls, list(unique))
    tc, coerced = _prepare(schema_cls, t, coerce)
    arms = []
    for col in schema_cls._fields:
        if col in coerced:
            arms.append((tc[f"__raw_{col}"].notnull() & tc[col].isnull(),
                         _error(ibis.literal(f"tacit: cannot coerce {col}: ") + tc[f"__raw_{col}"])))
        if not plan.nullable[col]:
            arms.append((tc[col].isnull(), _error(f"tacit: column '{col}' is null")))
    for it in plan.items:
        arms.append(((~it.pred(tc)).fill_null(False),
                     _error(ibis.literal(f"tacit: {it.column} failed {it.name}; first bad value: ") + tc[it.column].cast("string"))))
    for col in plan.unique:   # needs a second pass over the data: scalar subquery (count - count distinct)
        arms.append((tc.count() - tc[col].nunique() > 0, _error(f"tacit: column '{col}' is not unique")))
    ok = ibis.cases(*arms, else_=True)
    out = tc.filter(ok)
    return out.drop(*[c for c in out.columns if c.startswith("__raw_")]) if coerced else out
