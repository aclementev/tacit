from typing import Any, reveal_type
from typing_extensions import TypeForm

def parse_as[T](form: TypeForm[T], value: Any) -> T: ...

class Iris: ...

reveal_type(parse_as(int, 1))
reveal_type(parse_as(Iris, 1))
reveal_type(parse_as(list[int] | None, 1))
