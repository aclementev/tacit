# Contracts

A contract ties [schemas](schemas.md) to a function's signature. The type
annotations declare what goes in and what comes out, `@tacit.contract` enforces
it at runtime, and type checkers verify it statically.

## Without `@contract`

You can write schema-safe functions without the decorator — call `cast()` on
inputs and outputs yourself:

```python
def engineer_features(df: tacit.DataFrame[Iris]) -> tacit.DataFrame[IrisFeatures]:
    result = df.mutate(
        sepal_ratio=df.sepal_length / df.sepal_width,
        petal_ratio=df.petal_length / df.petal_width,
        petal_area=df.petal_length * df.petal_width,
    )
    return IrisFeatures.cast(result)
```

This works. The `cast()` call at the end verifies the output structure and
returns a `DataFrame[IrisFeatures]`. But every function needs the same
boilerplate: call `cast()` on the result, possibly on inputs too. For a
pipeline with many stages, that's a lot of noise.

## With `@contract`

The decorator reads the type annotations and calls `cast()` on inputs and
outputs automatically:

```python
@tacit.contract
def engineer_features(df: tacit.DataFrame[Iris]) -> tacit.DataFrame[IrisFeatures]:
    return df.mutate(
        sepal_ratio=df.sepal_length / df.sepal_width,
        petal_ratio=df.petal_length / df.petal_width,
        petal_area=df.petal_length * df.petal_width,
    )
```

Same safety, less noise. The decorator inspects the annotations, finds every
parameter and return type that's a `DataFrame[S]`, and wraps them with the
appropriate schema check.

Non-DataFrame parameters (strings, ints, config objects) pass through
unchanged.

??? note "Why no unwrap or cast on the input?"

    You might expect to need something like `df.unwrap()` or `Iris.cast(df)`
    inside the function body to get a regular ibis Table to work with. You
    don't — `DataFrame[S]` *is* an ibis Table (it's a subclass), so you can
    call `.mutate()`, `.filter()`, `.group_by()`, or any ibis API directly on
    it. The result is a plain `ir.Table` that you can continue working with
    normally. See [DataFrames](dataframes.md) for more on this.

## `validate=True`

By default, `@contract` uses `cast()` — structural checks only. If you want
full validation (type coercion + constraint checking via `parse()`), pass
`validate=True`:

```python
@tacit.contract(validate=True)
def ingest_iris(raw: tacit.DataFrame[RawIris]) -> tacit.DataFrame[Iris]:
    return raw.mutate(...)
```

This is useful at pipeline entry points where the data hasn't been validated
yet, or at boundaries where you want to re-validate after a complex
transformation. It has a performance cost — `parse()` executes queries against
the engine — so use it where correctness matters more than speed.

## `returns=`

There's a friction point when using `@contract` with type checkers. The
function body returns an `ir.Table` (the natural result of ibis operations like
`.mutate()`), but the annotation says `-> DataFrame[IrisFeatures]`. The type
checker sees a mismatch — it checks the body against its own return annotation,
independently of any decorator. This forces you to add `cast()` inside the body
anyway, defeating the purpose.

`returns=` solves this by moving the output schema to the decorator:

```python
@tacit.contract(returns=IrisFeatures)
def engineer_features(df: tacit.DataFrame[Iris]) -> ir.Table:
    return df.mutate(
        sepal_ratio=df.sepal_length / df.sepal_width,
        petal_ratio=df.petal_length / df.petal_width,
        petal_area=df.petal_length * df.petal_width,
    )
```

The function body annotates `-> ir.Table`, which is what ibis operations
actually return — no type error. The decorator handles `cast()` on the result.
Call sites still see `DataFrame[IrisFeatures]` as the return type, so
downstream code is fully typed.

**When to use it:** `returns=` is the recommended approach when you want
`@contract` to own the full input/output checking without any manual `cast()`
in the body. It's especially useful when the function does several ibis
operations and you don't want to cast intermediate results.

**The alternative** is the plain `@tacit.contract` form with
`-> DataFrame[IrisFeatures]` in the annotation and an explicit `cast()` at the
end of the body. Both approaches are equivalent at runtime — choose based on
whether you prefer the schema in the decorator or in the annotation.

## What the decorator does not do

`@contract` checks inputs and outputs. It does not validate what happens
*inside* the function body — the transformation logic between the input schema
and the output schema is yours. If you add wrong columns, compute wrong values,
or introduce nulls, the decorator won't catch it unless those violations also
break the output schema's structural checks (or constraint checks, with
`validate=True`).

The contract is a boundary check, not a line-by-line audit.

## Error handling

Contract failures use the same exception family as `cast()` and `parse()`, but
with contract-specific boundary context attached:

```python
from tacit.errors import ValidationError, ValidationPhase

try:
    result = transform(df)
except ValidationError as exc:
    if exc.phase is ValidationPhase.CONTRACT_INPUT:
        ...
    elif exc.phase is ValidationPhase.CONTRACT_OUTPUT:
        ...
```

The concrete subclasses are:

- `StructuralError`
- `CoercionError`
- `ConstraintError`
- `CheckExecutionError`

Import them from `tacit.errors`.
