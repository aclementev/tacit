# tacit

Pydantic-style schemas for DataFrame pipelines, built on
[ibis](https://ibis-project.org/) and
[pandera](https://pandera.readthedocs.io/).

Every DataFrame operation makes implicit assumptions about the data — which
columns exist, their types, whether nulls are allowed. Tacit makes them
explicit: you define [**schemas**](concepts/schemas.md) as Python classes
and enforce [**contracts**](concepts/contracts.md) on the functions that
transform them. From that single definition:

- **Catch errors where they happen** — pandera validates actual data at pipeline
  boundaries. Missing columns, wrong types, constraint violations — caught where
  bad data enters, not three stages downstream. Validation is pushed down to the
  engine as SQL.
- **Catch errors before they happen** — type checkers (mypy, pyright, ty,
  pyrefly) verify that every pipeline stage respects the contract before your
  code runs. Forget to add a column after a `.mutate()`? Your editor underlines
  it immediately.
- **Make contracts self-documenting** — "go to definition" on any schema shows
  every column, its type, and its constraints. No Slack threads, no stale wiki
  pages, no asking the person who wrote the pipeline six months ago. The code
  has the full context — for teammates, for your future self, and for coding
  agents that can discover schemas autonomously without extra context files.
- **Make changes safe** — pipeline functions declare their schemas in type
  annotations, so "find all references" shows every consumer of a table across
  your codebase. Rename a column and your type checker flags every function that
  needs updating — across teams, across repos.

All of this works across any
[ibis-supported backend](https://ibis-project.org/backends/) — DuckDB, Spark,
BigQuery, Polars, Postgres, and more.

## Install

=== "uv"

    ```bash
    uv add tacit
    ```

=== "pip"

    ```bash
    pip install tacit
    ```

## Quick example

```python
import ibis
import tacit


# Schemas are Python classes. Your editor autocompletes column names from these.
class Iris(tacit.Schema):
    sepal_length: float
    sepal_width: float
    petal_length: float
    petal_width: float
    species: str


# Inheritance composes schemas — no duplication.
class IrisFeatures(Iris):
    sepal_ratio: float
    petal_ratio: float
    petal_area: float


# Type annotations declare the contract: what goes in, what comes out.
# @contract enforces it at runtime — wrong columns or types raise immediately.
@tacit.contract
def engineer_features(df: tacit.DataFrame[Iris]) -> tacit.DataFrame[IrisFeatures]:
    return df.mutate(
        sepal_ratio=df.sepal_length / df.sepal_width,  # (1)
        petal_ratio=df.petal_length / df.petal_width,
        petal_area=df.petal_length * df.petal_width,
    )


con = ibis.duckdb.connect()
table = con.read_csv("iris.csv")

# parse() at the boundary: coerces types and validates against the schema.
# This is where untrusted data becomes a typed DataFrame.
iris = Iris.parse(table)

# From here, everything is type-safe.
# pyright knows engineer_features expects DataFrame[Iris]
# and returns DataFrame[IrisFeatures].
features = engineer_features(iris)
```

1. `df.sepal_length` — this is ibis's expression API. Tacit doesn't wrap it;
   you get the full power of ibis with column names that your editor can verify.
