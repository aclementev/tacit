# Schemas

A schema is a Python class that declares the shape of a DataFrame — column
names and their types. It's the single source of truth that your editor, type
checker, and runtime validation all read from.

```python
import tacit

class Iris(tacit.Schema):
    sepal_length: float
    sepal_width: float
    petal_length: float
    petal_width: float
    species: str
```

## Field types

Schema fields use Python types, which tacit maps to ibis types:

| Python type | ibis type |
|-------------|-----------|
| `float`     | `float64` |
| `int`       | `int64`   |
| `str`       | `string`  |
| `bool`      | `boolean` |

These are the types that `parse()` coerces to and `cast()` checks against. If
your CSV has string columns where you declared `float`, `parse()` will coerce
them automatically. `cast()` will reject the mismatch.

## Inheritance

Schemas compose via inheritance. Each pipeline stage typically adds columns
to the previous stage's schema:

```python
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


class IrisPrediction(IrisFeatures):
    predicted_species: str
```

`IrisFeatures` has eight columns (five from `Iris`, three new).
`IrisPrediction` has nine. No duplication — if you rename a column in `Iris`,
it propagates to every schema that inherits from it.

This mirrors how pipelines actually work: each stage takes a DataFrame,
transforms it, and produces a wider (or differently shaped) DataFrame. Schema
inheritance expresses that directly.

## Strict mode

By default, tacit is strict — both `parse()` and `cast()` reject DataFrames
with extra columns that aren't declared in the schema:

```python
import ibis

table = ibis.memtable({
    "sepal_length": [5.1],
    "sepal_width": [3.5],
    "petal_length": [1.4],
    "petal_width": [0.2],
    "species": ["setosa"],
    "row_id": [1],  # not in the schema
})

Iris.cast(table)
# ValueError: Extra columns: ['row_id']
```

This is intentional. Silent extra columns are a common source of bugs in data
pipelines — a join produces more columns than expected, or an upstream change
adds a column that shadows a downstream computation. Strict mode catches this
immediately.

## `parse()` vs `cast()`

Both are called on the schema class and return a typed `DataFrame[S]`. They
differ in how much work they do:

| | `parse()` | `cast()` |
|---|-----------|----------|
| Check columns exist | Yes | Yes |
| Reject extra columns | Yes | Yes |
| Check types | Yes | Yes |
| Coerce types | Yes | No |
| Validate constraints | Yes | No |
| Executes queries | Yes | No |

**Use `parse()` at pipeline boundaries** — where you're ingesting data you
don't fully trust (files, databases, API responses). It coerces types (e.g.,
string → float from a CSV) and validates all constraints.

**Use `cast()` between internal steps** — where you trust the data but want
type safety. It checks column names and types against ibis metadata with zero
execution cost. Think of it as a lightweight `parse()` that verifies structure
without running queries.

```python
# At the boundary: full validation
iris = Iris.parse(con.read_csv("iris.csv"))

# Between internal steps: structural check only
features = IrisFeatures.cast(df.mutate(...))
```

## Adding constraints

Schemas can also declare constraints on individual columns using `Annotated`
and `tacit.Check`:

```python
from typing import Annotated

class Iris(tacit.Schema):
    sepal_length: float
    sepal_width: Annotated[float, tacit.Check.gt(0)]
    species: str
```

Constraints are validated by `parse()` and ignored by `cast()`. See
[Constraints](constraints.md) for the full details.
