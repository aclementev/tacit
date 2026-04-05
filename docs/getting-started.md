# Getting Started

## The full picture

Here's a complete tacit pipeline. The annotations walk through each piece.

```python
from typing import Annotated

import ibis
import tacit


class Iris(tacit.Schema):  # (1)
    sepal_length: float
    sepal_width: Annotated[float, tacit.Check.gt(0)]  # (2)
    petal_length: float
    petal_width: float
    species: str


class IrisFeatures(Iris):  # (3)
    sepal_ratio: float
    petal_ratio: float
    petal_area: float


@tacit.contract  # (4)
def engineer_features(df: tacit.DataFrame[Iris]) -> tacit.DataFrame[IrisFeatures]:
    return df.mutate(
        sepal_ratio=df.sepal_length / df.sepal_width,
        petal_ratio=df.petal_length / df.petal_width,
        petal_area=df.petal_length * df.petal_width,
    )


con = ibis.duckdb.connect()
raw = con.read_csv("iris.csv")

iris = Iris.parse(raw)  # (5)
features = engineer_features(iris)  # (6)
```

1. **Schema** — a Python class declaring column names and types.
   [Learn more](concepts/schemas.md).
2. **Constraint** — `sepal_width` must be positive. Uses pandera's `Check`
   objects via `Annotated`. [Learn more](concepts/constraints.md).
3. **Inheritance** — `IrisFeatures` includes all `Iris` columns plus three new
   ones. No duplication.
4. **Contract** — `@tacit.contract` enforces the input and output schemas at
   runtime. Type checkers also verify them statically.
   [Learn more](concepts/contracts.md).
5. **Parse** — coerces types (e.g., string → float from a CSV) and validates
   all constraints. This is the boundary where untrusted data becomes a typed
   `DataFrame[Iris]`. [Learn more](concepts/dataframes.md).
6. **Type-safe call** — `engineer_features` expects `DataFrame[Iris]` and
   returns `DataFrame[IrisFeatures]`. Your editor knows this. The decorator
   verifies it at runtime.

If that's enough to get started, go build something. The rest of this page
walks through each step in more detail.

---

## Define a schema

A schema declares what a DataFrame looks like — column names and their Python
types:

```python
class Iris(tacit.Schema):
    sepal_length: float
    sepal_width: float
    petal_length: float
    petal_width: float
    species: str
```

This is the single source of truth. Your editor, your type checker, and your
runtime validation all read from this class.

Schemas compose via inheritance. If a pipeline stage adds columns, declare a new
schema that extends the previous one:

```python
class IrisFeatures(Iris):
    sepal_ratio: float
    petal_ratio: float
    petal_area: float
```

`IrisFeatures` has all eight columns — five from `Iris`, three new.
See [Schemas](concepts/schemas.md) for the full details.

## Add constraints

Plain types check structure, but often you need more: a column must be positive,
non-null, or restricted to specific values. Use `Annotated` with `tacit.Check`
(a re-export of pandera's `Check` for convenience — both work the same):

```python
from typing import Annotated

class Iris(tacit.Schema):
    sepal_length: float
    sepal_width: Annotated[float, tacit.Check.gt(0)]
    petal_length: float
    petal_width: float
    species: str
```

`sepal_width` must be greater than zero. If any row violates this, `parse()`
raises a clear error naming the column, the check, and the failing values.
See [Constraints](concepts/constraints.md) for all available checks.

## Parse at the boundary

`Schema.parse()` is where untrusted data becomes a typed DataFrame:

```python
con = ibis.duckdb.connect()
raw = con.read_csv("iris.csv")

iris = Iris.parse(raw)
```

`parse()` does three things:

1. Checks that all expected columns exist (and no unexpected extras)
2. Coerces types — e.g., strings from a CSV become floats
3. Validates constraints — pushed down to the engine as SQL

If anything fails, you get an error at this boundary — not three stages later.

For internal pipeline steps where you trust the data but want type safety, use
`cast()` instead. It checks column names and types against ibis metadata with
zero execution cost. See [DataFrames](concepts/dataframes.md) for when to use
each.

## Write transformations

After parsing, you have a `DataFrame[Iris]` — a typed ibis Table. Use the
full ibis expression API:

```python
def engineer_features(df: tacit.DataFrame[Iris]) -> tacit.DataFrame[IrisFeatures]:
    result = df.mutate(
        sepal_ratio=df.sepal_length / df.sepal_width,
        petal_ratio=df.petal_length / df.petal_width,
        petal_area=df.petal_length * df.petal_width,
    )
    return IrisFeatures.cast(result)
```

The type annotations declare the contract: this function takes `DataFrame[Iris]`
and returns `DataFrame[IrisFeatures]`. Your editor autocompletes `df.sepal_length`
because it knows the schema. The `cast()` call at the end verifies the output
has the right shape — you can think of it as a lightweight `parse()` that does
structural checks (column names and types) but skips full runtime validation.

## Add a contract

The function above works, but the `cast()` call at the end is boilerplate.
`@tacit.contract` handles it for you:

```python
@tacit.contract
def engineer_features(df: tacit.DataFrame[Iris]) -> tacit.DataFrame[IrisFeatures]:
    return df.mutate(
        sepal_ratio=df.sepal_length / df.sepal_width,
        petal_ratio=df.petal_length / df.petal_width,
        petal_area=df.petal_length * df.petal_width,
    )
```

The decorator reads the type annotations and automatically calls `cast()` on
inputs and outputs. Same safety, less noise.

For boundary functions where you want full validation (not just structural
checks), pass `validate=True`:

```python
@tacit.contract(validate=True)
def ingest(raw: tacit.DataFrame[Iris]) -> tacit.DataFrame[IrisFeatures]:
    ...
```

This calls `parse()` instead of `cast()`, running the full constraint
validation. See [Contracts](concepts/contracts.md) for the full API.

## Next steps

- [Schemas](concepts/schemas.md) — field types, inheritance, how schemas map to ibis
- [DataFrames](concepts/dataframes.md) — `parse()` vs `cast()`, strict mode
- [Contracts](concepts/contracts.md) — `@contract`, `validate=True`, `returns=`
- [Constraints](concepts/constraints.md) — `Check`, `Nullable`, `Annotated`
