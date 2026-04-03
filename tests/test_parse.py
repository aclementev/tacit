from typing import Annotated

import ibis
import pandera.errors
import pandera.ibis as pa
import pytest

from tacit import Check, DataFrame, Nullable, Schema


class Iris(Schema):
    sepal_length: float
    species: str


def _iris_table() -> ibis.Table:
    return ibis.memtable({"sepal_length": [5.1, 4.9], "species": ["setosa", "setosa"]})


def test_cast_returns_dataframe():
    df = Iris.cast(_iris_table())
    assert isinstance(df, DataFrame)


def test_cast_preserves_data():
    df = Iris.cast(_iris_table())
    result = df.execute()
    assert len(result) == 2
    assert list(result["sepal_length"]) == [5.1, 4.9]


def test_cast_sets_tacit_schema():
    df = Iris.cast(_iris_table())
    assert df._tacit_schema is Iris


def test_cast_does_not_execute_query():
    """cast() only inspects metadata — it should work on unexecutable expressions."""
    table = ibis.table({"sepal_length": "float64", "species": "string"}, name="nonexistent")
    df = Iris.cast(table)
    assert isinstance(df, DataFrame)


def test_cast_rejects_missing_columns():
    table = ibis.memtable({"species": ["setosa"]})
    with pytest.raises(ValueError, match="sepal_length"):
        Iris.cast(table)


def test_cast_rejects_multiple_missing_columns():
    table = ibis.memtable({"unrelated": [1]})
    with pytest.raises(ValueError, match="Missing columns"):
        Iris.cast(table)


def test_cast_rejects_extra_columns():
    table = ibis.memtable({
        "sepal_length": [5.1],
        "species": ["setosa"],
        "EXTRA": [999],
    })
    with pytest.raises(ValueError, match="EXTRA"):
        Iris.cast(table)


def test_cast_rejects_wrong_type():
    table = ibis.memtable({
        "sepal_length": ["not_a_float"],
        "species": ["setosa"],
    })
    with pytest.raises(TypeError, match=r"sepal_length.*float64.*string"):
        Iris.cast(table)


def test_cast_reports_all_type_mismatches():
    """All mismatched columns are reported, not just the first."""
    table = ibis.memtable({
        "sepal_length": ["bad"],
        "species": [123],
    })
    with pytest.raises(TypeError) as exc_info:
        Iris.cast(table)
    msg = str(exc_info.value)
    assert "sepal_length" in msg
    assert "species" in msg


def test_cast_checks_missing_before_types():
    """Missing columns are caught before type checking (can't check types on absent columns)."""
    table = ibis.memtable({"species": [123]})
    with pytest.raises(ValueError, match="Missing"):
        Iris.cast(table)


def test_cast_checks_extra_before_types():
    """Extra columns are caught before type checking."""
    table = ibis.memtable({
        "sepal_length": [5.1],
        "species": ["setosa"],
        "bonus": [1],
        "extra": [2],
    })
    with pytest.raises(ValueError, match="Extra"):
        Iris.cast(table)


# --- parse() tests ---


def test_parse_returns_dataframe():
    df = Iris.parse(_iris_table())
    assert isinstance(df, DataFrame)


def test_parse_preserves_data():
    df = Iris.parse(_iris_table())
    result = df.execute()
    assert len(result) == 2
    assert list(result["sepal_length"]) == [5.1, 4.9]


def test_parse_sets_tacit_schema():
    df = Iris.parse(_iris_table())
    assert df._tacit_schema is Iris


def test_parse_coerces_compatible_types():
    """parse() handles int64 → float64 coercion (cast() would reject this)."""
    table = ibis.memtable({"sepal_length": [5, 4], "species": ["setosa", "setosa"]})
    df = Iris.parse(table)
    result = df.execute()
    assert list(result["sepal_length"]) == [5.0, 4.0]


def test_parse_rejects_missing_columns():
    table = ibis.memtable({"species": ["setosa"]})
    with pytest.raises(ValueError, match="sepal_length"):
        Iris.parse(table)


def test_parse_rejects_extra_columns():
    table = ibis.memtable({
        "sepal_length": [5.1],
        "species": ["setosa"],
        "EXTRA": [999],
    })
    with pytest.raises(ValueError, match="EXTRA"):
        Iris.parse(table)


def test_pandera_schema_has_strict_mode():
    schema = Iris._pandera_schema()
    assert schema.strict is True


def test_pandera_schema_has_expected_columns():
    schema = Iris._pandera_schema()
    assert set(schema.columns.keys()) == {"sepal_length", "species"}


def test_pandera_schema_defaults_non_nullable():
    schema = Iris._pandera_schema()
    for col in schema.columns.values():
        assert col.nullable is False


# --- Constraint validation via parse() ---


class Order(Schema):
    amount: Annotated[float, Check.ge(0)]
    status: Annotated[str, Check.isin(["pending", "shipped"])]


class BoundedScore(Schema):
    score: Annotated[float, Check.ge(0), Check.le(100)]


class WithNullable(Schema):
    required: str
    optional: Annotated[str, Nullable()]


class ConstrainedParent(Schema):
    value: Annotated[float, Check.gt(0)]


class ConstrainedChild(ConstrainedParent):
    name: str


def _order_table(**overrides: list) -> ibis.Table:
    data = {"amount": [10.0, 20.0], "status": ["pending", "shipped"]}
    data.update(overrides)
    return ibis.memtable(data)


def test_parse_passes_when_constraints_satisfied():
    df = Order.parse(_order_table())
    result = df.execute()
    assert len(result) == 2


def test_parse_rejects_ge_violation():
    table = _order_table(amount=[-5.0, 10.0])
    with pytest.raises(pandera.errors.SchemaError, match="amount"):
        Order.parse(table)


def test_parse_rejects_isin_violation():
    table = _order_table(status=["pending", "INVALID"])
    with pytest.raises(pandera.errors.SchemaError, match="status"):
        Order.parse(table)


def test_parse_rejects_multiple_checks_on_same_column():
    table = ibis.memtable({"score": [150.0]})
    with pytest.raises(pandera.errors.SchemaError, match="score"):
        BoundedScore.parse(table)


def test_parse_passes_multiple_checks_when_valid():
    table = ibis.memtable({"score": [50.0, 0.0, 100.0]})
    df = BoundedScore.parse(table)
    assert len(df.execute()) == 3


def test_parse_rejects_null_by_default():
    table = ibis.memtable({"sepal_length": [5.1, None], "species": ["setosa", "setosa"]})
    with pytest.raises(pandera.errors.SchemaError, match="sepal_length"):
        Iris.parse(table)


def test_parse_accepts_null_when_nullable():
    table = ibis.memtable({"required": ["a", "b"], "optional": ["x", None]})
    df = WithNullable.parse(table)
    assert len(df.execute()) == 2


def test_parse_rejects_null_on_required_field():
    table = ibis.memtable({"required": ["a", None], "optional": ["x", "y"]})
    with pytest.raises(pandera.errors.SchemaError, match="required"):
        WithNullable.parse(table)


def test_parse_enforces_inherited_constraints():
    table = ibis.memtable({"value": [-1.0], "name": ["test"]})
    with pytest.raises(pandera.errors.SchemaError, match="value"):
        ConstrainedChild.parse(table)


def test_parse_passes_inherited_constraints_when_valid():
    table = ibis.memtable({"value": [1.0], "name": ["test"]})
    df = ConstrainedChild.parse(table)
    assert len(df.execute()) == 1
