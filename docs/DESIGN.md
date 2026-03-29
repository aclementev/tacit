# Design

This document captures the current design direction for tacit, including decisions
made, open questions, and future work. It's a living document — expect it to evolve
as we build and learn.


## Vision

Tacit is **Pydantic for DataFrames**. Define your data contracts as Python classes,
get type safety in your editor, and enforce those contracts at runtime — across any
backend supported by ibis.

The target user is anyone building **production data pipelines in a team setting**:
data engineers, ML engineers, analytics engineers. The value is strongest when
schemas are shared across people or systems — "me in 6 months" counts as a different
person.

Tacit is a **library, not a framework**. It provides schemas, validation, and typed
DataFrames. It does not prescribe how to run your pipeline. Ibis handles execution
and backend flexibility; tacit handles contracts.

### The full vision (beyond v0)

v0 provides **concrete boundary contracts**: define a schema, validate at pipeline
edges, get type-safe function signatures between stages. This is already valuable
for production pipelines.

The long-term vision is **composable, generic transformations**:

```python
# Today (v0): concrete schemas, works great for pipelines
def engineer_features(df: DataFrame[Iris]) -> DataFrame[IrisFeatures]:
    ...

# Future: generic transformations, reusable across any schema
def add_risk_score[S: Schema](df: DataFrame[S]) -> DataFrame[S + {"risk_score": float}]:
    return df.mutate(risk_score=compute_risk(df))
```

The generic form would allow building a **library of composable transformation
functions** with full type safety — any schema in, schema-plus-modifications out.
This requires type-level computation that Python's type system does not support
today (no mapped types, no `keyof`, no type arithmetic).

This is the same problem TypeScript solved with mapped types circa 2016. Python
is roughly where TypeScript was in 2015. The realistic paths forward:

1. **Type checker plugin** (medium-term) — teach pyright/mypy that specific
   transformation patterns produce known schema modifications. Most impactful
   investment, most effort.
2. **Language evolution** — PEP 747 (TypeForm) and future PEPs may eventually
   enable type-level computation. Timeline: years.
3. **Runtime-only generics** — dynamic schema classes without static checking.
   Pragmatic stopgap.

v0 is concrete schemas at pipeline boundaries. The architecture should not
preclude the generic transformation story — but it's explicitly deferred.


## Architecture

### Dependencies

- **ibis** — execution engine and DataFrame API. Provides multi-backend support
  (DuckDB, Spark, BigQuery, Polars, Postgres, etc.). Users write transformations
  in ibis's expression API; tacit doesn't wrap or replace it.
- **pandera** — validation engine. Pandera's ibis backend translates checks into
  engine-native expressions (SQL queries, etc.), so validation doesn't pull data
  into Python. Tacit schemas generate pandera schemas internally.

We intentionally avoid re-implementing a DataFrame transformation API or a validation
API. Both ibis and pandera are mature; tacit is the opinionated glue that makes them
work together with good ergonomics.

### Key Types

- `tacit.Schema` — base class for schema definitions. Users subclass this and
  declare columns as annotated class attributes.
- `tacit.DataFrame[S]` — a schema-aware DataFrame. Wraps an ibis Table and carries
  the schema type parameter `S` for static analysis. Column access (`df.column_name`)
  uses ibis's native expression API.

### How the Pieces Fit

```
User defines         tacit generates            ibis executes
─────────────        ───────────────            ─────────────
class Iris(Schema)   → pandera schema           → validates against engine
  sepal_length: float  (DataFrameModel)           (DuckDB, Spark, etc.)
  species: str       → ibis schema
                       (column names + types)   → structural checks (free)

tacit.DataFrame[Iris]  wraps ibis.Table
  df.sepal_length      → ibis column expression → compiled to SQL / engine ops
```

## Decisions

### Schemas are Python classes (via inheritance)

Schemas are defined as subclasses of `tacit.Schema`. Composition uses Python
class inheritance. This gives us:

- Static type checking and IDE support for free
- Import resolution, go-to-definition, version control diffs
- No need for a custom DSL, YAML, or JSON Schema

Schema inheritance is the primary composition mechanism:

```python
class Base(tacit.Schema):
    id: int
    created_at: str

class User(Base):
    name: str
    email: str
```

Non-additive composition (drop columns, rename) is not supported in v0. If a
pipeline needs a subset of columns, define a separate schema class. Duplication
of a few field declarations is acceptable; it keeps things explicit and
statically checkable.

### Types use Python built-ins

Column types use Python's built-in types (`float`, `int`, `str`, `bool`) as the
primary interface. These map to ibis/pandera types under the hood:

| Python type | ibis type | Notes |
|-------------|-----------|-------|
| `int`       | `int64`   |       |
| `float`     | `float64` |       |
| `str`       | `string`  |       |
| `bool`      | `boolean` |       |

