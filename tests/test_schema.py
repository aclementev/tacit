from typing import Annotated

import ibis.expr.datatypes as dt

from tacit import Check, Nullable, Schema


class Iris(Schema):
    sepal_length: float
    species: str


class IrisFeatures(Iris):
    sepal_ratio: float


class Empty(Schema):
    pass


class AllTypes(Schema):
    i: int
    f: float
    s: str
    b: bool


def test_get_fields_basic():
    assert Iris._get_fields() == {"sepal_length": float, "species": str}


def test_get_fields_inheritance():
    fields = IrisFeatures._get_fields()
    assert fields == {
        "sepal_length": float,
        "species": str,
        "sepal_ratio": float,
    }


def test_get_fields_empty():
    assert Empty._get_fields() == {}


def test_get_fields_all_types():
    assert AllTypes._get_fields() == {
        "i": int,
        "f": float,
        "s": str,
        "b": bool,
    }


def test_ibis_schema_basic():
    schema = Iris._ibis_schema()
    assert schema["sepal_length"] == dt.float64
    assert schema["species"] == dt.string


def test_ibis_schema_all_types():
    schema = AllTypes._ibis_schema()
    assert schema["i"] == dt.int64
    assert schema["f"] == dt.float64
    assert schema["s"] == dt.string
    assert schema["b"] == dt.boolean


def test_ibis_schema_inheritance():
    schema = IrisFeatures._ibis_schema()
    assert schema["sepal_length"] == dt.float64  # from parent
    assert schema["sepal_ratio"] == dt.float64  # from child
    assert schema["species"] == dt.string  # from parent


def test_ibis_schema_empty():
    schema = Empty._ibis_schema()
    assert len(schema) == 0


# --- Annotated constraint extraction ---


class Constrained(Schema):
    amount: Annotated[float, Check.ge(0)]
    status: Annotated[str, Check.isin(["pending", "shipped"])]
    name: str


class MultiCheck(Schema):
    score: Annotated[float, Check.ge(0), Check.le(100)]


class WithNullable(Schema):
    required: str
    optional: Annotated[str, Nullable()]
    explicit_required: Annotated[str, Nullable(False)]


class ConstrainedChild(Constrained):
    extra: int


def test_annotated_extracts_base_type():
    fields = Constrained._get_fields()
    assert fields["amount"] is float
    assert fields["status"] is str
    assert fields["name"] is str


def test_annotated_extracts_checks():
    checks = Constrained._field_checks
    assert "amount" in checks
    assert len(checks["amount"]) == 1
    assert "status" in checks
    assert len(checks["status"]) == 1
    assert "name" not in checks


def test_annotated_extracts_multiple_checks():
    checks = MultiCheck._field_checks
    assert "score" in checks
    assert len(checks["score"]) == 2


def test_nullable_extraction():
    nullable = WithNullable._field_nullable
    assert nullable.get("optional") is True
    assert nullable.get("explicit_required") is False
    assert "required" not in nullable


def test_annotated_ibis_schema_uses_base_type():
    schema = Constrained._ibis_schema()
    assert schema["amount"] == dt.float64
    assert schema["status"] == dt.string


def test_inheritance_preserves_constraints():
    assert "amount" in ConstrainedChild._field_checks
    assert len(ConstrainedChild._field_checks["amount"]) == 1
    fields = ConstrainedChild._get_fields()
    assert fields["extra"] is int
    assert fields["amount"] is float
