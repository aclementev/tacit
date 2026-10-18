from tacit import DataFrame, Schema


class Iris(Schema):
    a: int


def to_int(x: DataFrame[Iris]) -> int:
    return x  # mypy: accepted? (fallback_to_any)


def to_str(x: DataFrame[Iris]) -> str:
    return x


def from_int(x: int) -> DataFrame[Iris]:
    return x  # accepted?
