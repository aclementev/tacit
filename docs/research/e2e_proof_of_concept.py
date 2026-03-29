"""
End-to-end proof of concept: tacit.DataFrame[S] as ibis.Table subclass.

Tests the three core goals:
1. Static typing works (DataFrame[S] is distinct from ibis.Table)
2. Transparent usage (no unwrap/to_ibis needed — it IS an ibis.Table)
3. Returning without parse() is a type error (distinct type enforces contracts)

This script tests the RUNTIME behavior. Static typing is verified separately
with pyright.
"""
from __future__ import annotations

import ibis
import ibis.expr.types as ir
import ibis.expr.datatypes as dt
import pandera.ibis as pa
import pandas as pd
from typing import Generic, TypeVar, get_type_hints

# ─────────────────────────────────────────────────────────────
# 1. Minimal DataFrame[S] implementation
# ─────────────────────────────────────────────────────────────

S = TypeVar("S")


class DataFrame(ir.Table, Generic[S]):
    """Schema-aware DataFrame. Subclass of ibis.Table with a type parameter."""

    __slots__ = ("_tacit_schema",)

    @classmethod
    def _from_table(cls, table: ir.Table, schema_type: type | None = None) -> "DataFrame[S]":
        """Wrap an existing ibis Table as a typed DataFrame."""
        df = cls(table.op())
        object.__setattr__(df, "_tacit_schema", schema_type)
        return df


# ─────────────────────────────────────────────────────────────
# 2. Minimal Schema base class
# ─────────────────────────────────────────────────────────────

TYPE_MAP = {
    int: dt.int64,
    float: dt.float64,
    str: dt.string,
    bool: dt.boolean,
}


class Schema:
    """Base class for tacit schemas."""

    @classmethod
    def _get_fields(cls) -> dict[str, type]:
        """Get column name → Python type from class annotations."""
        hints = {}
        for klass in reversed(cls.__mro__):
            if klass is Schema or klass is object:
                continue
            hints.update(get_type_hints(klass))
        return hints

    @classmethod
    def _ibis_schema(cls) -> ibis.Schema:
        """Build an ibis Schema from the class annotations."""
        fields = cls._get_fields()
        return ibis.schema({name: TYPE_MAP.get(typ, typ) for name, typ in fields.items()})

    @classmethod
    def _pandera_schema(cls) -> pa.DataFrameSchema:
        """Build a pandera DataFrameSchema for validation."""
        fields = cls._get_fields()
        columns = {}
        for name, typ in fields.items():
            ibis_type = TYPE_MAP.get(typ, typ)
            columns[name] = pa.Column(ibis_type)
        return pa.DataFrameSchema(columns, strict=True)

    @classmethod
    def parse(cls, table: ir.Table) -> DataFrame:
        """Full parsing: coerce types + validate + wrap."""
        # Step 1: Cast column types (handles coercion, e.g., int → float)
        target_schema = cls._ibis_schema()
        cast_map = {}
        for col_name, target_type in target_schema.items():
            actual_type = table.schema()[col_name]
            if actual_type != target_type:
                cast_map[col_name] = target_type
        if cast_map:
            table = table.cast(cast_map)

        # Step 2: Validate with pandera (runs checks against engine)
        pandera_schema = cls._pandera_schema()
        validated = pandera_schema.validate(table)

        # Step 3: Wrap as DataFrame[cls]
        return DataFrame._from_table(validated, schema_type=cls)

    @classmethod
    def cast(cls, table: ir.Table) -> DataFrame:
        """Structural check only: column names + types, zero execution cost."""
        target_schema = cls._ibis_schema()
        actual_schema = table.schema()

        # Check columns exist
        missing = set(target_schema.names) - set(actual_schema.names)
        if missing:
            raise ValueError(f"Missing columns: {missing}")

        # Check no extra columns (strict)
        extra = set(actual_schema.names) - set(target_schema.names)
        if extra:
            raise ValueError(f"Unexpected columns: {extra}")

        # Check types match
        for col_name, expected_type in target_schema.items():
            actual_type = actual_schema[col_name]
            if actual_type != expected_type:
                raise TypeError(
                    f"Column '{col_name}': expected {expected_type}, got {actual_type}"
                )

        return DataFrame._from_table(table, schema_type=cls)


# ─────────────────────────────────────────────────────────────
# 3. Define test schemas
# ─────────────────────────────────────────────────────────────

class Iris(Schema):
    sepal_length: float
    sepal_width: float
    petal_length: float
    petal_width: float
    species: str


class IrisFeatures(Iris):
    sepal_ratio: float
    petal_area: float


# ─────────────────────────────────────────────────────────────
# 4. Run the tests
# ─────────────────────────────────────────────────────────────

def test_parse():
    """Test Schema.parse() — full validation."""
    print("=" * 60)
    print("TEST: Schema.parse()")
    print("=" * 60)

    raw = ibis.memtable(pd.DataFrame({
        "sepal_length": [5.1, 4.9, 4.7],
        "sepal_width": [3.5, 3.0, 3.2],
        "petal_length": [1.4, 1.4, 1.3],
        "petal_width": [0.2, 0.2, 0.2],
        "species": ["setosa", "setosa", "setosa"],
    }))

    df = Iris.parse(raw)
    print(f"  type(df) = {type(df).__name__}")
    print(f"  isinstance(df, ir.Table) = {isinstance(df, ir.Table)}")
    print(f"  isinstance(df, DataFrame) = {isinstance(df, DataFrame)}")
    print(f"  df._tacit_schema = {df._tacit_schema}")
    print(f"  df.columns = {df.columns}")
    print(f"  df.execute() =\n{df.execute()}")
    print()
    return df


