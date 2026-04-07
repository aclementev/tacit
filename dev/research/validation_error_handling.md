# Validation Error Handling Spike

**Date**: 2026-04-07
**Issue**: #35
**Verdict**: Prefer a small tacit exception hierarchy rooted in a common
`TacitValidationError`, while preserving the original pandera/backend exception
as the cause instead of trying to normalize every engine-specific detail.

---

## The question

How should tacit expose validation failures so that users can reliably identify
and handle them, without re-implementing the full error surface of pandera,
ibis, and every backend engine?

This question matters because tacit's primary value proposition is *clear,
useful failures at data boundaries*. Today, the error surface is split:

- structural checks in tacit raise `ValueError` / `TypeError`
- constraint and schema failures from pandera raise `SchemaError`
- coercion failures from `ibis.Table.cast()` raise backend-specific exceptions
  like DuckDB's `ConversionException`
- `@contract(validate=True)` currently lets those raw exceptions through without
  adding parameter/return-value context

The result is informative in some cases, but not stable enough to serve as an
API for users who want to catch and handle validation errors.

## Goals

1. Give users a reliable way to identify the *kind* of failure.
2. Preserve boundary context: which tacit operation failed, against which
   schema, and for which contract parameter/return value.
3. Preserve the useful low-level details from pandera/backend exceptions.
4. Keep the design small enough that tacit does not become an error-normalizing
   framework for every ibis backend.

## Non-goals

1. Re-implement every pandera or backend exception class.
2. Promise a portable, engine-agnostic error message string.
3. Normalize all failure-case payloads into one schema.
4. Hide backend details that are useful for debugging real pipelines.

## Important project context

Backward compatibility is **not** a meaningful constraint for this decision.
Tacit is still pre-stable and does not have an established user base that would
justify carrying forward a weaker API just to avoid breakage.

That means the design should optimize for the best long-term public exception
API, not for preserving today's ad hoc mix of `ValueError`, `TypeError`,
`SchemaError`, and backend exceptions.

## Current tacit behavior

### High-level failure matrix

| Scenario | Where it fails today | What the user sees |
|---|---|---|
| Missing/extra columns in `cast()` / `parse()` | tacit `_check_columns()` | `ValueError` |
| Wrong dtype in `cast()` | tacit `cast()` | `TypeError` |
| Coercion failure in `parse()` | `ibis.Table.cast()` / backend execution | backend-specific exception |
| Constraint/nullability/check failure in `parse()` | pandera ibis backend | `pandera.errors.SchemaError` |
| Multiple pandera failures with `lazy=True` | pandera ibis backend | `pandera.errors.SchemaErrors` |
| Custom pandera check crashes | pandera wraps it | `pandera.errors.SchemaError` with `reason_code=CHECK_ERROR` |
| `@contract(validate=True)` failure | raw exception bubbles through | no contract-specific context |

### Why this split exists

Tacit performs **structural** checks itself, but it performs **coercion** via
`ibis.Table.cast()` before handing off **data validation** to pandera:

```python
target = cls._ibis_schema()
actual = table.schema()
cls._check_columns(target, actual)

cast_map = {col: target_type for col, target_type in target.items() if actual[col] != target_type}
if cast_map:
    table = table.cast(cast_map)

validated = cls._pandera_schema().validate(table)
```

Source: [src/tacit/schema.py](../../src/tacit/schema.py)

That means:

- missing/extra columns are controlled by tacit
- successful casts disappear
- failed casts are backend execution failures, not pandera failures
- pandera only sees the post-cast table

This is the single most important fact shaping the design.

## Evidence

### 1. Pandera's Ibis backend already has structured validation errors

Pandera documents that Ibis validation raises `SchemaError` eagerly and
`SchemaErrors` with `lazy=True`:

- Pandera Ibis guide:
  <https://pandera.readthedocs.io/en/stable/ibis.html>
- Pandera lazy validation guide:
  <https://pandera.readthedocs.io/en/stable/lazy_validation.html>
- Pandera error classes:
  <https://pandera.readthedocs.io/en/stable/reference/generated/pandera.errors.SchemaError.html>
  and
  <https://pandera.readthedocs.io/en/stable/reference/generated/pandera.errors.SchemaErrors.html>

Pandera's `SchemaError` is not just a message; it carries structured fields:

- `reason_code`
- `failure_cases`
- `check`
- `check_output`
- `column_name`
- `schema`

