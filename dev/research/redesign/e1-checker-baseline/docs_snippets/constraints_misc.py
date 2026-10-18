from typing import Annotated
from tacit import Check, Nullable, Schema

class Misc(Schema):
    a: Annotated[float, Check.between(-40, 85)]
    score: Annotated[float, Check.in_range(0, 1, include_min=False, include_max=False)]
    b: Annotated[float, Nullable(), Check.gt(0)]
    c: Annotated[int, Check.ge(0, error="age must be non-negative")]


class UserProfile(Schema):
    age: Annotated[int, Check.ge(0), Check.lt(200)]
    email: Annotated[str, Check.str_contains("@"), Check.str_length(min_value=5)]
    score: Annotated[float, Check.gt(0), Check.lt(1000), Check.ne(42.0)]


class Event(Schema):
    event_type: str                                    # not nullable (default)
    payload: Annotated[str, Nullable()]                # nullable
    priority: Annotated[int, Nullable(allow=False)]    # explicitly not nullable

def is_even(x: int) -> bool:
    return x % 2 == 0

class MySchema(Schema):
    count: Annotated[int, Check(is_even, element_wise=True)]
