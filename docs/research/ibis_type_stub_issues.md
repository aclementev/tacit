# ibis Type Annotation Issues

**Date**: 2026-03-29
**ibis version**: 12.0.0 (ibis-framework[duckdb])
**Type checker**: pyright 1.1.x

These are false-positive type errors pyright reports on valid ibis code. They all
work correctly at runtime. These are upstream issues in ibis's type annotations,
not in tacit. We could contribute fixes.

---

## Issue 1: `Table.__getattr__` returns `Column` (too broad)

**File**: `ibis/expr/types/relations.py:1166`

```python
def __getattr__(self, key: str, /) -> ir.Column:
```

`Table.__getattr__` is how column access works (`df.sepal_length`). It returns
`ir.Column`, which is the base `Column` class from `ibis/expr/types/generic.py`.

The problem: arithmetic operators (`/`, `*`, `+`, `-`) and comparison operators
(`>`, `<`, `>=`, etc.) are defined on `NumericValue` (in `ibis/expr/types/numeric.py`),
NOT on the base `Column`. Since pyright resolves `df.sepal_length` as `Column`,
it doesn't see these operators.

**pyright error**:
```
Operator "/" not supported for types "Column" and "Column" (reportOperatorIssue)
Operator "*" not supported for types "Column" and "Column" (reportOperatorIssue)
Operator ">" not supported for types "Column" and "float" (reportOperatorIssue)
```

**Actual class hierarchy** (at runtime):
```
df.sepal_length → FloatingColumn → NumericColumn → (Column, NumericValue) → ...
                                                     ↑ has operators
```

**Possible fix**: Change return type to a union or use `@overload` — though this
is hard because `__getattr__` doesn't know the column type statically. The real
fix is a type checker plugin that knows the schema, which is future work.

**Workaround for tacit users**: Ignore `reportOperatorIssue` in pyright config
for transformation code, or use `# type: ignore[operator]` on individual lines.
The contract enforcement (parse/cast) is not affected by this issue.

---

## Issue 2: `mutate()` kwargs don't accept Python literals

**File**: `ibis/expr/types/relations.py:2340`

```python
def mutate(
    self, *exprs: ir.Value | Deferred, **mutations: ir.Value | Deferred | str
) -> Table:
```

The `**mutations` parameter accepts `ir.Value | Deferred | str`, but ibis at runtime
also accepts Python scalars (`int`, `float`, `bool`) which it auto-wraps into ibis
literals.

**pyright error**:
```
Argument of type "Literal[1]" cannot be assigned to parameter "x" of
type "Value | Deferred | str" in function "mutate"
```

**Possible fix**: Widen the type annotation to include Python scalar types:
```python
**mutations: ir.Value | Deferred | str | int | float | bool | None
```

Or define a `Scalarlike` type alias that ibis uses consistently across its API.

---

## Issue 3: `ibis.Schema.names` / `.types` typed as `Attribute` (not iterable)

**File**: `ibis/expr/schema.py:66-71`

```python
@attribute
def names(self):
    return tuple(self.keys())

@attribute
def types(self):
    return tuple(self.values())
```

The `@attribute` decorator (from `ibis.common.annotations`) is a cached property-like
descriptor. pyright infers the type as `Attribute` rather than `tuple[str, ...]` /
`tuple[DataType, ...]`, so it doesn't know the result is iterable.

**pyright error**:
```
Argument of type "Attribute" cannot be assigned to parameter "iterable"
of type "Iterable[_T@set]"
```

**Possible fix**: Add return type annotations:
```python
@attribute
def names(self) -> tuple[str, ...]:
    return tuple(self.keys())

@attribute
def types(self) -> tuple[dt.DataType, ...]:
    return tuple(self.values())
```

Or type the `@attribute` decorator as a generic descriptor that preserves return types
(like `@functools.cached_property`).

---

## Issue 4: `pandera.ibis` exports not visible to pyright

**File**: `pandera/ibis/__init__.py` (or `pandera/__init__.py`)

pyright reports `DataFrameSchema` and `Column` as not exported from `pandera.ibis`.
This is a pandera issue, not ibis, but worth noting since we use both.

**pyright error**:
```
"DataFrameSchema" is not exported from module "pandera.ibis" (reportPrivateImportUsage)
"Column" is not exported from module "pandera.ibis" (reportPrivateImportUsage)
```

**Possible fix**: Add explicit `__all__` to `pandera/ibis/__init__.py`, or ensure
re-exports use the `import X as X` pattern that pyright recognizes as intentional
re-exports.

---

## Impact on tacit

These issues affect **user transformation code** (the ibis operations between
parse/cast boundaries). They do NOT affect tacit's core contract enforcement:
- `DataFrame[S]` as a distinct type from `ibis.Table` — works correctly
- Generic parameter invariance — works correctly
- `parse()` / `cast()` return types — works correctly

The most impactful issue is #1 (`__getattr__` return type), because every column
access in transformation code triggers it. The others are minor annoyances.

## Contribution plan

Priority order for upstream PRs:
1. **Issue 2** (mutate kwargs) — smallest, most self-contained fix
2. **Issue 3** (Schema.names/types) — small fix, clear benefit
3. **Issue 4** (pandera exports) — small fix, different repo (pandera)
4. **Issue 1** (__getattr__ return type) — hardest, may need discussion with ibis
   maintainers about approach. A type checker plugin is the proper long-term solution.
