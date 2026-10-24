# Probe: one generic marker at two levels (NumericValue=_Fam[float], IntegerValue=_Fam[int]): pyright/mypy take the
# first base, so IntegerColumn is not _Fam[int]. Hence L2 gives each family class exactly one marker.
from famstub import _Fam, IntegerColumn, FloatingColumn, StringValue, NumericValue, BooleanValue
def want_int(x: _Fam[int]) -> None: ...
def want_float(x: _Fam[float]) -> None: ...
def want_str(x: _Fam[str]) -> None: ...
def f(i: IntegerColumn, fl: FloatingColumn, s: StringValue, n: NumericValue, b: BooleanValue) -> None:
    want_int(i)    # ok
    want_float(i)  # ok
    want_int(fl)   # E
    want_str(i)    # E
    want_float(fl) # ok
    want_str(s)    # ok
    want_float(s)  # E
    want_int(n)    # E
    want_int(b)    # ok (bool is int)
    want_str(b)    # E
