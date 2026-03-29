# PRD: tacit v0

**Goal:** Ship a usable library where users can define schemas as Python classes,
validate DataFrames at pipeline boundaries, and get type safety from pyright —
all backed by ibis (execution) and pandera (validation).

**Design:** [DESIGN.md](DESIGN.md)
**Testing strategy:** [research/TESTING.md](research/TESTING.md)
**Research:** [research/SUMMARY.md](research/SUMMARY.md)

## Acceptance criteria (v0)

From DESIGN.md:

1. Iris ML pipeline example works end-to-end with schema validation
2. TPC-H Q1 example works end-to-end with `@tacit.contract`
3. Both run against DuckDB via ibis
4. Editor autocomplete on `df.column_name` inside transformations
5. Clear, actionable errors on validation failure (wrong type, missing column,
   constraint violation)


---


## Milestones

### M1: Structural contracts end-to-end

**Goal:** Define a schema, load data, `cast()` it, get a typed `DataFrame[S]`,
use ibis API on it. Pyright catches forgetting `cast()`.

This is the thinnest possible vertical slice that proves the core value prop:
type safety via structural contracts. No validation, no pandera yet — just
schema metadata checks and the type system doing its job.

**What works after M1:**

```python
import tacit

class Iris(tacit.Schema):
    sepal_length: float
    species: str

raw = ibis.memtable({"sepal_length": [5.1], "species": ["setosa"]})
df = Iris.cast(raw)        # ✓ structural check, returns DataFrame[Iris]
df.sepal_length             # ✓ ibis column expression
df.mutate(x=1)             # ✓ returns ibis.Table (schema drops off)

# pyright catches:
def bad(t: ir.Table) -> tacit.DataFrame[Iris]:
    return t               # ✗ type error: Table ≠ DataFrame[Iris]
```

**Acceptance criteria:**
- Schema class collects fields from annotations (including inheritance)
- `cast()` accepts valid tables, rejects missing/extra/wrong-type columns
- `DataFrame[S]` is an ibis Table (isinstance, full API works)
- ibis operations drop back to plain Table
- pyright enforces contracts (tested via typechecking/ suite)
- Error messages name the specific columns and types involved

**Tickets:**

#### T1: Test infrastructure and project setup
**Type:** feature
**Depends on:** none

Set up the test skeleton so all subsequent tickets can write tests from the start.

- [ ] Add `pyright>=1.1.400` to dev dependencies
- [ ] Create `tests/conftest.py` with DuckDB fixtures and sample data helpers
- [ ] Create `tests/typechecking/pyproject.toml` with pyright config
      (`reportUnnecessaryTypeIgnoreComment = true`, `reportOperatorIssue = false`)
- [ ] Create `tests/test_typecheck.py` — pytest wrapper that shells out to pyright
- [ ] Verify `uv run pytest tests/test_typecheck.py` runs (even if typechecking/
      has no files yet — should pass vacuously or be skipped)

#### T2: Schema base class
**Type:** feature
**Depends on:** T1

The foundation: define schemas as Python classes, get field metadata out.

- [ ] `Schema.__init_subclass__` collects fields via `get_type_hints`
- [ ] `Schema._get_fields()` returns `{name: type}` mapping
- [ ] Inheritance works: `Child._get_fields()` includes parent fields
- [ ] `Schema._ibis_schema()` maps Python types to ibis types
      (`float→float64`, `int→int64`, `str→string`, `bool→boolean`)
- [ ] `__init__.py` exports `Schema`
- [ ] `tests/test_schema.py` covers all the above

#### T3: DataFrame[S] and cast()
**Type:** feature
**Depends on:** T2

The typed DataFrame and the structural boundary check.

- [ ] `DataFrame` subclasses `ir.Table` with `Generic[S]`
- [ ] `DataFrame._from_table()` wraps an ibis Table
- [ ] `Schema.cast(table)` checks columns/types against ibis metadata,
      returns `DataFrame[S]`
- [ ] `cast()` rejects missing columns — error names the missing columns
- [ ] `cast()` rejects extra columns (strict) — error names the extras
- [ ] `cast()` rejects wrong types — error names column, expected vs actual
- [ ] `cast()` does not execute queries (metadata only)
- [ ] `isinstance(df, ir.Table)` is True
- [ ] ibis operations on DataFrame return plain `ir.Table`
- [ ] `__init__.py` exports `DataFrame`
- [ ] `tests/test_dataframe.py` covers DataFrame identity and transparency
- [ ] `tests/test_parse.py` covers cast() (happy path + error cases with
      message assertions)

