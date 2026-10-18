"""A1: static type is a typed descriptor Col[Get, Set]; runtime metadata is the dtype.

Get = what `frame.col` returns; Set = what the synthesized constructor accepts
(ibis arithmetic returns NumericValue, not FloatingColumn, so Set is wider).
"""

from typing import Annotated

import ibis.expr.datatypes as dt
import ibis.expr.types as ir

from .frame import Col

Float64 = Annotated[Col[ir.FloatingColumn, ir.NumericValue], dt.float64]
Int64 = Annotated[Col[ir.IntegerColumn, ir.IntegerValue], dt.int64]
String = Annotated[Col[ir.StringColumn, ir.StringValue], dt.string]
Date = Annotated[Col[ir.DateColumn, ir.DateValue], dt.date]