def test_transparent_usage(df: DataFrame):
    """Test that DataFrame[S] works transparently as an ibis Table."""
    print("=" * 60)
    print("TEST: Transparent ibis usage (no unwrap needed)")
    print("=" * 60)

    # Direct column access — ibis expression API
    expr = df.sepal_length
    print(f"  df.sepal_length type = {type(expr).__name__}")

    # ibis operations work directly
    mutated = df.mutate(
        sepal_ratio=df.sepal_length / df.sepal_width,
        petal_area=df.petal_length * df.petal_width,
    )
    print(f"  type after mutate() = {type(mutated).__name__}")
    print(f"  isinstance(mutated, ir.Table) = {isinstance(mutated, ir.Table)}")
    print(f"  isinstance(mutated, DataFrame) = {isinstance(mutated, DataFrame)}")

    # Filter works
    filtered = df.filter(df.sepal_length > 4.8)
    print(f"  type after filter() = {type(filtered).__name__}")

    # Select works
    selected = df.select("sepal_length", "species")
    print(f"  type after select() = {type(selected).__name__}")

    # Join works (join with itself as a test)
    joined = df.cross_join(df)
    print(f"  type after join() = {type(joined).__name__}")

    print()
    return mutated


def test_cast_after_transform(mutated: ir.Table):
    """Test Schema.cast() — structural check after transformation."""
    print("=" * 60)
    print("TEST: Schema.cast() after transformation")
    print("=" * 60)

    features = IrisFeatures.cast(mutated)
    print(f"  type(features) = {type(features).__name__}")
    print(f"  isinstance(features, DataFrame) = {isinstance(features, DataFrame)}")
    print(f"  features._tacit_schema = {features._tacit_schema}")
    print(f"  features.columns = {features.columns}")
    print(f"  features.execute() =\n{features.execute()}")
    print()


def test_type_errors():
    """Test that structural mismatches are caught."""
    print("=" * 60)
    print("TEST: Type errors are caught")
    print("=" * 60)

    # Missing column
    bad_table = ibis.memtable(pd.DataFrame({
        "sepal_length": [5.1],
        "species": ["setosa"],
    }))
    try:
        Iris.cast(bad_table)
        print("  ERROR: should have raised for missing columns!")
    except ValueError as e:
        print(f"  Missing columns caught: {e}")

    # Extra column (strict mode)
    extra_table = ibis.memtable(pd.DataFrame({
        "sepal_length": [5.1],
        "sepal_width": [3.5],
        "petal_length": [1.4],
        "petal_width": [0.2],
        "species": ["setosa"],
        "EXTRA": [999],
    }))
    try:
        Iris.cast(extra_table)
        print("  ERROR: should have raised for extra columns!")
    except ValueError as e:
        print(f"  Extra columns caught: {e}")

    # Wrong type
    wrong_type = ibis.memtable(pd.DataFrame({
        "sepal_length": ["not_a_float"],
        "sepal_width": [3.5],
        "petal_length": [1.4],
        "petal_width": [0.2],
        "species": ["setosa"],
    }))
    try:
        Iris.cast(wrong_type)
        print("  ERROR: should have raised for wrong type!")
    except TypeError as e:
        print(f"  Wrong type caught: {e}")

    print()


def test_full_pipeline():
    """Test the full pipeline: parse → transform → cast."""
    print("=" * 60)
    print("TEST: Full pipeline (parse → transform → cast)")
    print("=" * 60)

    # Simulate reading raw data
    raw = ibis.memtable(pd.DataFrame({
        "sepal_length": [5.1, 4.9, 4.7],
        "sepal_width": [3.5, 3.0, 3.2],
        "petal_length": [1.4, 1.4, 1.3],
        "petal_width": [0.2, 0.2, 0.2],
        "species": ["setosa", "setosa", "setosa"],
    }))

    # Parse at boundary (typed world entry)
    iris: DataFrame[Iris] = Iris.parse(raw)
    print(f"  1. Parsed: type={type(iris).__name__}, schema={iris._tacit_schema.__name__}")

    # Transform (drops to ibis.Table)
    transformed = iris.mutate(
        sepal_ratio=iris.sepal_length / iris.sepal_width,
        petal_area=iris.petal_length * iris.petal_width,
    )
    print(f"  2. Transformed: type={type(transformed).__name__}")

    # Cast at boundary (typed world re-entry)
    features: DataFrame[IrisFeatures] = IrisFeatures.cast(transformed)
    print(f"  3. Cast: type={type(features).__name__}, schema={features._tacit_schema.__name__}")
    print(f"  4. Result:\n{features.execute()}")


def test_type_annotation_introspection():
    """Test that we can extract schema type from function annotations."""
    print("=" * 60)
    print("TEST: Type annotation introspection")
    print("=" * 60)

    def engineer_features(df: DataFrame[Iris]) -> DataFrame[IrisFeatures]:
        return df.mutate(
            sepal_ratio=df.sepal_length / df.sepal_width,
            petal_area=df.petal_length * df.petal_width,
        )

    hints = get_type_hints(engineer_features)
    print(f"  hints = {hints}")

    # Can we extract the schema types?
    for param_name, hint in hints.items():
        origin = getattr(hint, "__origin__", None)
        args = getattr(hint, "__args__", None)
        print(f"  {param_name}: origin={origin}, args={args}")

    print()


# ─────────────────────────────────────────────────────────────
# Run all tests
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    df = test_parse()
    mutated = test_transparent_usage(df)
    test_cast_after_transform(mutated)
    test_type_errors()
    test_full_pipeline()
    test_type_annotation_introspection()

    print("=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
