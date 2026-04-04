# ibis: Comparison operators reject Python scalars

**Status:** Proposed
**ibis version:** 12.0.0
**Severity:** Medium — affects every `Column < scalar` expression

## Observed symptoms

pyright reports `reportOperatorIssue` for any comparison between an ibis
column and a Python scalar:

```
Operator "<" not supported for types "Column" and "float"
Operator "<=" not supported for types "Column" and "Literal['1998-09-02']"
```

These operations work correctly at runtime. ibis coerces Python scalars
to ibis literals internally.

## Minimal reproduction

```python
# pyright_test.py
import ibis

t = ibis.table({"x": "float64"})

# FAILS: float is not a Value
r1 = t.x < 5.0  # reportOperatorIssue

# WORKS: Value < Value is fine
r2 = t.x < t.x  # no error

# WORKS: literal() returns a Value
r3 = t.x < ibis.literal(5.0)  # no error
```

Run: `pyright pyright_test.py`

## Root cause

Comparison operators on `Value` (`ibis/expr/types/generic.py`) only accept
`Value` as the `other` parameter:

```python
def __lt__(self, other: Value) -> ir.BooleanValue:
    return _binop(ops.Less, self, other)
```

Meanwhile, arithmetic operators on `NumericValue` (`ibis/expr/types/numeric.py`)
already accept Python scalars:

```python
Number = Union[int, float, Decimal]

def __add__(self, other: Number | NumericValue | ibis.Deferred) -> NumericValue:
    ...
```

The inconsistency is in the type annotations only. At runtime, `_binop`
handles coercion of Python scalars to ibis expressions for all operators.

## Proposed fix

Widen the `other` parameter on all six comparison operators in
`ibis/expr/types/generic.py` to accept Python scalars. The exact scalar
types should match what `_binop` coerces at runtime:

```python
if TYPE_CHECKING:
    from decimal import Decimal
    Scalar = Union[int, float, Decimal, str, bool, None]

def __lt__(self, other: Value | Scalar | ibis.Deferred) -> ir.BooleanValue:
    return _binop(ops.Less, self, other)

# Same for __le__, __gt__, __ge__, __eq__, __ne__
```

The exact union may need refinement based on what `_binop` actually accepts,
but the pattern should mirror what `NumericValue.__add__` already does.

**Affected methods (6):** `__eq__`, `__ne__`, `__lt__`, `__le__`, `__gt__`, `__ge__`

## Impact

This would fix all `reportOperatorIssue` errors involving scalar comparisons
for any pyright/mypy user of ibis, with no runtime behavior change.
