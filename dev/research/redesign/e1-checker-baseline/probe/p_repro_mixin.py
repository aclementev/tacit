from typing import reveal_type

try:
    from rich.jupyter import JupyterMixin
except ImportError:

    class M:
        pass
else:

    class M(JupyterMixin):
        pass


class Base(M):
    def __getattr__(self, k: str) -> int: ...


class D(Base): ...


def f(d: D, b: Base):
    reveal_type(d.x)
    reveal_type(b.x)


def g(b: Base) -> D:
    return b  # error expected: Base is not a D


# control: unconditional mixin
class N: ...


class Base2(N):
    def __getattr__(self, k: str) -> int: ...


class D2(Base2): ...


def f2(d: D2):
    reveal_type(d.x)


def g2(b: Base2) -> D2:
    return b  # error expected