Local source:

- `.venv/lib/python3.12/site-packages/pandera/errors.py`
- `.venv/lib/python3.12/site-packages/pandera/backends/ibis/container.py`
- `.venv/lib/python3.12/site-packages/pandera/backends/ibis/components.py`

Important nuance: for the Ibis backend, `column_name` is often `None`, even
when the error message clearly identifies a column. The useful structured
fields are `reason_code`, `check`, and `failure_cases`.

### 2. Coercion failures do *not* come from pandera in tacit's flow

Pandera's Ibis docs say parsers apply `coerce=True` as part of validation, but
in the installed `pandera 0.30.1` Ibis backend, `coerce=True` did not coerce in
practice in local testing:

```python
schema = pa.DataFrameSchema({"a": pa.Column(float, coerce=True)})
schema.validate(ibis.memtable({"a": [1, 2]}))
# SchemaError: expected column 'a' to have type float64, got int64
```

Tacit therefore correctly performs coercion itself today. But once tacit calls
`table.cast(...)`, any failure is whatever the backend chooses to raise. With
DuckDB, the observed type was `_duckdb.ConversionException`.

This means coercion failure is *not* something tacit can reliably identify by
matching a specific exception class across backends.

### 3. Pandera's lazy mode is useful, but tacit does not currently use it

Pandera's Ibis backend can aggregate multiple failures into `SchemaErrors`,
including multiple checks on multiple columns. The aggregated object contains:

- `schema_errors`: a list of `SchemaError`
- `failure_cases`: a consolidated failure table
- `message`: a grouped error report

This is useful evidence for future API design, but tacit currently calls
`validate(..., lazy=False)` implicitly via `schema.validate(table)`.

### 4. Pandera distinguishes failure reasons more reliably than message text

Observed `reason_code` values from local experiments:

- `COLUMN_NOT_IN_DATAFRAME`
- `COLUMN_NOT_IN_SCHEMA`
- `WRONG_DATATYPE`
- `SERIES_CONTAINS_NULLS`
- `DATAFRAME_CHECK`
- `CHECK_ERROR`

This is a better hook for a tacit API than parsing human-readable strings.

### 5. `@contract(validate=True)` is the main place where tacit must add value

Users need contract context that pandera/backend exceptions do not know about:

- was this a function input or output?
- which parameter?
- which schema was being enforced?

This is tacit's unique information, and it should be added consistently even if
the underlying error remains a pandera or backend exception.

## Local experiments

Script:
[validation_error_scenarios.py](validation_error_scenarios.py)

Run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python dev/research/validation_error_scenarios.py
```

### Key observed shapes

#### `tacit.parse()` coercion failure

```text
type: _duckdb.ConversionException
message: Conversion Error: Could not convert string 'bad' to DOUBLE ...
```

Takeaway: backend-specific, rich, not something tacit should try to rewrite into
a fake portable message.

#### `tacit.parse()` constraint failure

```text
type: pandera.errors.SchemaError
reason_code: SchemaErrorReason.DATAFRAME_CHECK
check: <Check greater_than_or_equal_to ...>
failure_cases: pandas.DataFrame
```

Takeaway: pandera already exposes a meaningful structured error surface.

#### Pandera eager wrong dtype

```text
type: pandera.errors.SchemaError
reason_code: SchemaErrorReason.WRONG_DATATYPE
check: "dtype('float64')"
failure_cases: 'string'
```

Takeaway: wrong-dtype validation inside pandera is already categorized.

#### Pandera lazy aggregated errors

```text
type: pandera.errors.SchemaErrors
schema_errors: list[SchemaError]
```

Takeaway: if tacit ever opts into `lazy=True`, there is already a structured
aggregate shape to preserve.

#### Custom check execution error

```text
type: pandera.errors.SchemaError
reason_code: SchemaErrorReason.CHECK_ERROR
failure_cases: 'ZeroDivisionError("division by zero")'
```

Takeaway: pandera already distinguishes "validation failed" from "check code
itself blew up".

## What users usually need to handle

From a pipeline user's perspective, the handling needs are coarse:

1. **Structural contract mismatch**
   The table shape is wrong: missing columns, extra columns, wrong dtypes in
   `cast()`.

2. **Coercion failure**
   The source data cannot be converted into the declared schema types.

3. **Constraint validation failure**
   The data has the right shape but violates declared checks/nullability.

4. **Validation/check execution failure**
   A custom check or backend operation failed for reasons other than "bad data".

5. **Boundary context**
   Did this happen in `Schema.parse()`, in a contract input, or in a contract
   output?

Users generally do **not** need tacit to normalize:

- every backend exception class
- every backend message format
- every `failure_cases` payload into a single table shape

## Candidate designs

### Option A: Keep raw exceptions, only improve docs

Behavior:

- `cast()` keeps raising `ValueError` / `TypeError`
- `parse()` keeps surfacing `SchemaError` and backend exceptions
- `@contract(validate=True)` maybe prefixes the message, but no new exception API

Pros:

- minimal implementation
- preserves maximum detail
- no backward-compatibility story to manage

Cons:

- no stable error API
- users must catch a grab-bag of exception types
- contract context remains weak unless tacit rewrites messages ad hoc

Verdict: too weak for tacit's value proposition.

### Option B: Single tacit wrapper with coarse category metadata

Behavior:

- `parse()` / `cast()` / `@contract` raise a tacit exception type
- the tacit exception carries coarse structured metadata
- the original pandera/backend exception is preserved as `__cause__` and/or an
  explicit `original` attribute

Possible fields:

```python
class ValidationKind(Enum):
    STRUCTURAL = "structural"
    COERCION = "coercion"
    CONSTRAINT = "constraint"
    CHECK_EXECUTION = "check_execution"
    UNKNOWN = "unknown"