#### T4: Type safety tests
**Type:** feature
**Depends on:** T3

Prove the core value prop mechanically: pyright catches contract violations.

- [ ] `tests/typechecking/check_safety.py` — can't forget cast/parse
- [ ] `tests/typechecking/check_invariance.py` — DataFrame[A] ≠ DataFrame[B]
- [ ] `tests/typechecking/check_transparent.py` — DataFrame[S] usable as ir.Table
- [ ] `uv run pytest tests/test_typecheck.py` passes (pyright exit code 0)


---


### M2: Validated pipelines

**Goal:** `parse()` validates data against the engine (coercion + pandera checks),
iris pipeline example works end-to-end.

Builds on M1's structural contracts by adding runtime validation — the "parse at
boundaries" workflow.

**What works after M2:**

```python
raw = con.read_csv("iris.csv")       # string columns from CSV
iris = Iris.parse(raw)                # coerces types + validates → DataFrame[Iris]

features = engineer_features(iris)    # ibis transformations
result = IrisFeatures.cast(features)  # structural check at internal boundary
```

**Acceptance criteria:**
- `parse()` coerces column types via ibis `.cast()` before validation
- `parse()` validates with pandera (checks pushed to engine as SQL)
- `parse()` returns `DataFrame[S]`
- `parse()` rejects invalid data with clear errors (column name, expected vs actual)
- Iris pipeline example (`examples/iris_pipeline.py`) runs end-to-end
- Example is tested in `tests/test_examples.py`

**Tickets:**

#### T5: parse() with pandera validation
**Type:** feature
**Depends on:** T3

The full boundary parsing operation: coerce types + validate + wrap.

- [ ] `Schema._pandera_schema()` generates `pandera.DataFrameSchema` from fields
      with `strict=True`
- [ ] `Schema.parse(table)` coerces column types via `ibis.Table.cast()` then
      validates with pandera
- [ ] `parse()` returns `DataFrame[S]` on success
- [ ] `parse()` rejects missing columns — error names the columns
- [ ] `parse()` rejects extra columns — error names the columns
- [ ] `parse()` handles type coercion (e.g., `int64` → `float64`)
- [ ] `parse()` rejects data that fails pandera checks — error is actionable
- [ ] `tests/test_parse.py` covers parse() happy path + error cases

#### T6: Iris pipeline example
**Type:** feature
**Depends on:** T5

Make the iris example runnable and tested.

- [ ] `examples/iris_pipeline.py` runs successfully against DuckDB
- [ ] `engineer_features()` and `predict()` use cast() at boundaries
      (or pipeline uses parse() at outer boundaries + cast() internally)
- [ ] `tests/test_examples.py::test_iris_pipeline` — runs pipeline, asserts
      result shape, column names, and output values
- [ ] Example data in `examples/data/` is sufficient


---


### M3: Contracts and TPC-H

**Goal:** `@tacit.contract` decorator automates boundary checks. TPC-H example
works, completing all v0 acceptance criteria except constraints.

**What works after M3:**

```python
@tacit.contract
def pricing_summary(lineitem: tacit.DataFrame[LineItem]) -> tacit.DataFrame[PricingSummary]:
    return lineitem.filter(...).group_by(...).agg(...)
    # decorator calls cast() on input and output automatically
```

**Acceptance criteria:**
- `@tacit.contract` inspects function annotations for `DataFrame[S]` params
- Calls `cast()` on inputs and outputs by default
- With `validate=True`, calls `parse()` instead
- Non-DataFrame parameters pass through unchanged
- TPC-H Q1 example runs end-to-end with `@tacit.contract`
- Type checking tests for contract-decorated functions

**Tickets:**

#### T7: @tacit.contract decorator
**Type:** feature
**Depends on:** T5

Runtime decorator that enforces schema contracts at function boundaries.

- [ ] Inspects function type annotations via `get_type_hints()`
- [ ] Identifies `DataFrame[S]` parameters and return type
- [ ] Calls `Schema.cast()` on DataFrame inputs and output by default
- [ ] With `validate=True`, calls `Schema.parse()` instead
- [ ] Non-DataFrame params/returns are passed through unchanged
- [ ] Clear error when contract is violated (names the parameter and schema)
- [ ] `__init__.py` exports `contract`
- [ ] `tests/test_contract.py` covers: default behavior, validate=True,
      mixed params, error cases

