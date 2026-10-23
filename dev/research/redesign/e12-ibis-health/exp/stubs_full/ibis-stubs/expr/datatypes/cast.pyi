import ibis.expr.datatypes.core as dt
from collections.abc import Iterable
from public import public
from typing import Any

__all__ = ['cast', 'castable', 'higher_precedence', 'highest_precedence']

@public
def cast(source: str | dt.DataType, target: str | dt.DataType, **kwargs) -> dt.DataType: ...
@public
def castable(source: dt.DataType, target: dt.DataType, value: Any = None) -> bool: ...
@public
def higher_precedence(left: dt.DataType, right: dt.DataType) -> dt.DataType: ...
@public
def highest_precedence(dtypes: Iterable[dt.DataType]) -> dt.DataType: ...
