import ibis.expr.datatypes as dt
from ibis.common.dispatch import lazy_singledispatch
from typing import Any

__all__ = ['infer', 'normalize']

@lazy_singledispatch
def infer(value: Any) -> dt.DataType: ...
def normalize(typ, value): ...
