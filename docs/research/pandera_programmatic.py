"""
Experiment 2: Build pandera ibis schemas programmatically
Tests: constructing schemas from dicts, adding checks dynamically
"""
import ibis
import ibis.expr.datatypes as dt
import pandas as pd
import pandera.ibis as pa
from pandera.ibis import Check

print("=" * 60)
print("1. Build schema from column specs dict")
print("=" * 60)

# Simulate what tacit would do: given a dict of {name: type}, build a schema
column_specs = {
    "id": int,
    "name": str,
    "score": float,
}

columns = {}
for col_name, col_type in column_specs.items():
    columns[col_name] = pa.Column(col_type)

schema = pa.DataFrameSchema(columns, strict=True)
print(f"Schema: {schema}")

t = ibis.memtable(pd.DataFrame({"id": [1, 2], "name": ["a", "b"], "score": [0.5, 0.9]}))
result = schema.validate(t)
print(f"Validation passed: {result.execute()}")

print()
print("=" * 60)
print("2. Build schema with ibis dtypes")
print("=" * 60)

columns_ibis = {
    "id": pa.Column(dt.int64),
    "name": pa.Column(dt.string),
    "score": pa.Column(dt.float64),
}
schema_ibis = pa.DataFrameSchema(columns_ibis, strict=True)
result2 = schema_ibis.validate(t)
print(f"Validation with ibis dtypes passed: {result2.execute()}")

print()
print("=" * 60)
print("3. Build schema with checks programmatically")
print("=" * 60)

# Simulate tacit's check specification
check_specs = {
    "score": {"ge": 0.0, "le": 1.0},
    "name": {"isin": ["a", "b", "c"]},
}

columns_with_checks = {}
for col_name, col_type in column_specs.items():
    checks = []
    if col_name in check_specs:
        for check_name, check_value in check_specs[col_name].items():
            check_fn = getattr(Check, check_name)
            checks.append(check_fn(check_value))
    columns_with_checks[col_name] = pa.Column(col_type, checks=checks)

schema_checks = pa.DataFrameSchema(columns_with_checks, strict=True)
result3 = schema_checks.validate(t)
print(f"Validation with dynamic checks passed: {result3.execute()}")

print()
print("=" * 60)
print("4. Validate without DataFrameModel at all")
print("=" * 60)

# Pure programmatic validation - no class definition needed
schema_pure = pa.DataFrameSchema(
    {
        "x": pa.Column(float, checks=[Check.ge(0), Check.le(100)]),
        "y": pa.Column(str, nullable=False),
    },
    strict=True,
)

t4 = ibis.memtable(pd.DataFrame({"x": [1.0, 50.0], "y": ["hello", "world"]}))
validated = schema_pure.validate(t4)
print(f"Pure programmatic validation: {validated.execute()}")

print()
print("=" * 60)
print("5. Can we add columns to an existing schema?")
print("=" * 60)

schema_base = pa.DataFrameSchema({"a": pa.Column(int)})
print(f"Base schema columns: {list(schema_base.columns.keys())}")

# Add a column
schema_base.columns["b"] = pa.Column(str)
schema_base.columns["b"].set_name("b")
print(f"After adding 'b': {list(schema_base.columns.keys())}")

t5 = ibis.memtable(pd.DataFrame({"a": [1], "b": ["x"]}))
result5 = schema_base.validate(t5)
print(f"Validated: {result5.execute()}")

print()
print("=" * 60)
print("6. Schema from ibis schema (column names + types)")
print("=" * 60)

# Given an ibis table, can we build a pandera schema from its ibis schema?
source_table = ibis.memtable(pd.DataFrame({"x": [1.0], "y": ["a"], "z": [True]}))
ibis_schema = source_table.schema()
print(f"Ibis schema: {ibis_schema}")

columns_from_ibis = {}
for col_name, col_type in ibis_schema.items():
    columns_from_ibis[col_name] = pa.Column(col_type)

schema_from_ibis = pa.DataFrameSchema(columns_from_ibis, strict=True)
print(f"Pandera schema from ibis schema: {schema_from_ibis}")

result6 = schema_from_ibis.validate(source_table)
print(f"Validated: {result6.execute()}")

print()
print("=" * 60)
print("7. DataFrameSchema.validate returns the same table")
print("=" * 60)

schema7 = pa.DataFrameSchema({"a": pa.Column(int)})
t7 = ibis.memtable(pd.DataFrame({"a": [1, 2, 3]}))
r7 = schema7.validate(t7)
print(f"Same object? {r7 is t7}")
print(f"Same expression? {r7.equals(t7)}")
print(f"Type of result: {type(r7)}")

print()
print("=" * 60)
print("8. nullable column check")
print("=" * 60)

schema_nullable = pa.DataFrameSchema({
    "x": pa.Column(int, nullable=True),
    "y": pa.Column(int, nullable=False),
})

# This should pass
t_with_nulls = ibis.memtable(pd.DataFrame({"x": [1, None, 3], "y": [1, 2, 3]}))
try:
    r = schema_nullable.validate(t_with_nulls)
    print(f"Nullable allowed: {r.execute()}")
except Exception as e:
    print(f"Nullable test: {type(e).__name__}: {e}")

# This should fail
t_null_in_required = ibis.memtable(pd.DataFrame({"x": [1, 2, 3], "y": [1, None, 3]}))
try:
    r = schema_nullable.validate(t_null_in_required)
    print(f"ERROR: should have raised! {r.execute()}")
except Exception as e:
    print(f"Non-nullable null caught: {type(e).__name__}: {str(e)[:150]}")

print("\nAll programmatic experiments completed successfully!")
