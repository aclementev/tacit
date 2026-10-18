"""Is the __tacit_type_is_invariant__ hack needed? Variants of DataFrame over real ir.Table."""
from typing import Any, Generic, TypeVar
import ibis.expr.types as ir
from tacit import Schema


class Parent(Schema):
    a: int


class Child(Parent):
    b: int


# V1: PEP 695, no hack (phantom param)
class V1[S: Schema](ir.Table):
    __slots__ = ()


# V2: PEP 695 + hack (what tacit does)
class V2[S: Schema](ir.Table):
    __slots__ = ()
    def __tacit_type_is_invariant__(self, x: S) -> S: ...


# V3: legacy TypeVar (explicitly invariant by default), no hack
T = TypeVar("T", bound=Schema)


class V3(ir.Table, Generic[T]):
    __slots__ = ()


# V4: PEP 695 with Any base (mypy case) + hack, no ibis involved
class V4[S: Schema](Any):
    def __tacit_type_is_invariant__(self, x: S) -> S: ...


# V5: legacy TypeVar with Any base
class V5(Any, Generic[T]):
    pass


# V6: PEP 695 explicit invariant? (no syntax) -> legacy with explicit variance defaults
def v1(x: V1[Child]) -> V1[Parent]: return x  # L40
def v2(x: V2[Child]) -> V2[Parent]: return x  # L41
def v3(x: V3[Child]) -> V3[Parent]: return x  # L42
def v4(x: V4[Child]) -> V4[Parent]: return x  # L43
def v5(x: V5[Child]) -> V5[Parent]: return x  # L44
