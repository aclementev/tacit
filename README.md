# tacit

Pydantic-style schemas for DataFrame pipelines, built on
[ibis](https://ibis-project.org/) and
[pandera](https://pandera.readthedocs.io/).

Every DataFrame operation makes implicit assumptions about the data — which
columns exist, their types, whether nulls are allowed. Tacit makes them
explicit: you define **schemas** as Python classes and enforce **contracts** on
the functions that transform them. From that single definition:

- **Catch errors where they happen** — pandera validates actual data at pipeline
  boundaries. Missing columns, wrong types, constraint violations — caught where
  bad data enters, not three stages downstream.
- **Catch errors before they happen** — type checkers (mypy, pyright, ty,
  pyrefly) verify that every pipeline stage respects the contract before your
  code runs.
- **Make contracts self-documenting** — "go to definition" on any schema shows
  every column, its type, and its constraints. No Slack threads, no stale wiki
  pages. The code has the full context — for teammates, for your future self,
  and for coding agents that can discover schemas without extra context files.
- **Make changes safe** — rename a column in a schema and your type checker
  flags every function that needs updating — across teams, across repos.

Works across any
[ibis-supported backend](https://ibis-project.org/backends/) — DuckDB, Spark,
BigQuery, Snowflake, Polars, Postgres, and more.

**[Documentation](https://aclementev.github.io/tacit/)**

## Install

```bash
uv add tacit

# or with pip directly
pip install tacit
```

## Quick example

```python
import ibis
import tacit


class Iris(tacit.Schema):
    sepal_length: float
    sepal_width: float
    petal_length: float
    petal_width: float
    species: str


class IrisFeatures(Iris):
    sepal_ratio: float
    petal_ratio: float
    petal_area: float


@tacit.contract
def engineer_features(df: tacit.DataFrame[Iris]) -> tacit.DataFrame[IrisFeatures]:
    return df.mutate(
        sepal_ratio=df.sepal_length / df.sepal_width,
        petal_ratio=df.petal_length / df.petal_width,
        petal_area=df.petal_length * df.petal_width,
    )


con = ibis.duckdb.connect()
raw = con.read_csv("iris.csv")

iris = Iris.parse(raw)
features = engineer_features(iris)
```

Schemas are Python classes — your editor autocompletes column names from them.
`parse()` coerces types and validates at the boundary. `@contract` enforces
input/output schemas at runtime. `DataFrame[S]` is an ibis Table, so you get
the full ibis expression API with no wrapping.

## What else

**Constraints** — go beyond column names and types with value-level checks,
powered by pandera:

```python
from typing import Annotated

class Order(tacit.Schema):
    amount: Annotated[float, tacit.Check.ge(0)]
    status: Annotated[str, tacit.Check.isin(["pending", "shipped"])]
    notes: Annotated[str, tacit.Nullable()]
```

**`cast()` vs `parse()`** — `parse()` runs full validation (executes queries).
`cast()` checks column names and types only — zero execution cost, for internal
pipeline steps where the data has already been validated.

**`validate=True`** — `@contract` uses `cast()` by default. Pass
`validate=True` at pipeline entry points to run full `parse()` validation on
inputs and outputs.

See the [documentation](https://aclementev.github.io/tacit/) for the full
guide, API reference, and examples.

## FAQ

**Does this work with pandas?** — Tacit builds on ibis, which
[moved away from pandas](https://ibis-project.org/posts/farewell-pandas/) as a
backend. If your data currently lives in pandas DataFrames, you can use a
well-supported engine like DuckDB or Polars as the execution backend — ibis
reads from and converts back to pandas seamlessly, while giving you a
modern query engine underneath.

**Which backends are supported?** — Any engine that ibis supports. Tacit
delegates all query execution to ibis, so backend support is inherited
automatically. See the
[ibis backends page](https://ibis-project.org/backends/) for the full list.

**Which checks and constraints are available?** — Tacit delegates constraint
validation to pandera's ibis backend. Anything in pandera's
[Check API](https://pandera.readthedocs.io/en/stable/reference/generated/pandera.api.checks.Check.html)
that has ibis support will work. See pandera's
[ibis compatibility status](https://pandera.readthedocs.io/en/stable/supported_libraries.html)
for what's currently available.

## Status

Early development. The API is not stable.