class ValidationPhase(Enum):
    CAST = "cast"
    PARSE = "parse"
    CONTRACT_INPUT = "contract_input"
    CONTRACT_OUTPUT = "contract_output"

class TacitValidationError(Exception):
    kind: ValidationKind
    phase: ValidationPhase
    schema: type[Schema]
    boundary_label: str | None
    reason_code: str | None
    column: str | None
    check: object | None
    failure_cases: object | None
    original: BaseException
```

Pros:

- one stable catch point for users
- preserves tacit's unique context
- avoids re-implementing backend detail
- works for both pandera and backend exceptions

Cons:

- changes public exception behavior
- needs careful compatibility story
- users who currently catch `SchemaError` directly would need migration help

Verdict: workable, but less Pythonic than a small hierarchy if tacit is ready
to commit to a few stable categories.

### Option C: Small hierarchy of tacit exceptions

Behavior:

- `TacitValidationError` as the common base
- `TacitStructuralError`
- `TacitCoercionError`
- `TacitConstraintError`
- `TacitCheckExecutionError`

Potentially no `Unknown` subclass at first. If tacit cannot classify a failure
confidently, it can raise the base `TacitValidationError`.

Pros:

- very explicit `except` blocks
- no need to inspect `.kind`
- aligns with Python's built-in exception handling model
- allows subtype-specific fields later if the API needs them
- gives type checkers/editors a natural narrowing model

Cons:

- more public API surface than a single wrapper
- requires discipline to avoid inventing too many subclasses
- still needs a fallback strategy for ambiguous failures

Verdict: best fit if tacit wants a stable public handling API now, provided the
hierarchy stays intentionally small.

### Option D: Hybrid, but contract-only wrapping

Behavior:

- `Schema.parse()` keeps current raw exceptions
- `@contract(validate=True)` wraps them with contract context

Pros:

- minimal disruption
- fixes the most obvious UX hole

Cons:

- `Schema.parse()` still lacks a stable handling API
- users get different exception models depending on how they invoke tacit

Verdict: better than today, but still fragmented.

## Recommendation

Recommend **Option C** with a deliberately small hierarchy:

```python
class TacitError(Exception):
    pass


class TacitValidationError(TacitError):
    schema: type[Schema]
    phase: ValidationPhase
    boundary_label: str | None
    original: BaseException
    reason_code: str | None
    check: object | None
    failure_cases: object | None
    column: str | None


class TacitStructuralError(TacitValidationError):
    pass


class TacitCoercionError(TacitValidationError):
    pass


class TacitConstraintError(TacitValidationError):
    pass


class TacitCheckExecutionError(TacitValidationError):
    pass
