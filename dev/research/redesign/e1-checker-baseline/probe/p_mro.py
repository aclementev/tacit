import ibis
import ibis.expr.types as ir
from typing import reveal_type

reveal_type(ir.Table.__mro__)
reveal_type(ir.Column)
reveal_type(ir.NumericColumn)
reveal_type(ir.Expr)
reveal_type(ir.Table.__getattr__)
reveal_type(ir.Table.mutate)


class A(ir.Table): ...


class B[T](ir.Table):
    def inv(self, x: T) -> T: ...


def f(t: ir.Table) -> A:
    return t


def g(x: str) -> A:
    return x


def h(x: int) -> B[int]:
    return x


def i(t: ir.Table) -> B[int]:
    return t


class Plain: ...


class C(Plain): ...


def j(p: Plain) -> C:
    return p
