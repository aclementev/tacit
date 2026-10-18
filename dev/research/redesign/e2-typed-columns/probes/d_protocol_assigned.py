"""D follow-up: does assigning the field specifier make pyright match the protocol?"""
from typing import Protocol, reveal_type

from proto.aliases_facade import Float64, NumCol
from proto.frame import Frame, column


class HasSepal(Protocol):
    @property
    def sepal_length(self) -> NumCol: ...


class IrisA(Frame):
    sepal_length: Float64 = column()


def f[F: HasSepal](df: F) -> F:
    return df


def probe(a: IrisA) -> None:
    reveal_type(f(a))
    reveal_type(a.sepal_length)
    IrisA()  # still required?


# Protocol declared with the tacit alias itself (declared types match exactly)
class HasSepal2(Protocol):
    sepal_length: Float64


def g[F: HasSepal2](df: F) -> F:
    reveal_type(df.sepal_length)
    return df


def probe2(a: IrisA) -> None:
    reveal_type(g(a))
