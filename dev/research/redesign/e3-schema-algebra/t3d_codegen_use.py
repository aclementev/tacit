"""3c. Using codegen output: every checker sees real classes."""

from typing import Protocol, Unpack, reveal_type

import ibis
import ibis.expr.types as ir

from cg_generated import IrisLabelled, IrisSepal, IrisSepalCols, IrisScored
from cg_models import Iris
from tx import DataFrame, Into, SchemaLike


class HasPetalP(SchemaLike, Protocol):
    petal_length: float


class HasLabelP(SchemaLike, Protocol):
    label: str


def needs_petal[S: HasPetalP](df: DataFrame[S]) -> None: ...
def needs_label[S: HasLabelP](df: DataFrame[S]) -> None: ...
def to_scored[O: Iris](df: Into[O], out: type[O]) -> DataFrame[O]: ...


def build_sepal(t: ibis.Table, **cols: Unpack[IrisSepalCols]) -> DataFrame[IrisSepal]:
    return IrisSepal.cast(t.select(**cols))


def use(s: DataFrame[IrisSepal], l: DataFrame[IrisLabelled], i: DataFrame[Iris], t: ibis.Table, f: ir.FloatingValue) -> None:
    needs_petal(s)  # case: c pick() result has no petal expect: err
    needs_petal(l)  # case: c rename() result keeps petal expect: ok
    needs_label(l)  # case: c rename() result has label expect: ok
    needs_label(i)  # case: c source has no label expect: err
    reveal_type(to_scored(i, IrisScored))  # case: c extend() result is a subtype (B2 works) expect: ok
    build_sepal(t, sepal_length=f, sepal_width=f)  # case: c generated Cols TypedDict expect: ok
    build_sepal(t, sepal_length=f)  # case: c generated Cols TypedDict missing col expect: err