For types that Python built-ins can't express (e.g., `Decimal(12, 2)`, `Date`,
`Timestamp`), we re-export ibis's types rather than defining our own.

### Strict by default

Unexpected columns in the data are an error. This is the opposite of pandera's
default (loose) but matches the "explicit contracts" philosophy. Users can opt
into loose mode when needed.

Rationale: in production pipelines, a surprise column is likely a bug — schema
drift, a bad join, a dependency changing its output. Fail loudly.

### Parsing is the gateway

`Schema.parse()` is the primary operation: take an untyped `ibis.Table` and
produce a typed `tacit.DataFrame[Schema]`. This is the gateway from the untyped
world to the typed world — analogous to Pydantic's `model_validate()`.

Parsing coerces types (e.g., string → float from CSV) and validates constraints
in one call. The schema declares what the data *should* look like; parsing makes
it so (or fails with a clear error). There is no separate "coerce then validate"
workflow.

### Two levels of parsing

- **`Schema.parse(table)`** — full parsing. Coerces types, runs pandera checks
  against the engine (ranges, nulls, etc.). Eager: executes queries. Use at
  pipeline boundaries where you don't trust the data source.
- **`Schema.cast(table)`** — structural parsing only. Checks column names and
  types against ibis's schema metadata. Zero execution cost (metadata only). Use
  between internal pipeline steps when you trust the data but want the type
  system to track the schema.

### Column access is ibis-native

Inside transformation functions, users access columns via ibis's standard
`df.column_name` syntax. The schema is not the column reference mechanism —
ibis handles that. `Schema.column_name` (returning the column name as a string)
is a secondary convenience for programmatic use.

### `@tacit.contract` decorator

`@tacit.contract` marks a function as having a data contract. It parses function
inputs and outputs against their `DataFrame[S]` type annotations at runtime.
It's opt-in — users who prefer explicit `parse()` calls can skip it.

By default, the decorator performs **structural checks only** (column names, types,
nullability) — zero or near-zero cost. Full parsing (data-level constraints) is
opt-in:

```python
@tacit.contract                       # structural only (default)
@tacit.contract(validate=True)        # full pandera validation (eager)
```

Rationale: structural checks catch the vast majority of pipeline bugs (wrong columns,
type mismatches) without forcing query execution. Full validation is for boundary
functions where you don't trust the data source.


## Open Questions

### What is `tacit.DataFrame[S]` at runtime?

We know what it is to the type checker: an ibis Table that conforms to schema `S`.
At runtime, the implementation is TBD. Options under consideration:

- **Subclass of `ibis.Table`** — ideal: `DataFrame[S]` IS an ibis Table, so
  users get the full ibis API with zero wrapping. ibis operations (`.mutate()`,
  `.filter()`, etc.) return plain `ibis.Table` — this is expected and correct.
  The first transformation exits tacit-world; you re-enter via `parse()`.
  Feasibility depends on whether ibis.Table can be subclassed (needs spike).
- **Thin wrapper** around `ibis.Table` with `__getattr__` delegation.
  Fallback if subclassing isn't feasible. Same user experience but needs
  explicit delegation, and `isinstance(df, ibis.Table)` may not work.
- **Phantom type only** — `DataFrame[S]` is just a type alias for `ibis.Table`
  with no runtime distinction. Simplest but loses type enforcement (see below).

**Key insight**: if `DataFrame[S]` is a distinct type from `ibis.Table`, the
type system enforces contracts automatically. A function declared as
`-> DataFrame[IrisFeatures]` cannot return a raw `ibis.Table` without a type
error — the user is forced to go through `parse()`, `cast()`, or
`@tacit.contract`. This is a "pit of success" where the wrong thing doesn't
compile. With a phantom type alias, this enforcement disappears.

Leaning toward: **subclass of ibis.Table** (if feasible), falling back to
**thin wrapper**. Either way, `DataFrame[S]` is a distinct type.

### The parse/transform/parse lifecycle

```python
ibis.Table  ──parse()──▶  tacit.DataFrame[Iris]  ──.mutate()──▶  ibis.Table  ──parse()──▶  tacit.DataFrame[IrisFeatures]
 (untyped)                 (typed, ibis API)                      (untyped)                  (typed)
```

The first ibis operation on a `DataFrame[S]` returns a plain `ibis.Table`.
This is correct: after arbitrary transformations, the schema is unknown.
Re-entering tacit-world requires an explicit `parse()` or `cast()` — or
`@tacit.contract` which does it automatically at function boundaries.

