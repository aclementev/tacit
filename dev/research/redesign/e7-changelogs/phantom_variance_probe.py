"""PEP 695 syntax with an UNUSED (phantom) type parameter, as tacit's DataFrame[S] has.
Does auto-variance break the invariance tacit relies on? (Expect: errors on lines marked ERR)"""
from typing import Generic, TypeVar
import ibis.expr.types as ir

class Iris: ...
class IrisFeatures(Iris): ...

class DF695[S](ir.Table):             # PEP 695: variance inferred, S unused
    pass

S_ = TypeVar("S_")
class DFOld(ir.Table, Generic[S_]):   # tacit today: invariant TypeVar
    pass

def need_features_695(d: DF695[IrisFeatures]) -> None: ...
def need_iris_695(d: DF695[Iris]) -> None: ...
def need_features_old(d: DFOld[IrisFeatures]) -> None: ...
def need_iris_old(d: DFOld[Iris]) -> None: ...

def run(a: DF695[Iris], b: DF695[IrisFeatures], c: DFOld[Iris], d: DFOld[IrisFeatures]) -> None:
    need_features_695(a)   # ERR (Iris -> IrisFeatures)
    need_iris_695(b)       # ERR for strict invariance
    need_features_old(c)   # ERR
    need_iris_old(d)       # ERR