```

If tacit cannot classify a failure confidently, it should raise the base
`TacitValidationError` rather than inventing more subclasses too early.

This best matches the stated goal:

- users get a stable API for identification and handling
- users can write direct, idiomatic `except TacitCoercionError` blocks
- tacit adds the context only tacit knows
- pandera/backend details remain available
- tacit avoids pretending it can normalize all engine failures

### Recommended invariants

1. Any validation failure originating from `Schema.cast`, `Schema.parse`, or
   `@contract` should be catchable as `TacitValidationError`.
2. The original exception should always be available via `__cause__` and an
   explicit attribute like `.original`.
3. Tacit should preserve boundary metadata (`schema`, `phase`,
   `boundary_label`) regardless of the subclass.
4. For pandera-backed errors, tacit should preserve `reason_code`, `check`, and
   `failure_cases` on a best-effort basis.
5. Tacit should only use specialized subclasses when it can classify the
   failure confidently from its own control flow or from stable pandera reason
   codes.

### Practical mapping

| Source | Recommended tacit exception |
|---|---|
| tacit missing/extra/wrong type in `cast()` | `TacitStructuralError` |
| failure during tacit's own pre-validation cast step | `TacitCoercionError` |
| `SchemaError` with `reason_code=CHECK_ERROR` | `TacitCheckExecutionError` |
| other `SchemaError` / `SchemaErrors` from pandera validation | `TacitConstraintError` |
| unexpected or ambiguous failure during validation | `TacitValidationError` |

This is intentionally coarse. The original exception retains the full detail.

### Why this is preferable to a `.kind` field

The `.kind` approach is mostly equivalent in expressiveness, but a small
hierarchy is more natural in Python:

- `except TacitCoercionError` is cleaner than `except TacitValidationError as e`
  followed by `if e.kind == ...`
- subtype-specific fields can be added later without turning the base class into
  a pile of optional attributes
- editors and type checkers can narrow by exception class more naturally than by
  runtime metadata

The main argument against the hierarchy is taxonomy churn. The solution is not
to flatten everything into `.kind`; it is to keep the hierarchy small and use
the base class as the fallback for ambiguous cases.

## Compatibility options

If backward compatibility is a concern, there are two plausible rollouts:

### Rollout 1: Introduce tacit exceptions everywhere

- change `parse()` / `cast()` / `@contract` to raise tacit exceptions now
- preserve original exception as cause
- document the migration

### Rollout 2: Introduce opt-in wrapping first

- add `wrap_errors=True` or a config flag
- transition docs/examples first
- make it default later

Given tacit's current stage, **Rollout 1** is the recommended path. There is no
meaningful installed base to protect, so the project should adopt the cleaner
exception API directly instead of introducing temporary compatibility layers.

## What tacit should not try to normalize

1. Backend exception classes across DuckDB, BigQuery, Snowflake, etc.
2. The textual message format of engine exceptions.
3. Exact `failure_cases` shapes across pandera failure modes.
4. Every possible backend execution failure into a large inheritance tree.

Those are the places where normalization becomes a fool's errand.

## Suggested next implementation steps

1. Define the exception classes and stable metadata fields.
2. Decide which subclass-specific fields, if any, should exist at v1.
3. Update `@contract(validate=True)` first so contract context is always added.
4. Update `Schema.parse()` / `Schema.cast()` to emit the same exception family.
5. Add tests for:
   - contract input/output validated failures
   - coercion failure classification
   - constraint failure classification
   - preservation of original exception as cause

## References

### Local source

- [src/tacit/schema.py](../../src/tacit/schema.py)
- [src/tacit/contract.py](../../src/tacit/contract.py)
- [.venv/lib/python3.12/site-packages/pandera/errors.py](../../.venv/lib/python3.12/site-packages/pandera/errors.py)
- [.venv/lib/python3.12/site-packages/pandera/backends/ibis/container.py](../../.venv/lib/python3.12/site-packages/pandera/backends/ibis/container.py)
- [.venv/lib/python3.12/site-packages/pandera/backends/ibis/components.py](../../.venv/lib/python3.12/site-packages/pandera/backends/ibis/components.py)

### Official docs

- Pandera Ibis guide:
  <https://pandera.readthedocs.io/en/stable/ibis.html>
- Pandera lazy validation:
  <https://pandera.readthedocs.io/en/stable/lazy_validation.html>
- Pandera `SchemaError`:
  <https://pandera.readthedocs.io/en/stable/reference/generated/pandera.errors.SchemaError.html>
- Pandera `SchemaErrors`:
  <https://pandera.readthedocs.io/en/stable/reference/generated/pandera.errors.SchemaErrors.html>

### Research script

- [validation_error_scenarios.py](validation_error_scenarios.py)
