"""
Experiment 1: Basic pandera + ibis validation
Tests: DataFrameModel, DataFrameSchema, type checking, strict mode, coercion

NOTE: On Python 3.14, bare type annotations (e.g. `age: int`) in DataFrameModel
are NOT detected by pandera's __init_subclass__ due to PEP 749 lazy annotations.
You must use explicit `Field()` assignment (e.g. `age: int = Field()`).
"""
import ibis
import pandas as pd
import pandera.ibis as pa
from pandera.ibis import Check

print("=" * 60)
print("1. DataFrameModel-based validation")
print("=" * 60)


class MySchema(pa.DataFrameModel):
    user_name: str = pa.Field()
    age: int = pa.Field()
    score: float = pa.Field()

    class Config:
        strict = True


df = pd.DataFrame({"user_name": ["alice", "bob"], "age": [30, 25], "score": [0.9, 0.8]})
t = ibis.memtable(df)

print(f"Input table type: {type(t)}")
print(f"Input table columns: {t.columns}")
print(f"Input table schema: {t.schema()}")

validated = MySchema.validate(t)
print(f"Validated type: {type(validated)}")
print(f"Validated is same object? {validated is t}")
print(f"Validated result:\n{validated.execute()}")

print()
print("=" * 60)
print("2. DataFrameSchema-based validation (programmatic)")
print("=" * 60)

schema = pa.DataFrameSchema(
    {
        "user_name": pa.Column(str),
        "age": pa.Column(int),
        "score": pa.Column(float),
    }
)

validated2 = schema.validate(t)
print(f"Validated type: {type(validated2)}")
print(f"Result:\n{validated2.execute()}")

print()
print("=" * 60)
print("3. Validation with checks")
print("=" * 60)

schema_with_checks = pa.DataFrameSchema(
    {
        "user_name": pa.Column(str, checks=Check.isin(["alice", "bob", "carol"])),
        "age": pa.Column(int, checks=[Check.ge(0), Check.le(150)]),
        "score": pa.Column(float, checks=Check.in_range(0.0, 1.0)),
    }
)
validated3 = schema_with_checks.validate(t)
print(f"Checks passed! Result:\n{validated3.execute()}")

print()
print("=" * 60)
print("4. Strict mode - extra columns")
print("=" * 60)

t_extra = ibis.memtable(
    pd.DataFrame(
        {"user_name": ["alice"], "age": [30], "score": [0.9], "extra": ["oops"]}
    )
)

strict_schema = pa.DataFrameSchema(
    {"user_name": pa.Column(str), "age": pa.Column(int), "score": pa.Column(float)},
    strict=True,
)

try:
    strict_schema.validate(t_extra)
    print("ERROR: should have raised!")
except Exception as e:
    print(f"Strict mode caught extra column: {type(e).__name__}")
    print(f"  Message: {e}")

print()
print("=" * 60)
print("5. Strict mode with filter")
print("=" * 60)

filter_schema = pa.DataFrameSchema(
    {"user_name": pa.Column(str), "age": pa.Column(int), "score": pa.Column(float)},
    strict="filter",
)

filtered = filter_schema.validate(t_extra)
print(f"Filtered columns: {filtered.columns}")
print(f"Result:\n{filtered.execute()}")

print()
print("=" * 60)
print("6. Coercion attempt")
print("=" * 60)

coerce_schema = pa.DataFrameSchema(
    {"x": pa.Column(float, coerce=True)},
)

t_int = ibis.memtable(pd.DataFrame({"x": [1, 2, 3]}))
print(f"Before coercion, type of x: {t_int.schema()['x']}")

try:
    coerced = coerce_schema.validate(t_int)
    print(f"After coercion, type of x: {coerced.schema()['x']}")
    print(f"Result:\n{coerced.execute()}")
except Exception as e:
    print(f"Coercion failed: {type(e).__name__}: {e}")

print()
print("=" * 60)
print("7. What does validate return?")
print("=" * 60)
print(f"validate returns ibis.Table: {isinstance(validated, ibis.Table)}")
print(f"same expression graph? {validated.equals(t)}")

print()
print("=" * 60)
print("8. Missing column detection")
print("=" * 60)
t_missing = ibis.memtable(pd.DataFrame({"user_name": ["alice"], "age": [30]}))
try:
    schema.validate(t_missing)
    print("ERROR: should have raised!")
except Exception as e:
    print(f"Missing column caught: {type(e).__name__}")
    print(f"  {e}")

print()
print("=" * 60)
print("9. Wrong dtype detection")
print("=" * 60)
t_wrong = ibis.memtable(
    pd.DataFrame({"user_name": ["alice"], "age": ["thirty"], "score": [0.9]})
)
try:
    schema.validate(t_wrong)
    print("ERROR: should have raised!")
except Exception as e:
    print(f"Wrong dtype caught: {type(e).__name__}")
    # just show first 200 chars
    print(f"  {str(e)[:200]}")

print()
print("=" * 60)
print("10. DataFrameModel with checks via Field")
print("=" * 60)


class SchemaWithChecks(pa.DataFrameModel):
    value: float = pa.Field(ge=0.0, le=1.0)
    category: str = pa.Field(isin=["a", "b", "c"])

    class Config:
        strict = True


t_checks = ibis.memtable(
    pd.DataFrame({"value": [0.5, 0.3], "category": ["a", "b"]})
)
validated_checks = SchemaWithChecks.validate(t_checks)
print(f"Validated with Field checks: {validated_checks.execute()}")

print("\nAll basic experiments completed successfully!")
