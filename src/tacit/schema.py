from __future__ import annotations

from typing import Annotated, ClassVar, Self, get_args, get_origin, get_type_hints

import ibis
import ibis.expr.types as ir
import pandera.errors as pe
import pandera.ibis as pa

from .constraints import Nullable
from .errors import (
    ValidationPhase,
    coercion_error_for_cast_failure,
    looks_like_coercion_failure,
    structural_error_for_columns,
    structural_error_for_type_mismatches,
    validation_error_from_execution,
    validation_error_from_pandera,
)


class DataFrame[S: "Schema"](ir.Table):
    """Schema-aware DataFrame. Wraps an ibis Table with a schema type parameter.

    DataFrame[S] IS an ibis Table (subclass), so the full ibis API works
    transparently. ibis operations (.mutate(), .filter(), etc.) return plain
    ir.Table — the schema type drops off, which is correct by design.
    """

    __slots__ = ("_tacit_schema",)

    # S is phantom (not stored in instance attrs). Without this stub, pyright
    # infers S as covariant, making DataFrame[Child] assignable to
    # DataFrame[Parent]. Both positions force invariance inference.
    def __tacit_type_is_invariant__(self, x: S) -> S: ...

    @classmethod
    def _from_table(cls, table: ir.Table, schema_type: type[Schema]) -> DataFrame[S]:
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
    _field_checks: ClassVar[dict[str, list[pa.Check]]]
    _field_nullable: ClassVar[dict[str, bool]]

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        fields: dict[str, type] = {}
        field_checks: dict[str, list[pa.Check]] = {}
        field_nullable: dict[str, bool] = {}

        for name, hint in get_type_hints(cls, include_extras=True).items():
            if get_origin(hint) is ClassVar:
                continue

            if get_origin(hint) is Annotated:
                args = get_args(hint)
                fields[name] = args[0]
                checks = [a for a in args[1:] if isinstance(a, pa.Check)]
                if checks:
                    field_checks[name] = checks
                for a in args[1:]:
                    if isinstance(a, Nullable):
                        field_nullable[name] = a.allow
                        break
            else:
                fields[name] = hint

        cls._fields = fields
        cls._field_checks = field_checks
        cls._field_nullable = field_nullable

    @classmethod
    def _get_fields(cls) -> dict[str, type]:
        return cls._fields

    @classmethod
    def _ibis_schema(cls) -> ibis.Schema:
        return ibis.schema(cls._get_fields())

    @classmethod
    def _pandera_schema(cls) -> pa.DataFrameSchema:
        columns = {}
        for name, dtype in cls._ibis_schema().items():
            checks = cls._field_checks.get(name, [])
            nullable = cls._field_nullable.get(name, False)
            columns[name] = pa.Column(dtype, checks=checks, nullable=nullable)
        return pa.DataFrameSchema(columns, strict=True)

    @classmethod
    def _check_columns(
        cls,
        target: ibis.Schema,
        actual: ibis.Schema,
        *,
        phase: ValidationPhase,
    ) -> None:
        target_names = set(target.names)  # type: ignore[reportArgumentType]  # ibis has no py.typed
        actual_names = set(actual.names)  # type: ignore[reportArgumentType]  # ibis has no py.typed

        missing = sorted(target_names - actual_names)
        extra = sorted(actual_names - target_names)
        if missing or extra:
            raise structural_error_for_columns(
                schema=cls,
                phase=phase,
                missing=missing,
                extra=extra,
            )

    @classmethod
    def parse(cls, table: ir.Table) -> DataFrame[Self]:
        """Full parsing: coerce types + validate with pandera + wrap as DataFrame.

        Executes queries against the engine. Use at pipeline boundaries where
        you're ingesting untrusted data.

        Raises:
            tacit.errors.ValidationError: Data fails structural, coercion, or
                validation checks.
        """
        target = cls._ibis_schema()
        actual = table.schema()
        cls._check_columns(target, actual, phase=ValidationPhase.PARSE)

        # Pandera's ibis backend doesn't support coercion — handle it ourselves
        cast_map = {
            col: target_type
            for col, target_type in target.items()
            if actual[col] != target_type
        }
        if cast_map:
            try:
                table = table.cast(cast_map)
            except Exception as exc:
                coercion_error = coercion_error_for_cast_failure(
                    schema=cls,
                    phase=ValidationPhase.PARSE,
                    cast_map=cast_map,
                    original=exc,
                )
                raise coercion_error from exc

        try:
            validated = cls._pandera_schema().validate(table)
        except (pe.SchemaError, pe.SchemaErrors) as exc:
            validation_error = validation_error_from_pandera(
                schema=cls,
                phase=ValidationPhase.PARSE,
                original=exc,
            )
            raise validation_error from exc
        except Exception as exc:
            if cast_map and looks_like_coercion_failure(exc):
                coercion_error = coercion_error_for_cast_failure(
                    schema=cls,
                    phase=ValidationPhase.PARSE,
                    cast_map=cast_map,
                    original=exc,
                )
                raise coercion_error from exc
            validation_error = validation_error_from_execution(
                schema=cls,
                phase=ValidationPhase.PARSE,
                original=exc,
            )
            raise validation_error from exc
        return DataFrame._from_table(validated, cls)

    @classmethod
    def cast(cls, table: ir.Table) -> DataFrame[Self]:
        """Structural check: verify column names and types match, wrap as DataFrame.

        Metadata-only — does not execute queries. Use at internal pipeline
        boundaries where you trust the data but want type safety.

        Raises:
            tacit.errors.StructuralError: Missing, extra, or wrong-type columns.
        """
        target = cls._ibis_schema()
        actual = table.schema()
        target_names = set(target.names)  # type: ignore[reportArgumentType]
        actual_names = set(actual.names)  # type: ignore[reportArgumentType]
        missing = sorted(target_names - actual_names)
        extra = sorted(actual_names - target_names)
        if missing or extra:
            raise structural_error_for_columns(
                schema=cls,
                phase=ValidationPhase.CAST,
                missing=missing,
                extra=extra,
            )

        type_errors: list[tuple[str, object, object]] = []
        for col_name, expected_type in target.items():
            actual_type = actual[col_name]
            if actual_type != expected_type:
                type_errors.append((col_name, expected_type, actual_type))
        if type_errors:
            raise structural_error_for_type_mismatches(
                schema=cls,
                phase=ValidationPhase.CAST,
                mismatches=type_errors,
            )

        return DataFrame._from_table(table, cls)
