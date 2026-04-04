# Contract Type Transparency Spike

**Date**: 2026-04-04
**Verdict**: `returns=` parameter with `@overload` signatures on `contract()`. No pyright plugin needed.

---

## The problem

`@tacit.contract` wraps a function to enforce DataFrame schemas at runtime.
The decorator calls `cast()` or `parse()` on the return value, so the function
body could safely return a plain `ir.Table` — the decorator will handle the
conversion.

But Python's type system checks function bodies against their **own** return
annotation, independently of any decorator. If a function declares
`-> DataFrame[Output]`, pyright requires the body to produce `DataFrame[Output]`.
This forces users to write `Output.cast(result)` inside every contract body —
exactly the boilerplate the decorator was supposed to eliminate.

```python
@tacit.contract
def transform(df: DataFrame[Iris]) -> DataFrame[IrisFeatures]:
    result = df.mutate(sepal_ratio=df.sepal_length / df.sepal_width)
    return IrisFeatures.cast(result)  # boilerplate — decorator already does this
```

## Approaches evaluated

### 1. ParamSpec + TypeVar (body return relaxation)

The idea: use `ParamSpec` to preserve parameter types and a `TypeVar` to
transform the return type, so the decorator signature says "body returns T,
call sites see DataFrame[S]".

**Problem**: Python's type system has no way to express "the body of this
function is checked against type A, but callers see type B." `ParamSpec`
preserves parameter types through decorators but doesn't help with return type
transformation in the *body* — the body is always checked against its own
annotation. The decorator can only change what *callers* see.

**Verdict**: Not viable. Fundamentally incompatible with how Python type
checking works.

### 2. @overload on contract() with returns= parameter

The idea: add a `returns=` parameter that moves the output schema to the
decorator. The function body annotates `-> ir.Table` (natural return type of
ibis operations). Overloaded signatures on `contract()` make call sites see
`DataFrame[S]`.

```python
@overload
def contract(fn: Callable[P, R], /) -> Callable[P, R]: ...
@overload
def contract(*, returns: type[S], validate: bool = ...,
) -> Callable[[Callable[P, ir.Table]], Callable[P, DataFrame[S]]]: ...
@overload
def contract(*, validate: bool = ...,
) -> Callable[[Callable[P, R]], Callable[P, R]]: ...
```

**How it works**:
- The body annotates `-> ir.Table`, so pyright is happy with plain ibis returns
- The overload with `returns=` maps `Callable[P, ir.Table]` to
  `Callable[P, DataFrame[S]]`, so call sites see the correct type
- `ParamSpec` preserves all parameter types through the transformation

**Verdict**: Works. Solves the problem without any special type system
extensions.

### 3. Protocol-based approach (ContractReturn[S])

The idea: define a protocol that both `ir.Table` and `DataFrame[S]` satisfy,
use it as the body return type.

**Problem**: `ir.Table` and `DataFrame[S]` share many methods, but creating
a protocol that captures enough of the ibis API is fragile and must track
upstream changes. More importantly, the protocol return type leaks into call
sites — callers would see `ContractReturn[S]` instead of `DataFrame[S]`.

**Verdict**: Too complex, leaky abstraction.

### 4. Pyright plugin / custom type stubs

The idea: write a pyright plugin that special-cases `@contract` to allow
`ir.Table` returns in decorated bodies.

**Problem**: pyright plugins are not a public API — they exist but are
unsupported and may break between versions. This also ties tacit to a single
type checker (no mypy support). The maintenance burden is disproportionate to
the problem.

**Verdict**: Overkill. Standard typing can express this.

## Decision

**Option 2: `returns=` with `@overload`**. It solves the problem entirely within
Python's standard typing system, requires no external tooling, and supports both
usage patterns:

```python
# Pattern A: explicit cast in body (full body type checking)
@tacit.contract
def transform(df: DataFrame[Iris]) -> DataFrame[IrisFeatures]:
    return IrisFeatures.cast(df.mutate(...))

# Pattern B: returns= (no cast needed, decorator owns the output schema)
@tacit.contract(returns=IrisFeatures)
def transform(df: DataFrame[Iris]) -> ir.Table:
    return df.mutate(...)
```

Both patterns produce `DataFrame[IrisFeatures]` at call sites. Pattern A gives
stricter body checking; pattern B eliminates boilerplate at the cost of no
body-level return type enforcement for the schema.

## Implementation notes

- Three `@overload` signatures cover: bare `@contract`, `@contract(returns=S)`,
  and `@contract(validate=True)` without `returns`
- Runtime behavior is identical regardless of which pattern is used — `_wrap()`
  always calls `cast()` or `parse()` on the return value
- `ParamSpec` (`P`) preserves parameter types across all overloads
- The `returns` parameter is `type[S]` (a Schema subclass), not an instance
