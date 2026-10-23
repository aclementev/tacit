import ibis.expr.datatypes.core as dt
from public import public

__all__ = ['parse']

@public
def parse(text: str, default_decimal_parameters: tuple[int | None, int | None] = (None, None)) -> dt.DataType: ...
