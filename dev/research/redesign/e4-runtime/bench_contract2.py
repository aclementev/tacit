"""Where do the 51us of S.cast() go, and what would caching the target schema save?"""
import timeit, warnings, ibis, functools
import tacit
from tacit import DataFrame
from tacit.contract import _enforce, _get_schema_type
warnings.filterwarnings("ignore")
best = lambda fn, n, r=7: min(timeit.repeat(fn, number=n, repeat=r)) / n * 1e6

class S(tacit.Schema):
    a: int
    b: float
    c: str
tt = ibis.table({"a": "int64", "b": "float64", "c": "string"}, name="T")
df = S.cast(tt)

print("S._ibis_schema() (rebuilt each call)      %.2f us" % best(S._ibis_schema, 5000))
print("tt.schema()                               %.2f us" % best(tt.schema, 50000))
tgt = S._ibis_schema(); act = tt.schema()
print("tgt == act (ibis Schema eq)               %.2f us" % best(lambda: tgt == act, 50000))
print("set(tgt.names) (x2) + diff                %.2f us" % best(lambda: (set(tgt.names) - set(act.names)), 20000))
print("DataFrame._from_table(tt, S)              %.2f us" % best(lambda: tacit.DataFrame._from_table(tt, S), 20000))
print("S.cast(df)  current                       %.2f us" % best(lambda: S.cast(df), 5000))

# fast path: cache target schema, one equality compare, fall back to full diagnostics on mismatch
_cache = {}
def cast_fast(cls, table):
    tgt = _cache.get(cls) or _cache.setdefault(cls, cls._ibis_schema())
    if table.schema() == tgt:
        return DataFrame._from_table(table, cls)
    return cls.cast(table)
print("cast_fast (cached target, eq fast path)   %.2f us" % best(lambda: cast_fast(S, df), 20000))
class W(tacit.Schema): pass
W._fields = {f"c{i}": int for i in range(100)}; W._field_checks = {}; W._field_nullable = {}
w = ibis.table({f"c{i}": "int64" for i in range(100)}, name="W")
print("100 cols: W.cast current                  %.2f us" % best(lambda: W.cast(w), 500))
print("100 cols: cast_fast                       %.2f us" % best(lambda: cast_fast(W, w), 5000))
# end to end contract with both
def f(x: DataFrame[S]) -> DataFrame[S]: return x
import inspect
sig = inspect.signature(f)
def wrapped(x, _enf=None):
    sig.bind(x)
    x = cast_fast(S, x); r = f(x); return cast_fast(S, r)
print("contract(1 param+ret): current            %.2f us" % best(lambda: tacit.contract(f)(df) if False else None, 1))
c = tacit.contract(f)
print("contract(1 param+ret): current            %.2f us" % best(lambda: c(df), 5000))
print("contract: cached sig + cast_fast          %.2f us" % best(lambda: wrapped(df), 20000))
print("contract: no bind + cast_fast             %.2f us" % best(lambda: cast_fast(S, f(cast_fast(S, df))), 20000))
