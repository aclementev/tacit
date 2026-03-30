import ibis.expr.datatypes as dt

from tacit import Schema


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
