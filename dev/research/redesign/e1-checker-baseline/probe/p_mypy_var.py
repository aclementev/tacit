from typing import Any, reveal_type
import ibis.expr.types as ir
from tacit import DataFrame, Schema

class Parent(Schema):
    a: int

class Child(Parent):
    b: int

def c2p(df: DataFrame[Child]) -> DataFrame[Parent]:
    return df  # should error if invariant

def p2c(df: DataFrame[Parent]) -> DataFrame[Child]:
    return df  # should error

def t2df(t: ir.Table) -> DataFrame[Parent]:
    return t  # should error

def any2df(t: Any) -> DataFrame[Parent]:
    return t

# control: same shape without ibis base
class Plain[S: Schema]:
    def __tacit_type_is_invariant__(self, x: S) -> S: ...

class Plain2[S: Schema]:
    pass

def pc2p(df: Plain[Child]) -> Plain[Parent]:
    return df  # should error

def p2c2(df: Plain[Parent]) -> Plain[Child]:
    return df  # should error

def pc2p2(df: Plain2[Child]) -> Plain2[Parent]:
    return df  # no hack, phantom => covariant: no error expected in pyright/mypy
