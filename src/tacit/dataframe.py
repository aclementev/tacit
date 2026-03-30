from __future__ import annotations

from typing import Generic, TypeVar

import ibis.expr.types as ir

from .schema import Schema

S = TypeVar("S", bound=Schema)


class DataFrame(ir.Table, Generic[S]):
    """Schema-aware DataFrame. Wraps an ibis Table with a schema type parameter.

    DataFrame[S] IS an ibis Table (subclass), so the full ibis API works
    transparently. ibis operations (.mutate(), .filter(), etc.) return plain
    ir.Table — the schema type drops off, which is correct by design.
    """

    __slots__ = ("_tacit_schema",)

    @classmethod
    def _from_table(
        cls, table: ir.Table, schema_type: type[Schema]
    ) -> DataFrame[S]:
        """Wrap an existing ibis Table as a typed DataFrame."""
        df = cls(table.op())
        object.__setattr__(df, "_tacit_schema", schema_type)
        return df