```python
@tacit.check_types
def engineer_features(df: tacit.DataFrame[Iris]) -> tacit.DataFrame[IrisFeatures]:
    # df IS an ibis Table (subclass) — full ibis API, no ceremony
    # .mutate() returns ibis.Table — we're in plain ibis land
    return df.mutate(
        sepal_ratio=df.sepal_length / df.sepal_width,
        petal_ratio=df.petal_length / df.petal_width,
        petal_area=df.petal_length * df.petal_width,
    )
    # @contract parses the ibis.Table result into DataFrame[IrisFeatures]
```

Without the decorator, the explicit equivalent is:

```python
def engineer_features(df: tacit.DataFrame[Iris]) -> tacit.DataFrame[IrisFeatures]:
    result = df.mutate(...)
    return IrisFeatures.cast(result)  # explicit parsing, type checker happy
```

Without either, the type checker flags the error: `ibis.Table` is not
assignable to `tacit.DataFrame[IrisFeatures]`. You cannot forget.

### Constraint syntax

How do users express "non-negative float" or "string matching regex X"?
Options:

```python
# Option A: Annotated metadata (like annotated-types / Pydantic)
class Order(tacit.Schema):
    amount: Annotated[float, tacit.Ge(0)]
    status: Annotated[str, tacit.OneOf("pending", "shipped", "delivered")]

# Option B: Field() calls (like Pydantic / pandera)
class Order(tacit.Schema):
    amount: float = tacit.Field(ge=0)
    status: str = tacit.Field(isin=["pending", "shipped", "delivered"])

# Option C: Custom types (like NewType)
NonNegativeFloat = tacit.Constrained(float, ge=0)
class Order(tacit.Schema):
    amount: NonNegativeFloat
```

These are not mutually exclusive. Needs exploration.

### Lazy validation with ibis

Pandera's ibis backend pushes checks down to the engine as native expressions,
which is good. But it still *executes* queries to verify. For lazy engines like
Spark, this means validation forces a query execution at each checkpoint.

Can we attach validation as part of the ibis expression graph so it runs when
the user finally materializes? Unclear if pandera supports this. May need
investigation or custom implementation. For v0, we accept that `validate()` is
eager.

### Hypothesis / property-based testing

Pandera's hypothesis integration is pandas-only — it doesn't work with ibis.
For property-based testing, we'd need to either:

- Generate pandas DataFrames from schemas, then convert to ibis via Arrow
- Build our own hypothesis strategy integration
- Defer this entirely

Deferred for now. Not a v0 priority.


## Future Work

### Generic schema transformations (the big one)

v0 schemas are concrete: `def f(df: DataFrame[Iris]) -> DataFrame[IrisFeatures]`.
The full vision is **generic** transformations that work across any schema:

```python
# The dream — not expressible in Python's type system today
def add_risk_score[S: Schema](df: DataFrame[S]) -> DataFrame[S + {"risk_score": float}]:
    return df.mutate(risk_score=compute_risk(df))
```

This would allow building a library of composable, reusable transformation functions
with full type safety. Python lacks the type-level computation needed for this
(no mapped types, no `keyof`, no type arithmetic). The realistic paths forward:

1. **Type checker plugin** (medium-term) — teach pyright/mypy that specific
   transformation patterns produce known schema modifications. Significant
   investment but the most impactful thing we could do for the ecosystem.
2. **Wait for language evolution** — PEP 747 (TypeForm) and future PEPs may
   eventually enable enough type-level computation. Timeline: years.
3. **Runtime-only generics** — support generic transformations at runtime
   (dynamic schema classes) without static checking. Pragmatic stopgap.

This is the v2 differentiator. v0 is concrete schemas at pipeline boundaries.

### Other future work

- **Dynamic schema composition**: `Schema.drop()`, `Schema.pick()`, `Schema.rename()`
  for creating derived schemas programmatically. Runtime-only (no static checking)
  but useful for reducing boilerplate with wide schemas.
- **Validation error customization**: control over error detail level — include data
  samples? percentages? Custom formatters?
- **Data diffing**: compare two instances of the same schema (e.g., today vs yesterday).
- **Type checker plugin**: mypy/pyright plugin for static column name verification.
  This is the path to catching `df.nonexistent_column` at check time, not runtime.
- **API documentation generation**: generate schema documentation from class definitions
  (column names, types, constraints, docstrings).
- **Hypothesis integration**: property-based test data generation from schemas.
  Pandera's hypothesis support is pandas-only. Would need a generate-then-convert
  strategy via Arrow.


## Acceptance Criteria (v0)

The library is usable when we can:

1. Implement the iris ML pipeline example (feature engineering → prediction)
   with schema validation at boundaries
2. Implement a TPC-H query (Q1 pricing summary) with typed input/output contracts
3. Run both examples against DuckDB via ibis
4. Get meaningful editor autocomplete on `df.column_name` inside transformation
   functions
5. Get a clear, actionable error when validation fails (wrong type, missing column,
   constraint violation)
