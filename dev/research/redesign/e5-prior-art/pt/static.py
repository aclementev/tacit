import patito as pt
import polars as pl

class A(pt.Model):
    x: int

class B(pt.Model):
    x: int
    y: int

def f(df: pt.DataFrame[A]) -> pt.DataFrame[B]:
    return df

def g(df: pt.DataFrame[B]) -> None: ...

df = A.DataFrame({"x": [1]})
g(df)
g(pl.DataFrame({"x": [1]}))
v = A.validate(pl.DataFrame({"x": [1]}))
reveal_type(v)
