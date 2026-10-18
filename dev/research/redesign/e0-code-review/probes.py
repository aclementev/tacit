"""Probes for suspected edge cases in the current tacit implementation."""
from __future__ import annotations

import datetime as dt
import decimal
import traceback
from typing import Annotated, Optional

import ibis
import tacit


def probe(name, fn):
    try:
        out = fn()
        print(f"[ok]   {name}: {out}")
    except Exception as e:  # noqa: BLE001
        print(f"[fail] {name}: {type(e).__name__}: {str(e).splitlines()[0][:200]}")


con = ibis.duckdb.connect()


class A(tacit.Schema):
    x: float
    y: str


# 1. Non-nullable source column vs nullable schema dtype in cast()
t_nonnull = ibis.memtable({"x": [1.0], "y": ["a"]}).mutate(x=ibis.literal(1.0))
probe("cast: schema of literal-derived col", lambda: t_nonnull.schema())
probe("cast() with non-nullable literal column", lambda: A.cast(t_nonnull))
con.raw_sql("create table nn (x double not null, y varchar not null)")
con.raw_sql("insert into nn values (1.0, 'a')")
probe("cast() on NOT NULL db table", lambda: A.cast(con.table("nn")))
probe("parse() on NOT NULL db table", lambda: A.parse(con.table("nn")).execute().shape)


# 2. Optional / X | None as nullable
def opt():
    class B(tacit.Schema):
        x: float | None
    return B._ibis_schema(), B._pandera_schema().columns["x"].nullable
probe("x: float | None", opt)


def opt2():
    class B(tacit.Schema):
        x: Optional[float]
    return B._ibis_schema()
probe("x: Optional[float]", opt2)


# 3. date / datetime / Decimal / int32
def dates():
    class C(tacit.Schema):
        d: dt.date
        ts: dt.datetime
        amount: decimal.Decimal
    return C._ibis_schema()
probe("date/datetime/Decimal", dates)


def ibis_dtypes():
    import ibis.expr.datatypes as dtypes
    class C(tacit.Schema):
        a: dtypes.Int32  # type: ignore[valid-type]
    return C._ibis_schema()
probe("ibis dtype class annotation", ibis_dtypes)


# 4. Column name access on the schema class
probe("Iris.x (column ref)", lambda: A.x)  # type: ignore[attr-defined]

# 5. Nullable column parse with nulls, int CSV with nulls
t = ibis.memtable({"x": [1.0, None], "y": ["a", "b"]})
probe("parse() with null in non-nullable col", lambda: A.parse(t).execute())


# 6. contract with TYPE_CHECKING-only import / forward ref
src = '''
from __future__ import annotations
from typing import TYPE_CHECKING
import tacit
if TYPE_CHECKING:
    from probes_schemas import Late
@tacit.contract
def f(df: tacit.DataFrame[Late]) -> tacit.DataFrame[Late]:
    return df
'''
probe("contract w/ TYPE_CHECKING import", lambda: exec(compile(src, "m", "exec"), {}))


# 7. contract with Optional / tuple returns / generic TypeVar
def tuple_ret():
    @tacit.contract
    def f(df: tacit.DataFrame[A]) -> tuple[tacit.DataFrame[A], tacit.DataFrame[A]]:
        return df.mutate(z=1), df  # type: ignore[return-value]
    return [type(r).__name__ for r in f(A.cast(ibis.memtable({"x": [1.0], "y": ["a"]})))]
probe("contract tuple return (extra col not caught?)", tuple_ret)


def generic():
    @tacit.contract
    def f[S: tacit.Schema](df: tacit.DataFrame[S]) -> tacit.DataFrame[S]:
        return df.mutate(z=1)  # type: ignore[return-value]
    return f(A.cast(ibis.memtable({"x": [1.0], "y": ["a"]})))
probe("contract generic TypeVar", generic)


def optional_param():
    @tacit.contract
    def f(df: tacit.DataFrame[A] | None = None) -> tacit.DataFrame[A]:
        return ibis.memtable({"x": [1.0], "y": ["a"]})  # type: ignore[return-value]
    return f(ibis.memtable({"q": [1]}))  # type: ignore[arg-type]
probe("contract Optional[DataFrame] param (wrong table passes?)", optional_param)

# 8. Schema subclass invariance at runtime: passing IrisFeatures frame to Iris contract
class A2(A):
    z: int


def child_to_parent():
    @tacit.contract
    def f(df: tacit.DataFrame[A]) -> tacit.DataFrame[A]:
        return df
    return f(A2.cast(ibis.memtable({"x": [1.0], "y": ["a"], "z": [1]})))  # type: ignore[arg-type]
probe("child frame into parent contract (strict)", child_to_parent)

# 9. Error message quality for a constraint violation
class Pos(tacit.Schema):
    x: Annotated[float, tacit.Check.ge(0)]
    y: Annotated[str, tacit.Check.isin(["a"])]


def bad():
    Pos.parse(ibis.memtable({"x": [-1.0, 2.0, -3.0], "y": ["a", "b", "a"]}))
try:
    bad()
except Exception as e:
    print("--- constraint error message ---")
    print(type(e).__name__, str(e)[:1500])
