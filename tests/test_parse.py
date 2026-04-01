import ibis
import pytest

from tacit import DataFrame, Schema


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
