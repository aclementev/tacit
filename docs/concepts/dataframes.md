# DataFrames

`DataFrame[S]` is a lightweight wrapper that ties a [schema](schemas.md) to an
ibis Table. It's how tacit tracks which contract a table has been verified
against.

```python
iris = Iris.parse(con.read_csv("iris.csv"))
# iris is a DataFrame[Iris] — an ibis Table that has been validated
```

`DataFrame[S]` is a subclass of `ibis.expr.types.Table`, so the full ibis
expression API works — `.mutate()`, `.filter()`, `.group_by()`, `.join()`,
aggregations, window functions, everything. Your editor autocompletes column
names from the schema.

## What happens after a transformation

When you call an ibis operation on a `DataFrame[S]`, the result is a plain
`ir.Table` — the schema type drops off:

```python
iris = Iris.parse(table)          # DataFrame[Iris]
result = iris.mutate(x=iris.sepal_length * 2)  # ir.Table — no longer typed
```

This is by design. After arbitrary transformations — adding columns, dropping
them, renaming, joining — tacit can't statically verify that the result still
matches any particular schema. Rather than pretend it does, the type drops off.
You re-enter typed territory explicitly via `cast()` or `parse()`.

To re-enter typed territory, use `cast()`:

```python
features = IrisFeatures.cast(result)  # DataFrame[IrisFeatures]
```

This is your way of telling tacit: "I've done my transformation, the result
matches this schema — verify the structure and continue checking types from
here." If the columns or types don't match, `cast()` raises immediately.

`@tacit.contract` automates this — it calls `cast()` on inputs and outputs so
you don't have to do it manually. See [Contracts](contracts.md).

## Each schema is a distinct type

`DataFrame[Iris]` and `DataFrame[IrisFeatures]` are different types, even
though `IrisFeatures` inherits from `Iris`. You can't pass one where the other
is expected:

```python
def needs_features(df: tacit.DataFrame[IrisFeatures]) -> ...:
    ...

iris = Iris.parse(table)
needs_features(iris)  # type error — DataFrame[Iris] ≠ DataFrame[IrisFeatures]
```

This is intentional. If `DataFrame[IrisFeatures]` were accepted anywhere
`DataFrame[Iris]` is expected (or vice versa), a function could receive data
that's missing columns it relies on. Each schema represents a specific contract,
and the type system enforces that you've verified the data against the right
one.

(For those familiar with type theory: `DataFrame` is invariant in its type
parameter.)

## Getting a `DataFrame[S]`

There's no way to construct a `DataFrame[S]` directly — and that's the point.
You can only get one through:

- **`Schema.parse(table)`** — checks column names and types, coerces where
  needed, and validates all constraints. Because it runs the full validation,
  the resulting `DataFrame[S]` is guaranteed to satisfy the schema. This is
  mostly intended for the edges of your pipeline — where data enters from
  files, databases, or API responses — but in practice you can use it anywhere
  you need full validation.

- **`Schema.cast(table)`** — checks that column names and types match, but
  skips constraint validation and type coercion. This implies some trust: you're
  asserting that the runtime constraints hold without re-checking them. The main
  use case is internal transformations where the input was already validated via
  `parse()` and is being transformed with user-controlled logic that tacit
  currently cannot verify end-to-end. `cast()` lets you re-enter typed territory
  without the performance cost of re-running full validation.

- **`@tacit.contract`** — syntactic sugar that calls `cast()` (or `parse()`
  with `validate=True`) on function inputs and outputs automatically, removing
  the boilerplate. See [Contracts](contracts.md).

This means a `DataFrame[S]` always represents data that has been verified
against schema `S` — either fully via `parse()`, or structurally via `cast()`
with the user vouching for the rest.

## Validation errors

`cast()` and `parse()` raise tacit's own exception types from `tacit.errors`.
This gives you a stable way to handle validation failures without depending on
backend-specific exception classes:

```python
from tacit.errors import CoercionError, ConstraintError, StructuralError

try:
    orders = Order.parse(raw)
except StructuralError:
    # Missing columns, extra columns, wrong dtypes in structural validation
    ...
except CoercionError:
    # Data couldn't be cast into the schema's target types
    ...
except ConstraintError:
    # Data has the right shape but violates checks/nullability
    ...
```

All of these inherit from `ValidationError`. Each exception exposes the schema
being enforced and the validation phase, and preserves the original pandera or
backend exception when there is one.
