# Feasibility Spike: `tacit.DataFrame[S]`

**Date**: 2026-03-29
**Verdict**: Feasible. Subclass `ibis.Table` with `Generic[S]`.

---

## The question

Can `tacit.DataFrame[S]` be a type that:
1. Carries schema info for static type checking (contracts work at check-time)
2. Is transparent to use (no `unwrap()` / `to_ibis()` ceremony)
3. Forces users through `parse()` / `cast()` (can't forget the contract)

## The answer

Yes. All three goals are met by subclassing `ibis.Table`:

```python
S = TypeVar("S")

class DataFrame(ir.Table, Generic[S]):
    __slots__ = ("_tacit_schema",)

    @classmethod
    def _from_table(cls, table: ir.Table, schema_type=None):
        df = cls(table.op())
        object.__setattr__(df, "_tacit_schema", schema_type)
        return df
```

## Evidence by goal

### Goal 1: Static typing works

pyright correctly extracts schema types from function annotations:

```python
def f(df: DataFrame[Iris]) -> DataFrame[IrisFeatures]: ...
# get_type_hints returns: {df: DataFrame[Iris], return: DataFrame[IrisFeatures]}
# __origin__ = DataFrame, __args__ = (Iris,) / (IrisFeatures,)
```

This enables `@tacit.contract` to introspect signatures at runtime.

- **Verified in**: [type_check_test.py](type_check_test.py) (pyright), [e2e_proof_of_concept.py](e2e_proof_of_concept.py) `test_type_annotation_introspection()`

### Goal 2: Transparent usage (no unwrap)

`DataFrame[S]` IS an `ibis.Table` (subclass), so:
- `df.sepal_length` → ibis column expression (column access works)
- `df.mutate(...)`, `df.filter(...)`, `df.select(...)` → all work natively
- Any function accepting `ir.Table` accepts `DataFrame[S]`
- pandera validation accepts it (backend dispatch via MRO)

- **Verified in**: [e2e_proof_of_concept.py](e2e_proof_of_concept.py) `test_transparent_usage()`, [ibis_subclass_test.py](ibis_subclass_test.py)

### Goal 3: Can't forget parse()/cast()

pyright reports type errors for:
- Returning `ibis.Table` where `DataFrame[S]` expected
- Returning `DataFrame[Iris]` where `DataFrame[IrisFeatures]` expected (invariant generic)

The "pit of success" works because:
1. `DataFrame[S]` is a **distinct type** from `ibis.Table`
2. ibis operations on `DataFrame[S]` return plain `ibis.Table` (hardcoded in ibis internals via `ops.Relation.to_expr()`)
3. The generic parameter `S` is **invariant** — `DataFrame[Iris] ≠ DataFrame[IrisFeatures]`

```
error: Type "Table" is not assignable to return type "DataFrame[IrisFeatures]"
error: "DataFrame[Iris]" is not assignable to "DataFrame[IrisFeatures]"
  Type parameter "S@DataFrame" is invariant
```

- **Verified in**: [type_check_test.py](type_check_test.py) (pyright output), [e2e_proof_of_concept.py](e2e_proof_of_concept.py) `test_type_errors()`

## ibis internals

| Question | Answer | Reference |
|----------|--------|-----------|
| Can `ibis.Table` be subclassed? | Yes, cleanly | [ibis_subclass_test.py](ibis_subclass_test.py) |
| Instantiate from existing Table? | `cls(table.op())` | [ibis_subclass_test.py](ibis_subclass_test.py) |
| `isinstance(df, ir.Table)`? | True (subclass) | [ibis_subclass_test.py](ibis_subclass_test.py) |
| Operations preserve subclass? | No → plain `Table` (correct by design) | [ibis_subclass_test.py](ibis_subclass_test.py), [logbook_ibis.md](logbook_ibis.md) |
| `__class_getitem__`? | via `Generic[S]` mixin | [ibis_subclass_test.py](ibis_subclass_test.py) |
| `__setattr__` blocked? | Use `object.__setattr__()` (Immutable base) | [logbook_ibis.md](logbook_ibis.md) |
| Auto-rewrap methods? | Not needed, not desirable | [ibis_metaclass_rewrap_test.py](ibis_metaclass_rewrap_test.py), [logbook_ibis.md](logbook_ibis.md) |
| Wrapper approach? | Tested, rejected (isinstance breaks) | [ibis_wrapper_test.py](ibis_wrapper_test.py), [logbook_ibis.md](logbook_ibis.md) |

## pandera integration

| Question | Answer | Reference |
|----------|--------|-----------|
| Backend dispatch with subclass? | Works (MRO-based) | [logbook_pandera.md](logbook_pandera.md) |
| Programmatic schema construction? | `DataFrameSchema({name: Column(type)})` | [pandera_programmatic.py](pandera_programmatic.py) |
| `validate()` return value? | Same object, preserves subclass type | [pandera_programmatic.py](pandera_programmatic.py), [logbook_pandera.md](logbook_pandera.md) |
| Coercion? | Not supported in ibis backend | [logbook_pandera.md](logbook_pandera.md) |
| Coercion workaround? | `ibis.Table.cast()` before pandera validate | [e2e_proof_of_concept.py](e2e_proof_of_concept.py) `test_parse()` |
| Strict mode (extra columns)? | Works with `strict=True` | [pandera_programmatic.py](pandera_programmatic.py) |
| Dynamic checks (ge, isin, etc.)? | Works via `Check.ge()` etc. | [pandera_programmatic.py](pandera_programmatic.py) |

## The lifecycle (confirmed working end-to-end)

```
ibis.Table ──parse()──▶ DataFrame[Iris] ──.mutate()──▶ ibis.Table ──cast()──▶ DataFrame[IrisFeatures]
 (untyped)               (typed, ibis API)               (untyped)              (typed)
```

1. `Schema.parse(table)`: cast types via ibis → validate with pandera → wrap as `DataFrame[S]`
2. User transforms with full ibis API (result drops to plain `Table`)
3. `Schema.cast(table)`: metadata-only structural check → wrap as `DataFrame[S]`

- **Full pipeline verified in**: [e2e_proof_of_concept.py](e2e_proof_of_concept.py) `test_full_pipeline()`

## Future consideration: generic parameter variance

`DataFrame[S]` uses an **invariant** TypeVar, meaning `DataFrame[IrisFeatures]` is
NOT assignable to `DataFrame[Iris]` even though `IrisFeatures` inherits from `Iris`.
This matches the "strict by default" philosophy.

However, a common use case is "accepts any DataFrame with at least these columns" —
i.e., covariance. Two viable approaches were identified:

### Option A: Bounded TypeVar at the call site (recommended)

No changes to DataFrame. Users opt into loose behavior per-function:

```python
# Strict (default) — exact schema
def strict_fn(df: DataFrame[Iris]) -> DataFrame[Iris]: ...

# Loose — accepts Iris or any subclass (more columns OK)
def loose_fn[S: Iris](df: DataFrame[S]) -> DataFrame[S]: ...
```

Pros: no new types, strict by default, preserves caller's specific schema type.
Cons: slightly more verbose annotation for the loose case.

### Option B: Make DataFrame covariant

Change `S = TypeVar("S", covariant=True)`. Then `DataFrame[IrisFeatures]` is always
assignable to `DataFrame[Iris]`.

Pros: simplest syntax.
Cons: loses invariant "exact match" at the type level. Runtime `cast(strict=True)`
still catches extra columns, but the static check for that direction is gone.

Note: covariance still prevents the dangerous direction — `DataFrame[Iris]` is NOT
assignable to `DataFrame[IrisFeatures]` (can't claim more columns than you have),
and plain `ibis.Table` is NOT assignable to any `DataFrame[S]`.

### Decision

Deferred to post-v0. The current invariant design supports both paths — switching
to covariant is a non-breaking change (it only accepts more things). Option A works
today with no changes.

## Known limitations

1. **ibis type annotations produce false positives in pyright** — see
   [ibis_type_stub_issues.md](ibis_type_stub_issues.md) for full details and
   potential upstream contribution plan.
2. **pandera coercion doesn't work for ibis**: we handle coercion ourselves via `ibis.Table.cast()` before handing to pandera. Straightforward workaround.
3. **Pickling doesn't preserve schema**: `__reduce__` would need an override. Not a v0 concern.

## Research artifacts

| File | Purpose |
|------|---------|
| [TESTING.md](TESTING.md) | Testing strategy: six layers, pydantic-style pyright tests, error messages as API |
| [logbook_ibis.md](logbook_ibis.md) | Detailed ibis research diary |
| [logbook_pandera.md](logbook_pandera.md) | Detailed pandera research diary |
| [ibis_subclass_test.py](ibis_subclass_test.py) | Subclassing experiments |
| [ibis_construction_test.py](ibis_construction_test.py) | Table construction & method override experiments |
| [ibis_metaclass_rewrap_test.py](ibis_metaclass_rewrap_test.py) | Auto-rewrap experiments (rejected) |
| [ibis_wrapper_test.py](ibis_wrapper_test.py) | Wrapper approach (rejected) |
| [pandera_ibis_basic.py](pandera_ibis_basic.py) | Basic pandera + ibis validation |
| [pandera_programmatic.py](pandera_programmatic.py) | Programmatic schema construction |
| [e2e_proof_of_concept.py](e2e_proof_of_concept.py) | Full end-to-end proof of concept (runtime) |
| [type_check_test.py](type_check_test.py) | Static type checking proof (pyright) |
| [constraint_syntax.md](constraint_syntax.md) | Constraint syntax spike: Annotated + pandera Check decision |
