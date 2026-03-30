import ibis
import ibis.expr.types as ir

from tacit import DataFrame, Schema


class Iris(Schema):
    sepal_length: float
    species: str


def _make_iris_df() -> DataFrame[Iris]:
    table = ibis.memtable({"sepal_length": [5.1, 4.9], "species": ["setosa", "setosa"]})
    return DataFrame._from_table(table, Iris)


def test_isinstance_ir_table():
    df = _make_iris_df()
    assert isinstance(df, ir.Table)


def test_isinstance_dataframe():
    df = _make_iris_df()
    assert isinstance(df, DataFrame)


def test_tacit_schema_attribute():
    df = _make_iris_df()
    assert df._tacit_schema is Iris


def test_columns_match_table():
    df = _make_iris_df()
    assert set(df.columns) == {"sepal_length", "species"}


def test_column_access_returns_ibis_expr():
    df = _make_iris_df()
    assert isinstance(df.sepal_length, ir.FloatingColumn)
    assert isinstance(df.species, ir.StringColumn)


def test_mutate_returns_plain_table():
    df = _make_iris_df()
    result = df.mutate(x=ibis.literal(1))
    assert type(result) is ir.Table
    assert not isinstance(result, DataFrame)


def test_filter_returns_plain_table():
    df = _make_iris_df()
    result = df.filter(df.sepal_length > 5.0)
    assert type(result) is ir.Table


def test_select_returns_plain_table():
    df = _make_iris_df()
    result = df.select("sepal_length")
    assert type(result) is ir.Table


def test_group_by_agg_returns_plain_table():
    df = _make_iris_df()
    result = df.group_by("species").agg(mean_sl=df.sepal_length.mean())
    assert type(result) is ir.Table


def test_execute_returns_pandas():
    df = _make_iris_df()
    result = df.execute()
    assert len(result) == 2
    assert list(result.columns) == ["sepal_length", "species"]
