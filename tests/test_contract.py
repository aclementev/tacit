import ibis
import pytest

from tacit import DataFrame, Schema, contract


class Iris(Schema):
    sepal_length: float
    species: str


class IrisFeatures(Iris):
    sepal_ratio: float


def _iris_table() -> ibis.Table:
    return ibis.memtable({"sepal_length": [5.1, 4.9], "species": ["setosa", "setosa"]})


def _iris_features_table() -> ibis.Table:
    return ibis.memtable({
        "sepal_length": [5.1, 4.9],
        "species": ["setosa", "setosa"],
        "sepal_ratio": [1.0, 1.0],
    })


# --- Default behavior (cast) ---


def test_contract_casts_input():
    @contract
    def fn(df: DataFrame[Iris]) -> DataFrame[Iris]:
        assert isinstance(df, DataFrame)
        assert df._tacit_schema is Iris
        return df

    fn(_iris_table())


def test_contract_casts_output():
    @contract
    def fn(df: DataFrame[Iris]) -> DataFrame[Iris]:
        return df

    result = fn(_iris_table())
    assert isinstance(result, DataFrame)
    assert result._tacit_schema is Iris


def test_contract_casts_input_and_output_schemas():
    @contract
    def transform(df: DataFrame[Iris]) -> DataFrame[IrisFeatures]:
        return df.mutate(sepal_ratio=df.sepal_length / 1.0)

    result = transform(_iris_table())
    assert isinstance(result, DataFrame)
    assert result._tacit_schema is IrisFeatures


def test_contract_does_not_execute_query():
    """Default cast mode only inspects metadata — works on unexecutable expressions."""
    table = ibis.table({"sepal_length": "float64", "species": "string"}, name="nonexistent")

    @contract
    def fn(df: DataFrame[Iris]) -> DataFrame[Iris]:
        return df

    result = fn(table)
    assert isinstance(result, DataFrame)


# --- validate=True (parse) ---


def test_contract_validate_parses_input():
    @contract(validate=True)
    def fn(df: DataFrame[Iris]) -> DataFrame[Iris]:
        assert isinstance(df, DataFrame)
        assert df._tacit_schema is Iris
        return df

    fn(_iris_table())


def test_contract_validate_coerces_types():
    """parse() coerces int64 → float64; cast() would reject this."""
    table = ibis.memtable({"sepal_length": [5, 4], "species": ["setosa", "setosa"]})

    @contract(validate=True)
    def fn(df: DataFrame[Iris]) -> DataFrame[Iris]:
        return df

    result = fn(table)
    data = result.execute()
    assert list(data["sepal_length"]) == [5.0, 4.0]


# --- Mixed params ---


def test_contract_passes_through_non_dataframe_params():
    @contract
    def fn(df: DataFrame[Iris], multiplier: float) -> DataFrame[IrisFeatures]:
        return df.mutate(sepal_ratio=df.sepal_length * multiplier)

    result = fn(_iris_table(), multiplier=2.0)
    assert isinstance(result, DataFrame)
    data = result.execute()
    assert list(data["sepal_ratio"]) == [10.2, 9.8]


def test_contract_passes_through_non_dataframe_return():
    @contract
    def fn(df: DataFrame[Iris]) -> int:
        return 42

    assert fn(_iris_table()) == 42


def test_contract_with_no_annotations_raises():
    """@contract with no DataFrame annotations is a programming error."""
    with pytest.raises(TypeError, match=r"no DataFrame\[S\] annotations"):

        @contract
        def fn(x, y):
            return x + y


def test_contract_with_kwargs():
    @contract
    def fn(df: DataFrame[Iris], *, verbose: bool = False) -> DataFrame[Iris]:
        return df

    result = fn(_iris_table(), verbose=True)
    assert isinstance(result, DataFrame)


# --- Error cases ---


def test_contract_input_missing_columns():
    @contract
    def fn(df: DataFrame[Iris]) -> DataFrame[Iris]:
        return df

    table = ibis.memtable({"species": ["setosa"]})
    with pytest.raises(ValueError, match=r"parameter 'df'.*Iris"):
        fn(table)


def test_contract_input_extra_columns():
    @contract
    def fn(df: DataFrame[Iris]) -> DataFrame[Iris]:
        return df

    table = ibis.memtable({
        "sepal_length": [5.1],
        "species": ["setosa"],
        "EXTRA": [1],
    })
    with pytest.raises(ValueError, match=r"parameter 'df'.*Iris"):
        fn(table)


def test_contract_input_wrong_type():
    @contract
    def fn(df: DataFrame[Iris]) -> DataFrame[Iris]:
        return df

    table = ibis.memtable({"sepal_length": ["bad"], "species": ["setosa"]})
    with pytest.raises(TypeError, match=r"parameter 'df'.*Iris"):
        fn(table)


def test_contract_output_schema_mismatch():
    @contract
    def fn(df: DataFrame[Iris]) -> DataFrame[IrisFeatures]:
        return df

    with pytest.raises((ValueError, TypeError), match=r"return value.*IrisFeatures"):
        fn(_iris_table())


def test_contract_input_not_a_table():
    @contract
    def fn(df: DataFrame[Iris]) -> DataFrame[Iris]:
        return df

    with pytest.raises(TypeError, match=r"parameter 'df'.*Iris.*got str"):
        fn("not a table")


def test_contract_preserves_function_metadata():
    @contract
    def my_transform(df: DataFrame[Iris]) -> DataFrame[Iris]:
        """My docstring."""
        return df

    assert my_transform.__name__ == "my_transform"
    assert my_transform.__doc__ == "My docstring."


# --- returns= parameter ---


def test_contract_returns_param_casts_output():
    @contract(returns=IrisFeatures)
    def fn(df: DataFrame[Iris]):
        return df.mutate(sepal_ratio=df.sepal_length / 1.0)

    result = fn(_iris_table())
    assert isinstance(result, DataFrame)
    assert result._tacit_schema is IrisFeatures


def test_contract_returns_param_validates_output():
    @contract(returns=IrisFeatures, validate=True)
    def fn(df: DataFrame[Iris]):
        return df.mutate(sepal_ratio=df.sepal_length / 1.0)

    result = fn(_iris_table())
    assert isinstance(result, DataFrame)
    assert result._tacit_schema is IrisFeatures


def test_contract_returns_param_still_checks_input():
    @contract(returns=Iris)
    def fn(df: DataFrame[Iris]):
        assert isinstance(df, DataFrame)
        assert df._tacit_schema is Iris
        return df

    fn(_iris_table())


def test_contract_returns_param_overrides_annotation():
    """returns= takes precedence over the return type annotation."""

    @contract(returns=IrisFeatures)
    def fn(df: DataFrame[Iris]) -> DataFrame[Iris]:
        return df.mutate(sepal_ratio=df.sepal_length / 1.0)

    result = fn(_iris_table())
    assert result._tacit_schema is IrisFeatures


def test_contract_returns_param_output_schema_mismatch():
    @contract(returns=IrisFeatures)
    def fn(df: DataFrame[Iris]):
        return df

    with pytest.raises((ValueError, TypeError), match=r"return value.*IrisFeatures"):
        fn(_iris_table())
