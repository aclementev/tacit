"""A3: static type is the ibis column type; runtime metadata is the dtype."""

from typing import Annotated

import ibis.expr.datatypes as dt
import ibis.expr.types as ir

Float64 = Annotated[ir.FloatingColumn, dt.float64]
Int64 = Annotated[ir.IntegerColumn, dt.int64]
String = Annotated[ir.StringColumn, dt.string]
Date = Annotated[ir.DateColumn, dt.date]
