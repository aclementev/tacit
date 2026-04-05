# Why tacit

## Implicit assumptions

Every DataFrame operation makes assumptions about the data. When you write
`df.sepal_length / df.sepal_width`, you're assuming both columns exist, that
they're numeric, and probably that `sepal_width` is never zero. When you filter
on `df.species == "setosa"`, you're assuming `species` is a string column with
that value in it.

These assumptions are usually invisible. They live in your head, in a Slack
message, maybe in a wiki page that's three versions behind. When an assumption
breaks — a column gets renamed upstream, a type changes from int to string, a
join produces unexpected nulls — you find out three stages downstream when
something produces garbage results. Or worse, you don't find out at all.

## Schemas make assumptions explicit

A [**schema**](concepts/schemas.md) is a Python class that declares exactly
what a DataFrame looks like — column names, types, and constraints:

```python
from typing import Annotated
import tacit

class Iris(tacit.Schema):
    sepal_length: float
    sepal_width: Annotated[float, tacit.Check.gt(0)]
    petal_length: float
    petal_width: float
    species: str
```

This says: the DataFrame has these five columns, with these types, and
`sepal_width` must be positive. Anyone — human or coding agent — can
"go to definition" and understand the full contract without running anything.

At pipeline boundaries, `Iris.parse(table)` coerces types and validates every
constraint. If the data doesn't match, you get a clear error where the bad data
entered, not deep inside your pipeline logic. Between internal steps,
`Iris.cast(table)` does a lightweight structural check — column names and types
only, zero execution cost.

Once parsed, your code can safely assume the data is correct. No defensive
checks scattered through your transformations. No silent failures.

## Contracts enforce them at function boundaries

A [**contract**](concepts/contracts.md) ties schemas to the functions that
transform data. The type signature *is* the contract — what goes in, what comes
out:

```python
@tacit.contract
def engineer_features(df: tacit.DataFrame[Iris]) -> tacit.DataFrame[IrisFeatures]:
    return df.mutate(
        sepal_ratio=df.sepal_length / df.sepal_width,
        petal_area=df.petal_length * df.petal_width,
    )
```

The `@contract` decorator enforces the schema on inputs and outputs at runtime.
Type checkers verify it statically. "Find all references" on `Iris` shows every
function that consumes that schema — rename a column and your type checker flags
every site that needs updating, across teams, across repos.

## Built on ibis and pandera, not replacing them

Tacit is not a new DataFrame library or a new validation framework. It builds
on [ibis](https://ibis-project.org/) for the DataFrame API and query execution,
and [pandera](https://pandera.readthedocs.io/) for data validation. Tacit
provides a unified interface with type safety on top.

A `tacit.DataFrame[S]` *is* an ibis Table — you write transformations with the
full ibis expression API, execute against any ibis backend, and get autocomplete
on column names. Validation constraints are pandera `Check` objects — anything
pandera can validate, tacit can validate. You can drop down to raw ibis or
pandera at any point.

This also means tacit inherits some of their current limitations — for example,
ibis's type stubs don't cover every dynamic API, so some type checker warnings
may require annotations. We document workarounds as we find them.

## How is tacit different from...

**Raw pandera** — pandera validates DataFrames, but doesn't provide typed
wrappers or static type checking. You validate, then work with an untyped
DataFrame. Tacit adds `DataFrame[S]` so your editor and type checker know the
schema throughout the pipeline.

**Great Expectations** — a test-suite approach: you write expectations
separately from your code and run them as a validation step. Tacit integrates
validation into the code itself — the schema is the source of truth, not a
parallel test suite that can drift.

**dbt tests** — SQL-only, post-hoc. You write tests in YAML or SQL that run
after transformations. Tacit validates at the Python layer, at the boundary
where data enters your pipeline, with the same schema that gives you type
safety and editor support.

## Design principles

- **Strict by default.** Unexpected columns are an error, not silently ignored.
  You can opt into loose mode when you need it.
- **Parsing is the gateway.** `Schema.parse()` coerces types and validates in
  one call. No separate coercion step.
- **Library, not framework.** Use tacit with Dagster, Airflow, a script, a
  notebook — anything that runs Python and ibis. It provides tools for writing
  type-safe transformations, not an execution environment.
- **Ibis-native.** Transformations use ibis's expression API directly. Tacit
  handles contracts, ibis handles the DataFrame API and query execution.

## Who is this for

Tacit is for data engineers and ML engineers building DataFrame pipelines in
Python who want their data assumptions to be explicit, checkable, and enforced
by the type system.

It's a good fit if you:

- Use ibis (or want to) for backend-portable DataFrame operations
- Want Pydantic-style schemas for your pipeline data
- Care about type safety and editor support in data code
- Work in teams where schema changes need to be traceable

It's probably not for you if:

- You don't use DataFrames (tacit is specifically for tabular data pipelines)
- Your DataFrame library isn't
  [supported by ibis](https://ibis-project.org/backends/) — tacit is built on
  ibis and requires an ibis backend
