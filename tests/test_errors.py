from typing import Annotated

import ibis
import pandera.ibis as pa
import pytest

from tacit import Check, DataFrame, Schema, contract
from tacit.errors import (
    CheckExecutionError,
    CoercionError,
    ConstraintError,
    StructuralError,
    ValidationError,
    ValidationPhase,
)


class Order(Schema):
    amount: Annotated[float, Check.ge(0)]
    status: str


class OrderOut(Order):
    total: float


class ExplodingCheck(Schema):
    value: Annotated[int, pa.Check(lambda _: 1 / 0, error="boom")]


def test_cast_missing_columns_raises_structural_error():
    with pytest.raises(StructuralError) as exc_info:
        Order.cast(ibis.memtable({"amount": [1.0]}))

    exc = exc_info.value
    assert exc.phase is ValidationPhase.CAST
    assert exc.schema is Order
    assert exc.original is None
    assert exc.boundary_label is None
    assert "missing columns ['status']" in str(exc)


def test_cast_multiple_type_mismatches_reported_in_message():
    with pytest.raises(StructuralError) as exc_info:
        Order.cast(ibis.memtable({"amount": ["bad"], "status": [1]}))

    exc = exc_info.value
    assert exc.phase is ValidationPhase.CAST
    assert exc.column is None
    assert "amount expected float64, got string" in str(exc)
    assert "status expected string, got int64" in str(exc)


def test_parse_coercion_failure_raises_coercion_error():
    with pytest.raises(CoercionError) as exc_info:
        Order.parse(ibis.memtable({"amount": ["bad"], "status": ["pending"]}))

    exc = exc_info.value
    assert exc.phase is ValidationPhase.PARSE
    assert exc.schema is Order
    assert exc.column == "amount"
    assert exc.original is not None
    assert exc_info.value.__cause__ is exc.original
    assert "failed to cast column 'amount' to float64" in str(exc)


def test_parse_unrelated_execution_failure_after_cast_is_not_coercion_error():
    class SingleFloat(Schema):
        a: float

    with pytest.raises(ValidationError) as exc_info:
        SingleFloat.parse(ibis.table({"a": "int64"}, name="nonexistent"))

    exc = exc_info.value
    assert type(exc) is ValidationError
    assert not isinstance(exc, CoercionError)
    assert exc.phase is ValidationPhase.PARSE
    assert exc.schema is SingleFloat
    assert exc.original is not None
    assert exc_info.value.__cause__ is exc.original
    assert "unbound tables" in str(exc).lower()


def test_parse_polars_coercion_failure_raises_coercion_error_when_backend_available():
    import polars as pl

    con = ibis.polars.connect()
    table = con.create_table(
        "orders_tmp",
        pl.DataFrame(
            {
                "amount": ["bad", "-1", "10"],
                "status": ["pending", None, "pending"],
            }
        ),
        overwrite=True,
    )

    with pytest.raises(CoercionError) as exc_info:
        Order.parse(table)

    exc = exc_info.value
    assert exc.phase is ValidationPhase.PARSE
    assert exc.schema is Order
    assert exc.original is not None
    assert exc_info.value.__cause__ is exc.original
    assert "failed to cast column 'amount' to float64" in str(exc)


def test_parse_constraint_failure_raises_constraint_error():
    with pytest.raises(ConstraintError) as exc_info:
        Order.parse(ibis.memtable({"amount": [-1.0], "status": ["pending"]}))

    exc = exc_info.value
    assert exc.phase is ValidationPhase.PARSE
    assert exc.schema is Order
    assert exc.reason_code == "dataframe_check"
    assert exc.column == "amount"
    assert exc.check is not None
    assert exc.original is not None
    assert exc_info.value.__cause__ is exc.original
    assert "column 'amount' failed check" in str(exc)


def test_parse_check_execution_failure_raises_check_execution_error():
    with pytest.raises(CheckExecutionError) as exc_info:
        ExplodingCheck.parse(ibis.memtable({"value": [1, 2, 3]}))

    exc = exc_info.value
    assert exc.phase is ValidationPhase.PARSE
    assert exc.schema is ExplodingCheck
    assert exc.reason_code == "check_error"
    assert exc.original is not None
    assert exc_info.value.__cause__ is exc.original
    assert "check boom raised ZeroDivisionError" in str(exc)


def test_contract_recontextualizes_structural_input_error():
    @contract
    def fn(df: DataFrame[Order]) -> DataFrame[Order]:
        return df

    with pytest.raises(StructuralError) as exc_info:
        fn(ibis.memtable({"amount": [1.0]}))

    exc = exc_info.value
    assert exc.phase is ValidationPhase.CONTRACT_INPUT
    assert exc.boundary_label == "parameter 'df'"
    assert exc.original is None
    assert isinstance(exc_info.value.__cause__, StructuralError)
    assert "on parameter 'df'" in str(exc)


def test_contract_recontextualizes_validated_input_error_with_root_original():
    @contract(validate=True)
    def fn(df: DataFrame[Order]) -> DataFrame[Order]:
        return df

    with pytest.raises(ConstraintError) as exc_info:
        fn(ibis.memtable({"amount": [-1.0], "status": ["pending"]}))

    exc = exc_info.value
    assert exc.phase is ValidationPhase.CONTRACT_INPUT
    assert exc.boundary_label == "parameter 'df'"
    assert exc.original is not None
    assert isinstance(exc_info.value.__cause__, ConstraintError)
    assert exc_info.value.__cause__ is not exc.original
    assert "on parameter 'df'" in str(exc)


def test_contract_recontextualizes_return_error():
    @contract(returns=OrderOut, validate=True)
    def fn(df: DataFrame[Order]):
        return df

    with pytest.raises(StructuralError) as exc_info:
        fn(ibis.memtable({"amount": [1.0], "status": ["pending"]}))

    exc = exc_info.value
    assert exc.phase is ValidationPhase.CONTRACT_OUTPUT
    assert exc.boundary_label == "return value"
    assert isinstance(exc_info.value.__cause__, StructuralError)
    assert "on return value" in str(exc)


def test_all_validation_errors_share_common_base_class():
    with pytest.raises(ValidationError):
        Order.cast(ibis.memtable({"amount": [1.0]}))
