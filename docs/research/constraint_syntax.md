# Constraint Syntax Spike

**Date**: 2026-04-04
**Verdict**: `Annotated` metadata with `pandera.Check` objects. No custom wrappers.

---

## The question

How should users express column-level constraints (non-negative, one-of, etc.)
in tacit schema definitions?

## Options evaluated

### Option A: Annotated metadata

```python
from typing import Annotated
from tacit import Schema, Check, Nullable

class Order(Schema):
    amount: Annotated[float, Check.ge(0)]
    status: Annotated[str, Check.isin(["pending", "shipped"])]
    notes: Annotated[str, Nullable(True)]
```

### Option B: Field() calls

```python
class Order(Schema):
    amount: float = tacit.Field(ge=0)
    status: str = tacit.Field(isin=["pending", "shipped"])
```

### Option C: Custom types

```python
NonNegativeFloat = tacit.Constrained(float, ge=0)
class Order(Schema):
    amount: NonNegativeFloat
```

## Decision: Option A (Annotated)

### Why Annotated wins

1. **No translation layer.** tacit delegates constraint validation to pandera.
   `Check.ge(0)` IS a pandera Check — it goes straight into
   `pa.Column(dtype, checks=[...])` with zero conversion. Defining `tacit.Ge(0)`
   objects that wrap pandera Checks adds code for no benefit.

2. **Type and constraints in one annotation.** `get_type_hints(cls, include_extras=True)`
   returns both the base type and constraint metadata in a single pass. No need to
   separately inspect class `__dict__` for Field() defaults.

3. **Composability.** Multiple constraints are additional Annotated args:
   `Annotated[float, Check.ge(0), Check.le(100)]`. No special syntax for combining.

4. **No default-value ambiguity.** `amount: float = Field(ge=0)` looks like a default
   value assignment. Annotated makes it clear these are type metadata.

5. **Modern Python direction.** PEP 593 Annotated is where the ecosystem is headed.
   Pydantic v2 recommends it. tacit has no legacy to support Field().

6. **Backward compatible.** Plain `amount: float` works unchanged — Annotated is
   opt-in per field.

### Why not Field()

- Requires inspecting `cls.__dict__` separately from type hints — two code paths.
- Default-value semantics are confusing.
- Pydantic supports both for legacy reasons; tacit doesn't have that constraint.
- Can be added later without breaking Annotated users.

### Why not custom types

- Combinatorial explosion: need a type for every constraint combination.
- Users can already create reusable aliases:
  `PositiveFloat = Annotated[float, Check.ge(0)]` — no library support needed.

## Reuse pandera directly

tacit re-exports `pandera.ibis.Check` as `tacit.Check` — literally `Check = pa.Check`.
No subclass, no wrapper. Users get the full pandera Check API. If pandera adds new
checks, they're available in tacit immediately.

The only tacit-defined constraint type is `Nullable(bool)`.

### Public API for constraints

```python
from typing import Annotated
from tacit import Schema, DataFrame, Check, Nullable
```

- `Check` — re-export of `pandera.ibis.Check`
- `Nullable(True/False)` — tacit marker for column nullability

### Why not wrap pandera Checks

- Wrapping adds a translation layer for a hypothetical future backend swap.
- pandera IS the validation engine for the foreseeable future.
- tacit's philosophy: "opinionated glue, not a reimplementation."
- If we ever need to swap, we can introduce wrappers as a non-breaking addition.

## Nullable: strict by default

Columns are non-nullable by default. This matches tacit's strict-by-default
philosophy — surprise nulls in production data are a top source of pipeline bugs.

```python
class Order(Schema):
    name: str                                     # nullable=False (default)
    amount: Annotated[float, Check.ge(0)]         # nullable=False (default)
    nickname: Annotated[str, Nullable(True)]      # nullable=True (opt-in)
```

Implementation: `_pandera_schema()` passes `nullable=False` to every `pa.Column`
unless a `Nullable(True)` marker is found in the field's Annotated metadata.

