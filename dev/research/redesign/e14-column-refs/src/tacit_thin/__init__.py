"""tacit-thin (E13): typed frames that ARE ibis tables, columns and contracts for ibis pipelines (E8 prototype).

    import tacit_thin as tc
    from tacit_thin import Column

    class Orders(tc.Frame):
        order_id: Column[int]
        amount: Column[float] = tc.field(ge=0)
        discount: Column[float | None]
"""

from ._column import Column, Ref, RefScalar, Scalar, SchemaBase, as_column, as_ibis, cases, lit, row_number
from ._errors import Issue, ValidationError
from ._fields import (
    Constraint,
    FieldSpec,
    between,
    check,
    dtype,
    field,
    ge,
    gt,
    isin,
    le,
    length,
    lt,
    notin,
    pattern,
    str_matches,
    unique,
)
from ._frame import IBIS_TABLE_MEMBERS, Frame, Into, as_table, fields, schema
from ._ibis_api import GroupedTable, Table, TableAPI
from ._join import Join, join
from ._step import step

__all__ = [
    "IBIS_TABLE_MEMBERS",
    "GroupedTable",
    "Table",
    "TableAPI",
    "as_table",
    "Column",
    "Constraint",
    "FieldSpec",
    "Frame",
    "Into",
    "Issue",
    "Join",
    "Scalar",
    "ValidationError",
    "as_column",
    "as_ibis",
    "between",
    "cases",
    "check",
    "dtype",
    "field",
    "fields",
    "ge",
    "gt",
    "isin",
    "join",
    "le",
    "length",
    "lit",
    "lt",
    "notin",
    "pattern",
    "row_number",
    "schema",
    "step",
    "str_matches",
    "unique",
]
