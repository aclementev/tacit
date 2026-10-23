from ibis.expr import types as ir
from ibis.expr.types.generic import Column, Scalar, Value
from typing import Literal

__all__ = ['BinaryValue', 'BinaryScalar', 'BinaryColumn']

class BinaryValue(Value):
    def hashbytes(self, how: Literal['md5', 'sha1', 'sha256', 'sha512'] = 'sha256', /) -> ir.BinaryValue: ...

class BinaryScalar(Scalar, BinaryValue): ...
class BinaryColumn(Column, BinaryValue): ...