`Nullable(False)` is redundant but allowed for explicitness.

## Error handling

pandera's `SchemaError` propagates directly from `parse()`. No wrapping.

pandera already provides clear error messages:

```
Column 'amount' failed element-wise validator number 0:
greater_than_or_equal_to(0) failure cases: {'amount': -5.0}
```

A `tacit.ValidationError` wrapper can be added later if needed, without breaking
existing `except SchemaError` handlers (by subclassing).

## Inheritance

Constraints compose through schema inheritance via `get_type_hints()` MRO
resolution. No special handling needed.

```python
class Base(Schema):
    amount: Annotated[float, Check.ge(0)]

class Child(Base):
    name: str
# Child inherits amount with Check.ge(0)

class Stricter(Base):
    amount: Annotated[float, Check.ge(0), Check.le(100)]
# Stricter overrides amount with tighter constraints
```

Verified: `get_type_hints(Child, include_extras=True)` returns the parent's
Annotated metadata for inherited fields.

## Implementation sketch

### New: `src/tacit/constraints.py`

```python
from dataclasses import dataclass
import pandera.ibis as pa

Check = pa.Check

@dataclass(frozen=True)
class Nullable:
    allow: bool = True
```

### Modified: `src/tacit/schema.py`

`__init_subclass__` changes from `get_type_hints(cls)` to
`get_type_hints(cls, include_extras=True)`. For each hint:

1. If `Annotated[T, ...]`: extract base type `T` into `_fields`, extract `Check`
   and `Nullable` instances into `_field_checks` and `_field_nullable`.
2. If plain type: store in `_fields` as before, no checks, `nullable=False`.

`_pandera_schema()` uses the extracted checks:

```python
@classmethod
def _pandera_schema(cls) -> pa.DataFrameSchema:
    columns = {}
    for name, dtype in cls._ibis_schema().items():
        checks = cls._field_checks.get(name, [])
        nullable = cls._field_nullable.get(name, False)
        columns[name] = pa.Column(dtype, checks=checks, nullable=nullable)
    return pa.DataFrameSchema(columns, strict=True)
```

No changes to `_ibis_schema()`, `cast()`, `DataFrame`, or `contract.py`.

### Modified: `src/tacit/__init__.py`

```python
from .constraints import Check, Nullable
# added to __all__
```

## Future exploration: Column[T] descriptors

A SQLAlchemy-style `Column[T]` annotation could make schema fields usable as ibis
deferred expressions:

```python
class Order(Schema):
    amount: Column[float] = Column(Check.ge(0))

# Then Order.amount returns ibis._.amount (a Deferred)
t.filter(Order.amount > 0)      # works in any ibis expression
t.mutate(doubled=Order.amount * 2)
```

This requires the annotation itself to be the descriptor type (`Column[float]`
instead of `float`). pyright correctly resolves the descriptor protocol and infers
`Deferred` for class-level access. The pattern is proven at scale by SQLAlchemy's
`Mapped[T]`.

**Trade-off**: every constrained field must be annotated `Column[float]` instead
of `float` — more verbose, but the only way to get typed deferred column references.

**Decision**: deferred. Ship v0 with Annotated to see if the ergonomics are
acceptable. If users want typed column references for expression building, the
`Column[T]` upgrade path is well-understood and non-breaking.

### Verified findings

| Question | Answer |
|----------|--------|
| `get_type_hints(cls, include_extras=True)` preserves Annotated? | Yes |
| `get_args()` extracts base type + Check metadata? | Yes |
| Multiple Checks compose in Annotated? | Yes — separate args |
| pandera Check objects work directly in `pa.Column(checks=[...])`? | Yes |
| Inheritance preserves Annotated metadata? | Yes — via MRO |
| pandera `nullable=False` catches nulls with ibis? | Yes |
| `Column() -> Any` trick (Pydantic-style) passes pyright? | Yes, but descriptor invisible |
| `Column[T]` with `__get__` overload → pyright sees Deferred? | Yes |
