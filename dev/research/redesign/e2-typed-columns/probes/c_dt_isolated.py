"""C. dataclass_transform + descriptor fields, isolated from ibis (plain classes).

Which checker (1) synthesizes __init__ from annotation-only descriptor fields,
(2) uses __set__'s value type as the parameter type, (3) reports missing/extra,
(4) keeps a base-class __init__ from shadowing the synthesized one?
"""

from typing import Any, dataclass_transform, overload, reveal_type


class GetT: ...


class SetT: ...


class Other: ...


class Col[G, S]:
    @overload
    def __get__(self, obj: None, owner: type) -> str: ...
    @overload
    def __get__(self, obj: object, owner: type) -> G: ...
    def __get__(self, obj: object, owner: type) -> Any: ...
    def __set__(self, obj: object, value: S) -> None: ...


@dataclass_transform(kw_only_default=True)
class BaseNoInit: ...


@dataclass_transform(kw_only_default=True)
class BaseWithInit:
    def __init__(self, **kw: Any) -> None: ...


class A(BaseNoInit):
    x: Col[GetT, SetT]
    y: Col[GetT, SetT]


class B(BaseWithInit):
    x: Col[GetT, SetT]
    y: Col[GetT, SetT]


class A2(A):
    z: Col[GetT, SetT]


def probe(a: A, b: B) -> None:
    reveal_type(a.x)  # GetT
    reveal_type(A.x)  # str
    A(x=SetT(), y=SetT())  # ok
    A(x=SetT())  # missing y
    A(x=SetT(), y=SetT(), w=SetT())  # unexpected w
    A(x=GetT(), y=SetT())  # GetT is not SetT (does the checker use __set__?)
    A(x=Other(), y=SetT())  # clearly wrong
    B(x=SetT())  # missing y, base __init__(**kw) defined
    B(x=Other(), y=SetT())
    A2(z=SetT())  # inherited x, y missing
