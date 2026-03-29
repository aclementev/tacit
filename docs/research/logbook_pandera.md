# pandera Research Logbook

Research diary for understanding pandera's ibis backend and how tacit can use it for validation.

---

## 2026-03-29: Feasibility Spike Results

### pandera ibis backend: basic functionality

All tested with pandera 0.26+ and ibis-framework 12.0.0 against DuckDB.

**What works:**

1. **`DataFrameModel` validation** -- class-based schema with `Field()` annotations.
   Works with ibis Tables. IMPORTANT: on Python 3.14+, bare annotations
   (`age: int`) are not detected due to PEP 749 lazy annotations; must use
   `age: int = pa.Field()`.
2. **`DataFrameSchema` validation** -- programmatic schema construction from dicts.
   This is what tacit should use (build pandera schemas from tacit `Schema` fields).
3. **Check types** -- `Check.ge()`, `Check.le()`, `Check.isin()`, `Check.in_range()`
   all work with ibis Tables. Checks are pushed down to the engine (SQL).
4. **Strict mode** -- `strict=True` catches extra columns. `strict="filter"` drops
   extra columns (useful for tacit's default strict behavior).
5. **Missing column detection** -- correctly raises `SchemaError` with helpful message.
6. **Wrong dtype detection** -- correctly raises `SchemaError`.
7. **Nullable checks** -- `pa.Column(int, nullable=False)` catches nulls.
8. **DataFrameModel Field checks** -- `pa.Field(ge=0.0, le=1.0)` etc. work.

**What does NOT work:**

1. **Coercion** -- `coerce=True` on a Column does NOT work with ibis backend.
   `pa.Column(float, coerce=True)` still raises `SchemaError: expected float64, got int64`.
   This is a known pandera limitation for ibis.
   **Workaround**: tacit does coercion itself via `ibis.Table.cast()` BEFORE
   passing to pandera for validation. This works perfectly.

### Programmatic schema construction

tacit should NOT use `DataFrameModel` (class-based). Instead, build
`DataFrameSchema` programmatically from `tacit.Schema` fields:

```python
columns = {}
for name, typ in schema._fields.items():
    ibis_type = TYPE_MAP.get(typ, typ)
    columns[name] = pa.Column(ibis_type)
pandera_schema = pa.DataFrameSchema(columns, strict=True)
```

This works with both Python built-in types (`int`, `float`, `str`, `bool`)
and ibis dtype objects (`dt.int64`, `dt.float64`, etc.).

### What does `validate()` return?

- Returns the **same object** (`result is table` is `True`)
- Returns type `ibis.Table` (or the subclass, if a subclass was passed)
- Expression graph is identical (`result.equals(table)` is `True`)
- **No copy or rewrap happens** -- pandera just runs checks and returns the input

This is ideal for tacit: after validation, we just wrap the same Table in our
`DataFrame[S]` subclass.

### Backend dispatch with subclass

pandera uses `schema.get_backend(check_obj)` to route to the ibis backend.
This works correctly with `DataFrame(ir.Table)` subclass -- it routes to
`pandera.backends.ibis.container.DataFrameSchemaBackend`.

No `isinstance` hacks needed.

### Adding checks dynamically

Works fine:

```python
check_fn = getattr(Check, check_name)  # e.g., Check.ge
checks.append(check_fn(check_value))   # e.g., Check.ge(0)
pa.Column(dtype, checks=checks)
```

This means tacit can translate its constraint syntax (`Annotated[float, Ge(0)]`
or `Field(ge=0)`) into pandera Checks programmatically.

### Schema from ibis schema

Can build a pandera schema directly from an ibis table's schema:

```python
for col_name, col_type in table.schema().items():
    columns[col_name] = pa.Column(col_type)
```

Useful for generating validation schemas from existing tables.

### Recommended approach for tacit

**`Schema.parse(table)`:**
1. Check column names exist (fast, metadata-only)
2. Cast column types via `ibis.Table.cast()` (handles coercion)
3. Validate with pandera `DataFrameSchema.validate()` (runs checks against engine)
4. Wrap result in `DataFrame._from_table(validated, schema_type=cls)`

**`Schema.cast(table)`:**
1. Check column names exist (metadata-only)
2. Check column types match ibis schema (metadata-only)
3. Check no extra columns (if strict, metadata-only)
4. Wrap in `DataFrame._from_table(table, schema_type=cls)`
5. Zero execution cost -- purely metadata checks

**`@tacit.contract` decorator:**
1. Inspect function annotations for `DataFrame[S]` parameters
2. On input: call `S.cast(arg)` for each annotated parameter
3. On output: call `S.cast(result)` for return annotation
4. Optionally `S.parse()` if `validate=True`
