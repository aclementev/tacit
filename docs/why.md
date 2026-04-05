# Why tacit

## The problem: implicit assumptions

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

## The solution: data contracts

A **data contract** makes every assumption explicit and checkable. In tacit,
a contract is a Python class that declares exactly what a DataFrame must look
like:

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
`sepal_width` must be positive. When you call `Iris.parse(table)`, tacit
validates all of it — and if the data doesn't match, you get a clear error
at the boundary where the bad data entered, not deep inside your pipeline
logic.

Once parsed, your code can safely assume the data is correct. No defensive
checks scattered through your transformations. No silent failures.

## What you get from a single definition

Because a data contract is a Python class with type annotations, the Python
ecosystem gives you more than just runtime validation:

- **Runtime validation** — `parse()` coerces types and validates constraints
  at pipeline boundaries, pushed down to the engine as SQL
- **Static type checking** — type checkers verify that every pipeline stage
  respects the contract before your code runs
- **Editor support** — autocomplete on column names, go-to-definition on
  schemas, find-all-references on consumers
- **Safe refactoring** — rename a column in a schema and your type checker
  flags every function that needs updating
- **AI-agent friendliness** — agents read the schema, generate code that
  satisfies it, and the type checker verifies correctness offline

## Design principles

- **Strict by default.** Unexpected columns are an error, not silently ignored.
  You can opt into loose mode when you need it.
- **Parsing is the gateway.** `Schema.parse()` coerces types and validates in
  one call. No separate coercion step.
- **Library, not framework.** Use tacit with Dagster, Airflow, a script, a
  notebook — anything. It provides tools for writing type-safe transformations,
  not an execution environment.
- **Ibis-native.** Transformations use ibis's expression API directly. Tacit
  handles contracts, ibis handles execution.
