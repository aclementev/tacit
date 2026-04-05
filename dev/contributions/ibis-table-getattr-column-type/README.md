# ibis: Table.__getattr__ returns base Column, losing type specialization

**Status:** Documented (upstream design limitation)
**ibis version:** 12.0.0
**Severity:** High — affects all column arithmetic and aggregation

## Observed symptoms

pyright reports errors for arithmetic operators and aggregation methods on
columns accessed via `Table` attribute access:

```
Operator "/" not supported for types "Column" and "Column"
Cannot access attribute "sum" for class "Column"
Cannot access attribute "mean" for class "Column"
```

These operations work correctly at runtime because the actual objects are
`NumericColumn` instances, which have these methods.

## Minimal reproduction

```python
# pyright_test.py
import ibis
import ibis.expr.types as ir

t = ibis.table({"x": "float64", "y": "float64"})

# FAILS: t.x is Column, which lacks __truediv__ and .sum()
r1 = t.x / t.y     # reportOperatorIssue
r2 = t.x.sum()     # reportAttributeAccessIssue

# WORKS: explicit NumericColumn has everything
nc: ir.NumericColumn = t.x  # type: ignore
r3 = nc / nc        # NumericValue ✓
r4 = nc.sum()       # NumericScalar ✓
```

Run: `pyright pyright_test.py`

## Root cause

`Table.__getattr__` is typed to return the base `Column` class:

```python
# ibis/expr/types/relations.py
class Table(Expr):
    def __getattr__(self, key: str, /) -> ir.Column:
        ...
```

The ibis column type hierarchy:

```
Column → Value → Expr              (base: has __lt__, but no arithmetic)
NumericColumn → Column + NumericValue  (has __truediv__, .sum(), .mean())
StringColumn → Column + StringValue    (has .upper(), .contains(), etc.)
```

Since `__getattr__` returns the base `Column`, pyright cannot see methods
defined on `NumericValue` (`__truediv__`, `__mul__`, etc.) or
`NumericColumn` (`.sum()`, `.mean()`, etc.).

This is a design limitation, not a bug: ibis cannot determine the column's
specific type from the table schema at static analysis time. The schema
is a runtime value, not a type parameter.

## Why this is hard to fix

The fundamental issue is that `Table.__getattr__`'s return type depends
on runtime data (the column's dtype in the table schema). Options:

1. **Return a union type** (`NumericColumn | StringColumn | ...`): would
   eliminate the "attribute not found" errors but introduce false positives
   in the other direction (e.g., `.upper()` would appear valid on numeric
   columns). Also, operators between union types may not resolve cleanly.

2. **Generic typed tables** (`Table[schema]`): would require ibis to
   adopt a schema-as-type-parameter approach (similar to what tacit does
   with `DataFrame[S]`), plus a `__getattr__` that's overloaded per-field.
   This would be a massive redesign of ibis's type system.

3. **Type stubs / plugin**: a pyright plugin or partial stubs could override
   `__getattr__` to return `Any` instead of `Column`, which would suppress
   errors at the cost of losing all type inference on column expressions.

None of these are practical upstream contributions at this time.

## Recommended workaround

Users should add to their `pyproject.toml`:

```toml
[tool.pyright]
reportOperatorIssue = false
reportAttributeAccessIssue = false
```

This is what the ibis community already does. These rules only affect ibis
column expressions in practice — tacit's own types are checked separately
via `tests/typechecking/`.
