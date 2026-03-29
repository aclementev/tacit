# Tacit

*We called it tacit because data contracts shouldn't be.*

Pydantic-style schemas for data pipelines, built on [ibis](https://ibis-project.org/).

Define your data contracts once. Get type-safe transformations with editor support,
structural and runtime validation, across any ibis-supported backend (DuckDB, Spark,
BigQuery, Polars, Postgres, and [many more](https://ibis-project.org/backends/)).

## Why

Data pipelines break silently. A column gets renamed upstream, a type changes from
int to string, a join produces unexpected nulls — and you find out three stages
downstream when something produces garbage results.

Tacit makes the shape of your data explicit and checkable:

- **At read time**: your editor autocompletes column names from the schema
- **At check time**: the type checker catches mismatches between pipeline stages
- **At run time**: parsing and validation ensure the actual data matches the contract

If a teammate changes a schema, every downstream consumer lights up in CI.
The same applies when an AI agent generates a pipeline step — the schema is
the acceptance test.

## Quick Example

```python
import ibis
import tacit

# Define schemas as classes. Inheritance composes them.
class Iris(tacit.Schema):
    sepal_length: float
    sepal_width: float
    petal_length: float
    petal_width: float
    species: str

class IrisFeatures(Iris):
    sepal_ratio: float
    petal_area: float

# Type-annotated functions define the contract between stages.
@tacit.contract
def engineer_features(df: tacit.DataFrame[Iris]) -> tacit.DataFrame[IrisFeatures]:
    return df.mutate(
        sepal_ratio=df.sepal_length / df.sepal_width,
        petal_area=df.petal_length * df.petal_width,
    )

# Parse at pipeline boundaries.
table = ibis.duckdb.connect().read_csv("iris.csv")
iris = Iris.parse(table)                 # coerce types + validate (eager)
features = engineer_features(iris)
```

Column access (`df.sepal_length`) is ibis-native — you get the full expression API
with autocomplete, because the DataFrame knows its schema.

## Core Concepts

**Schemas** are Python classes. They declare column names and types. They compose
via inheritance — no duplication.

```python
class Base(tacit.Schema):
    id: int
    created_at: str

class User(Base):
    name: str
    email: str

class UserWithScore(User):
    risk_score: float
```

**Parsing** is the gateway from untyped to typed:

- `Schema.parse(table)` — full parsing. Coerces types, runs constraints,
  executes against the engine (no data pulled into Python).
  Use at pipeline boundaries where you don't trust the data.
- `Schema.cast(table)` — structural check only. Verifies column names and types
  against ibis metadata. Zero execution cost. Use between internal steps.

**Typed functions** declare what goes in and what comes out:

```python
def transform(df: tacit.DataFrame[User]) -> tacit.DataFrame[UserWithScore]:
    return df.mutate(risk_score=compute_risk(df))
```

The optional `@tacit.contract` decorator enforces these signatures at runtime.

## Design Principles

- **Strict by default.** Unexpected columns are an error, not silently ignored.
  You can opt into loose mode when you need it.
- **Parsing is the gateway.** `Schema.parse()` coerces types (e.g., string → float
  from CSV) and validates in one call. No separate coercion step.
- **Library, not framework.** Tacit doesn't run your pipeline. Use it with
  Dagster, Airflow, a script, a notebook — anything. It provides tools for writing
  type-safe transformations, not an execution environment.
- **Ibis-native.** Transformations use ibis's expression API directly. Tacit
  doesn't wrap or replace it — ibis handles execution and backend flexibility,
  tacit handles contracts.

## Status

Early development. The API is not stable. See [DESIGN.md](DESIGN.md) for the
vision and current decisions.
