from __future__ import annotations

from typing import ClassVar, Generic, Self, TypeVar, get_origin, get_type_hints

import ibis
import ibis.expr.types as ir

S = TypeVar("S", bound="Schema")


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
        df = cls(table.op())
        object.__setattr__(df, "_tacit_schema", schema_type)
        return df


class Schema:
    """Base class for tacit schema definitions.

    Subclass and declare columns as annotated class attributes:

        class Iris(Schema):
            sepal_length: float
            species: str
    """

    _fields: ClassVar[dict[str, type]]

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        cls._fields = {
            name: typ
            for name, typ in get_type_hints(cls).items()
            if get_origin(typ) is not ClassVar
        }

    @classmethod
    def _get_fields(cls) -> dict[str, type]:
        return cls._fields

    @classmethod
    def _ibis_schema(cls) -> ibis.Schema:
        return ibis.schema(cls._get_fields())

    @classmethod
    def cast(cls, table: ir.Table) -> DataFrame[Self]:
        """Structural check: verify column names and types match, wrap as DataFrame.

        Metadata-only — does not execute queries. Use at internal pipeline
        boundaries where you trust the data but want type safety.

        Raises:
            ValueError: Missing or extra columns (strict mode).
            TypeError: Column type mismatch.
        """
        target = cls._ibis_schema()
        actual = table.schema()

        missing = sorted(set(target.names) - set(actual.names))
        if missing:
            raise ValueError(f"Missing columns: {missing}")

        extra = sorted(set(actual.names) - set(target.names))
        if extra:
            raise ValueError(f"Extra columns: {extra}")

        type_errors = []
        for col_name, expected_type in target.items():
            actual_type = actual[col_name]
            if actual_type != expected_type:
                type_errors.append(
                    f"  {col_name}: expected {expected_type}, got {actual_type}"
                )
        if type_errors:
            detail = "\n".join(type_errors)
            raise TypeError(f"Column type mismatches:\n{detail}")

        return DataFrame._from_table(table, cls)
