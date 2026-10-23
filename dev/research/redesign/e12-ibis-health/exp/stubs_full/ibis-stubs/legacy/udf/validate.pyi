import ibis.expr.datatypes as dt
from collections.abc import Callable as Callable
from inspect import Signature
from typing import Any

def validate_input_type(input_type: list[dt.DataType], func: Callable) -> Signature: ...
def validate_output_type(output_type: Any) -> None: ...
