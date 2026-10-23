"""Hybrid, narwhals flavour: fuse pandera's *narwhals* builtin checks (nw.Expr -> nw.Expr) into one select.

This is the shape pandera is converging on (spec #2401: the ibis API becomes a shim over the narwhals
backend, builtins are pure `nw.Expr` functions). If that lands, the batching can live upstream in
`pandera/backends/narwhals/` with no ibis-specific code.

usage: uv run --frozen --with narwhals python hybrid_nw.py
"""
import sys
import warnings

import narwhals.stable.v1 as nw

import pandera.backends.narwhals.builtin_checks  # noqa: F401  registers nw.Expr implementations
from pandera.api.checks import Check

warnings.simplefilter("ignore")


def fused_counts(schema, table):
    """One query: failing-row count per (column, check) for builtin column checks + nullability."""
    lf = nw.from_native(table)
    aggs, keys = [], []
    for name, col in schema.columns.items():
        c = nw.col(name)
        if not col.nullable:
            isna = c.is_null()
            if col.dtype is not None and str(col.dtype).startswith("float"):
                isna = isna | c.is_nan()
            aggs.append(isna.cast(nw.Int64).sum().alias(f"k{len(keys)}"))
            keys.append((name, "not_nullable"))
        for ck in col.checks:
            fn = Check.get_builtin_check_fn(ck._check_fn.__name__)   # Dispatcher -> nw.Expr impl
            ok = fn(c, **ck._check_kwargs)
            if ck.ignore_na:
                ok = ok | c.is_null()
            aggs.append((~ok).cast(nw.Int64).sum().alias(f"k{len(keys)}"))
            keys.append((name, ck.error))
    row = nw.to_native(lf.select(*aggs)).to_pyarrow().to_pylist()[0]
    return {keys[int(k[1:])]: v for k, v in row.items() if v}


if __name__ == "__main__":
    sys.path.insert(0, "../e4-runtime")
    from common import Customer, log_queries, log_reset, make_con

    import hybrid

    con, t = make_con(100_000, bad_rate=0.001)
    schema = Customer._pandera_schema()
    tc = t.cast({"created": "timestamp"})
    log_reset(con)
    got = fused_counts(schema, tc)
    print("narwhals-fused queries:", len(log_queries(con)))
    rep = hybrid.validate(schema, tc, n_samples=0)
    ref = {(f.column, f.check): f.count for f in rep.failures}
    print("narwhals-fused:", got)
    print("ibis hybrid   :", ref)
    print("PARITY" if got == ref else "DIFF")
