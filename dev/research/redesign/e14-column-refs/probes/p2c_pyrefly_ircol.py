# ruff: noqa
import ibis.expr.types as ir
from ibis.expr.types.generic import Column, Value
class X: ...
a: ir.Column = X()
b: ir.Value = X()
c: Column = X()
d: ir.BooleanColumn = X()
e: ir.Table = X()
