# Constraints

[Schemas](schemas.md) declare column names and types. Constraints go further —
they express rules about the *values* in those columns: must be positive, must
be one of a fixed set, must match a pattern, can't be null.

Tacit delegates constraint validation entirely to
[pandera](https://pandera.readthedocs.io/) — anything pandera can check, tacit
can check. `tacit.Check` is a re-export of pandera's `Check` for convenience
(both work the same). You attach checks to columns using `Annotated`:

```python
from typing import Annotated
from tacit import Check, Nullable, Schema


class SensorReading(Schema):
    timestamp: str
    device_id: Annotated[str, Check.str_matches(r"^DEV-\d{4}$")]
    temperature: Annotated[float, Check.between(-40, 85)]
    humidity: Annotated[float, Check.ge(0), Check.le(100)]
    status: Annotated[str, Check.isin(["ok", "warn", "error"])]
    error_msg: Annotated[str, Nullable()]
```

Constraints are validated by `parse()` — pushed down to the engine as SQL. They
are skipped by `cast()`, which only checks structure.

For the full list of available checks, see
[pandera's Check API reference](https://pandera.readthedocs.io/en/stable/reference/generated/pandera.api.checks.Check.html).
Since tacit uses pandera's ibis backend, some checks that work with pandas may
not yet be available — see pandera's
[ibis backend support](https://pandera.readthedocs.io/en/stable/supported_libraries.html)
page for the current compatibility status (this is actively being expanded).

Below are examples of what you can do.

## Numeric checks

| Check | Alias | Example |
|-------|-------|---------|
| `Check.greater_than(v)` | `Check.gt(v)` | `Annotated[float, Check.gt(0)]` |
| `Check.greater_than_or_equal_to(v)` | `Check.ge(v)` | `Annotated[int, Check.ge(0)]` |
| `Check.less_than(v)` | `Check.lt(v)` | `Annotated[float, Check.lt(100)]` |
| `Check.less_than_or_equal_to(v)` | `Check.le(v)` | `Annotated[float, Check.le(1.0)]` |
| `Check.equal_to(v)` | `Check.eq(v)` | `Annotated[int, Check.eq(1)]` |
| `Check.not_equal_to(v)` | `Check.ne(v)` | `Annotated[int, Check.ne(0)]` |

These work on `int`, `float`, and `str` columns (where comparison is
lexicographic for strings).

## Range checks

`Check.between(lo, hi)` checks that values fall within a range (inclusive by
default):

```python
temperature: Annotated[float, Check.between(-40, 85)]
```

For exclusive bounds, use `Check.in_range()` with explicit flags:

```python
# 0 < score < 1 (exclusive on both ends)
score: Annotated[float, Check.in_range(0, 1, include_min=False, include_max=False)]
```

## Membership checks

| Check | Example |
|-------|---------|
| `Check.isin(values)` | `Annotated[str, Check.isin(["red", "green", "blue"])]` |
| `Check.notin(values)` | `Annotated[int, Check.notin([0, -1])]` |

Works with `str`, `int`, `float`, and `bool` values.

## String checks

| Check | Example | Notes |
|-------|---------|-------|
| `Check.str_startswith(s)` | `Annotated[str, Check.str_startswith("user_")]` | Literal prefix |
| `Check.str_endswith(s)` | `Annotated[str, Check.str_endswith(".csv")]` | Literal suffix |
| `Check.str_contains(p)` | `Annotated[str, Check.str_contains(r"@.+\.")]` | Regex search (unanchored) |
| `Check.str_matches(p)` | `Annotated[str, Check.str_matches(r"^[A-Z]{3}-\d{3}$")]` | Regex match (anchored to start) |
| `Check.str_length(...)` | `Annotated[str, Check.str_length(min_value=1, max_value=50)]` | Also supports `exact_value` |

!!! note "`str_contains` vs `str_matches`"

    Both accept regex patterns. `str_contains` searches anywhere in the string.
    `str_matches` anchors to the start — it prepends `^` if your pattern doesn't
    already start with one. For full-string matching, use
    `str_matches(r"^pattern$")`.

## Multiple checks per column

Stack multiple checks in `Annotated` — all are evaluated independently:

```python
class UserProfile(Schema):
    age: Annotated[int, Check.ge(0), Check.lt(200)]
    email: Annotated[str, Check.str_contains("@"), Check.str_length(min_value=5)]
    score: Annotated[float, Check.gt(0), Check.lt(1000), Check.ne(42.0)]
```

If any check fails, `parse()` raises a `SchemaError` naming the column, the
check, and the failing values.

## Nullable

By default, all columns are **not nullable** — null values cause `parse()` to
fail. Use `Nullable()` to allow them:

```python
from tacit import Nullable

class Event(Schema):
    event_type: str                                    # not nullable (default)
    payload: Annotated[str, Nullable()]                # nullable
    priority: Annotated[int, Nullable(allow=False)]    # explicitly not nullable
```

`Nullable()` combines with checks. Null rows are skipped during check
evaluation — only non-null values are tested:

```python
# Allows nulls, but non-null values must be positive
score: Annotated[float, Nullable(), Check.gt(0)]
```

## Custom checks

For validation logic that built-in checks don't cover, you can write custom
checks. The function receives each value and returns a boolean:

```python
def is_even(x: int) -> bool:
    return x % 2 == 0

class MySchema(Schema):
    count: Annotated[int, Check(is_even, element_wise=True)]
```

!!! warning "Lambdas don't work for element-wise checks"

    pandera wraps element-wise custom checks as ibis scalar UDFs, which require
    return type annotations. Lambdas lack these, so they raise
    `MissingReturnAnnotationError`. Use a named function with `-> bool` instead.

### Custom error messages

All checks accept an `error` parameter for clearer failure messages:

```python
age: Annotated[int, Check.ge(0, error="age must be non-negative")]
```

## Limitations

Since tacit delegates to pandera's ibis backend, you inherit its current
limitations:

- **No groupby or aggregate checks.** Checks that operate across groups or
  compute aggregates are not implemented in the ibis backend.
- **No statistical tests.** `one_sample_ttest`, `two_sample_ttest` etc. are
  defined on the `Check` class but have no ibis implementation.
- **`unique_values_eq` materializes data.** Unlike other checks that stay lazy,
  this one pulls distinct values into Python to compare sets.

These are pandera limitations, not tacit's — as pandera's ibis backend matures,
they'll become available automatically. Check pandera's
[ibis backend support](https://pandera.readthedocs.io/en/stable/supported_libraries.html)
page for the latest compatibility status.