#### T8: TPC-H example and contract type checks
**Type:** feature
**Depends on:** T7

Complete the second example and add type checking for decorated functions.

- [ ] `examples/tpch_q1.py` runs successfully against DuckDB
- [ ] Example data generated or provided in `examples/data/`
- [ ] `tests/test_examples.py::test_tpch_q1` — runs query, asserts result
      shape and column names
- [ ] `tests/typechecking/check_contract.py` — type checking tests for
      @contract decorated functions (positive and negative cases)


---


### M4: Constraints

**Goal:** Users can express column-level constraints (non-negative, one-of, etc.)
that are checked during `parse()`.

This completes the v0 acceptance criteria: "clear, actionable error when
validation fails — constraint violation."

**What works after M4:**

```python
class Order(tacit.Schema):
    amount: Annotated[float, tacit.Ge(0)]           # or Field(ge=0), TBD
    status: Annotated[str, tacit.OneOf("pending", "shipped")]
```

**Acceptance criteria:**
- Constraint syntax is decided and implemented
- Constraints translate to pandera `Check` objects
- `parse()` validates constraints against the engine
- Constraint violations produce clear errors (column, check, values)
- At least: `Ge`, `Le`, `Gt`, `Lt`, `OneOf`, `NotNull` constraints

**Tickets:**

#### T9: Constraint syntax spike
**Type:** spike
**Depends on:** T5

Time-boxed research to decide constraint syntax. Evaluate:
- `Annotated[float, tacit.Ge(0)]` (annotated-types style)
- `float = tacit.Field(ge=0)` (pydantic style)
- Both simultaneously

Consider: ergonomics, type checker compatibility, pandera translation
complexity, composability.

- [ ] Document decision with rationale
- [ ] Update DESIGN.md open questions section
- [ ] Sketch implementation approach

#### T10: Constraint implementation
**Type:** feature
**Depends on:** T9

Implement the chosen constraint syntax.

- [ ] Constraint objects (`Ge`, `Le`, `Gt`, `Lt`, `OneOf`, `NotNull` at minimum)
- [ ] `Schema._pandera_schema()` translates constraints to pandera `Check` objects
- [ ] `parse()` validates constraints — violations produce clear error messages
      (which column, which check, expected vs actual)
- [ ] Constraints compose with inheritance (child schema inherits parent constraints)
- [ ] `tests/test_parse.py` extended with constraint tests
- [ ] `__init__.py` exports constraint types


---


## Ticket index

| ID | Issue | Type | Milestone | Depends on |
|----|-------|------|-----------|------------|
| T1 | #6 Test infrastructure and project setup | feature | M1 (#2) | — |
| T2 | #7 Schema base class | feature | M1 (#2) | #6 |
| T3 | #8 DataFrame[S] and cast() | feature | M1 (#2) | #7 |
| T4 | #9 Type safety tests | feature | M1 (#2) | #8 |
| T5 | #10 parse() with pandera validation | feature | M2 (#3) | #8 |
| T6 | #11 Iris pipeline example | feature | M2 (#3) | #10 |
| T7 | #12 @tacit.contract decorator | feature | M3 (#4) | #10 |
| T8 | #13 TPC-H example and contract type checks | feature | M3 (#4) | #12 |
| T9 | #14 Constraint syntax spike | spike | M4 (#5) | #10 |
| T10 | #15 Constraint implementation | feature | M4 (#5) | #14 |

```
M1: Structural contracts          M2: Validated pipelines
┌────┐                            ┌────┐
│ T1 │ setup                      │ T5 │ parse()
└──┬─┘                            └──┬─┘
   │                                 │
┌──▼─┐                            ┌──▼─┐
│ T2 │ Schema                     │ T6 │ iris example
└──┬─┘                            └────┘
   │
┌──▼─┐        ┌────┐
│ T3 │───────▶│ T5 │─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐
└──┬─┘        └──┬─┘
   │             │             M3: Contracts
┌──▼─┐        ┌──▼─┐          ┌────┐
│ T4 │        │ T7 │─────────▶│ T8 │ tpch example
└────┘        └────┘          └────┘
  type         contract
  safety                       M4: Constraints
                              ┌────┐    ┌─────┐
                         T5──▶│ T9 │───▶│ T10 │
                              └────┘    └─────┘
                              spike      impl
```
