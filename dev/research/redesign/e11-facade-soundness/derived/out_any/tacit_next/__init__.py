"""tacit-next: typed frames, columns and contracts for ibis pipelines (E8 prototype).

    import tacit_next as tc
    from tacit_next import Column

    class Orders(tc.Frame):
        order_id: Column[int]
        amount: Column[float] = tc.field(ge=0)
        discount: Column[float | None]
"""

from ._column import Column, Scalar, as_column, as_ibis, cases, lit, row_number
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
from ._frame import Frame, Into, fields, schema
from ._join import Join, join
from ._step import step

__all__ = [
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
