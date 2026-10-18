"""Q4: @contract overhead + cast() on deep expressions."""
import functools, inspect, timeit, statistics, warnings
import ibis, ibis.expr.types as ir
import tacit
from tacit import DataFrame
from tacit.contract import _enforce, _get_schema_type
from typing import get_type_hints
warnings.filterwarnings("ignore")

class S(tacit.Schema):
    a: int
    b: float
    c: str

def best(fn, number, repeat=7):
    return min(timeit.repeat(fn, number=number, repeat=repeat)) / number

t = ibis.memtable({"a": [1, 2], "b": [1.0, 2.0], "c": ["x", "y"]})
tt = ibis.table({"a": "int64", "b": "float64", "c": "string"}, name="T")   # unbound table
df = S.cast(tt)

def plain(x): return x
@tacit.contract
def c1(x: DataFrame[S]) -> DataFrame[S]: return x
@tacit.contract
def c2(x: DataFrame[S], y: DataFrame[S]) -> DataFrame[S]: return x
@tacit.contract(returns=S)
def c3(x: DataFrame[S]) -> ir.Table: return x

def wrap_cached(fn, *, validate=False, returns=None):
    """Same as tacit.contract._wrap but inspect.signature(fn) hoisted out of the wrapper."""
    hints = get_type_hints(fn); ret = hints.pop("return", None)
    param_schemas = {n: s for n, h in hints.items() if (s := _get_schema_type(h)) is not None}
    return_schema = returns or (_get_schema_type(ret) if ret else None)
    sig = inspect.signature(fn)                                  # <-- once
    names = tuple(sig.parameters)
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        bound = sig.bind(*args, **kwargs); bound.apply_defaults()
        for p, st in param_schemas.items():
            bound.arguments[p] = _enforce(bound.arguments[p], st, validate=validate, label=f"parameter '{p}'")
        r = fn(*bound.args, **bound.kwargs)
        return _enforce(r, return_schema, validate=validate, label="return value") if return_schema else r
    return wrapper

def wrap_fast(fn, *, returns=None):
    """Cached signature AND positional fast path (no bind) -- only valid when args are passed positionally."""
    hints = get_type_hints(fn); ret = hints.pop("return", None)
    names = list(inspect.signature(fn).parameters)
    idx = {n: names.index(n) for n, h in hints.items() if _get_schema_type(h) is not None}
    sch = {n: _get_schema_type(hints[n]) for n in idx}
    return_schema = returns or (_get_schema_type(ret) if ret else None)
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if kwargs or len(args) < len(names):               # fall back
            return wrap_cached(fn, returns=returns)(*args, **kwargs)
        args = list(args)
        for n, i in idx.items():
            args[i] = _enforce(args[i], sch[n], validate=False, label=f"parameter '{n}'")
        r = fn(*args)
        return _enforce(r, return_schema, validate=False, label="return value") if return_schema else r
    return wrapper

def c1_cached_src(x: DataFrame[S]) -> DataFrame[S]: return x
c1c = wrap_cached(c1_cached_src)
c1f = wrap_fast(c1_cached_src)

N = 20000
print("### per-call cost (microseconds, min of 7 repeats)")
rows = [
    ("plain function call", lambda: plain(df)),
    ("inspect.signature(fn) alone", lambda: inspect.signature(plain)),
    ("inspect.signature(fn).bind(df)", lambda: inspect.signature(plain).bind(df)),
    ("S.cast(df)  [3 cols, matching]", lambda: S.cast(df)),
    ("S.cast(df) of bound memtable (unbound -> .schema())", lambda: S.cast(df)),
    ("@contract 1 param + return (cast x2)", lambda: c1(df)),
    ("@contract 2 params + return (cast x3)", lambda: c2(df, df)),
    ("@contract(returns=S) 1 param", lambda: c3(df)),
    ("same, signature cached (wrap_cached)", lambda: c1c(df)),
    ("same, cached + no bind (wrap_fast)", lambda: c1f(df)),
]
base = None
for name, fn in rows:
    us = best(fn, N) * 1e6
    base = base or us
    print(f"{name:55s} {us:9.2f} us")

print("\n### deep expression: 50 chained mutates on the SAME column, 3-col table")
def chain(depth, width=3):
    x = ibis.table({f"c{i}": "int64" for i in range(width)}, name="W")
    for i in range(depth):
        x = x.mutate(c0=x.c0 + 1)
    return x
class W3(tacit.Schema):
    c0: int; c1: int; c2: int
print(f"{'depth':>6} {'build chain (ms)':>18} {'.schema() (us)':>16} {'W3.cast() (us)':>16} {'ibis.to_sql (ms)':>18}")
for d in (1, 10, 50, 200, 1000):
    tb = chain(d)
    tb_build = best(lambda: chain(d), 3 if d >= 200 else 20, 3) * 1e3
    sch = best(lambda: tb.schema(), 2000) * 1e6
    cst = best(lambda: W3.cast(tb), 500) * 1e6
    sql = best(lambda: ibis.to_sql(tb), 1 if d >= 200 else 5, 3) * 1e3
    print(f"{d:>6} {tb_build:>18.2f} {sch:>16.2f} {cst:>16.2f} {sql:>18.2f}")
print("\n### deep + wide: 50 chained mutates, 100 columns (each step mutates 1 col)")
class Wide(tacit.Schema): pass
Wide._fields = {f"c{i}": int for i in range(100)}; Wide._field_checks = {}; Wide._field_nullable = {}
for d in (1, 50):
    tb = chain(d, 100)
    print(f"depth {d:>3}: build {best(lambda: chain(d,100), 5, 3)*1e3:8.2f} ms   .schema() {best(lambda: tb.schema(), 2000)*1e6:7.2f} us   cast() {best(lambda: Wide.cast(tb), 500)*1e6:8.2f} us")
print("\n### per-step mutate that adds a NEW column each time (50 columns at the end)")
x = ibis.table({"c0": "int64"}, name="N")
import time
t0 = time.perf_counter()
for i in range(1, 51): x = x.mutate(**{f"c{i}": x.c0 + i})
print(f"build 50 add-column mutates: {(time.perf_counter()-t0)*1e3:.1f} ms; schema() {best(lambda: x.schema(), 2000)*1e6:.2f} us")
