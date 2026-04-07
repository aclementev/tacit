from __future__ import annotations

import re
from enum import Enum
from typing import TYPE_CHECKING, Any

import pandera.errors as pe

if TYPE_CHECKING:
    from .schema import Schema


class ValidationPhase(Enum):
    CAST = "cast"
    PARSE = "parse"
    CONTRACT_INPUT = "contract_input"
    CONTRACT_OUTPUT = "contract_output"


class ValidationError(Exception):
    """Base class for tacit validation failures."""

    _summary = "Validation"

    def __init__(
        self,
        *,
        schema: type[Schema],
        phase: ValidationPhase,
        detail: str | None = None,
        boundary_label: str | None = None,
        reason_code: str | None = None,
        check: object | None = None,
        failure_cases: object | None = None,
        column: str | None = None,
        original: BaseException | None = None,
    ) -> None:
        self.schema = schema
        self.phase = phase
        self.detail = detail
        self.boundary_label = boundary_label
        self.reason_code = reason_code
        self.check = check
        self.failure_cases = failure_cases
        self.column = column
        self.original = original
        super().__init__(self._build_message())

    def _build_message(self) -> str:
        message = f"{self._summary} failed for schema {self.schema.__name__} {self._phase_phrase()}."
        if self.detail:
            return f"{message[:-1]}: {self.detail}"
        return message

    def _phase_phrase(self) -> str:
        if self.phase is ValidationPhase.CAST:
            return "during cast"
        if self.phase is ValidationPhase.PARSE:
            return "during parse"
        if self.phase is ValidationPhase.CONTRACT_INPUT:
            return f"on {self.boundary_label or 'contract input'}"
        return f"on {self.boundary_label or 'return value'}"


class StructuralError(ValidationError):
    _summary = "Structural validation"


class CoercionError(ValidationError):
    _summary = "Coercion"


class ConstraintError(ValidationError):
    _summary = "Constraint validation"


class CheckExecutionError(ValidationError):
    _summary = "Check execution"


_STRUCTURAL_REASON_CODES = {
    pe.SchemaErrorReason.COLUMN_NOT_IN_DATAFRAME,
    pe.SchemaErrorReason.COLUMN_NOT_IN_SCHEMA,
    pe.SchemaErrorReason.WRONG_DATATYPE,
}
_CHECK_EXECUTION_REASON_CODES = {pe.SchemaErrorReason.CHECK_ERROR}


def structural_error_for_columns(
    *,
    schema: type[Schema],
    phase: ValidationPhase,
    missing: list[str],
    extra: list[str],
) -> StructuralError:
    parts = []
    if missing:
        parts.append(f"missing columns {missing}")
    if extra:
        parts.append(f"extra columns {extra}")
    detail = "; ".join(parts) + "."
    return StructuralError(schema=schema, phase=phase, detail=detail)


def structural_error_for_type_mismatches(
    *,
    schema: type[Schema],
    phase: ValidationPhase,
    mismatches: list[tuple[str, Any, Any]],
) -> StructuralError:
    if len(mismatches) == 1:
        column, expected, actual = mismatches[0]
        detail = f"column '{column}' expected {expected}, got {actual}."
        return StructuralError(
            schema=schema,
            phase=phase,
            detail=detail,
            column=column,
        )

    pieces = [
        f"{column} expected {expected}, got {actual}"
        for column, expected, actual in mismatches
    ]
    detail = "column type mismatches: " + "; ".join(pieces) + "."
    return StructuralError(schema=schema, phase=phase, detail=detail)


def coercion_error_for_cast_failure(
    *,
    schema: type[Schema],
    phase: ValidationPhase,
    cast_map: dict[str, Any],
    original: BaseException,
) -> CoercionError:
    columns = list(cast_map)
    if len(columns) == 1:
        column = columns[0]
        detail = (
            f"failed to cast column '{column}' to {cast_map[column]}. "
            f"{_summarize_original(original)}"
        )
        return CoercionError(
            schema=schema,
            phase=phase,
            detail=detail,
            column=column,
            original=original,
        )

    detail = (
        f"failed to cast columns {columns} to target schema types. "
        f"{_summarize_original(original)}"
    )
    return CoercionError(
        schema=schema,
        phase=phase,
        detail=detail,
        original=original,
    )


def validation_error_from_pandera(
    *,
    schema: type[Schema],
    phase: ValidationPhase,
    original: BaseException,
) -> ValidationError:
    if isinstance(original, pe.SchemaErrors):
        detail = f"multiple validation errors detected ({len(original.schema_errors)} errors)."
        return ConstraintError(
            schema=schema,
            phase=phase,
            detail=detail,
            failure_cases=original.failure_cases,
            original=original,
        )

    if not isinstance(original, pe.SchemaError):
        return ValidationError(
            schema=schema,
            phase=phase,
            detail=_summarize_original(original),
            original=original,
        )

    reason_code = original.reason_code
    reason_value = reason_code.value if reason_code is not None else None
    column = _extract_column(original)
    check = original.check
    failure_cases = original.failure_cases

    if reason_code in _CHECK_EXECUTION_REASON_CODES:
        detail = f"check {_format_check(check)} raised {_summarize_original(original)}"
        return CheckExecutionError(
            schema=schema,
            phase=phase,
            detail=detail,
            boundary_label=None,
            reason_code=reason_value,
            check=check,
            failure_cases=failure_cases,
            column=column,
            original=original,
        )

    if reason_code in _STRUCTURAL_REASON_CODES:
        detail = _structural_detail_from_pandera(original, column)
        return StructuralError(
            schema=schema,
            phase=phase,
            detail=detail,
            reason_code=reason_value,
            check=check,
            failure_cases=failure_cases,
            column=column,
            original=original,
        )

    detail = _constraint_detail_from_pandera(original, column)
    return ConstraintError(
        schema=schema,
        phase=phase,
        detail=detail,
        reason_code=reason_value,
        check=check,
        failure_cases=failure_cases,
        column=column,
        original=original,
    )


def validation_error_from_execution(
    *,
    schema: type[Schema],
    phase: ValidationPhase,
    original: BaseException,
) -> ValidationError:
    return ValidationError(
        schema=schema,
        phase=phase,
        detail=_ensure_period(_summarize_original(original)),
        original=original,
    )


def recontextualize_validation_error(
    exc: ValidationError,
    *,
    phase: ValidationPhase,
    boundary_label: str,
) -> ValidationError:
    return type(exc)(
        schema=exc.schema,
        phase=phase,
        detail=exc.detail,
        boundary_label=boundary_label,
        reason_code=exc.reason_code,
        check=exc.check,
        failure_cases=exc.failure_cases,
        column=exc.column,
        original=exc.original,
    )


def looks_like_coercion_failure(exc: BaseException) -> bool:
    name = type(exc).__name__
    text = str(exc)
    return (
        "Conversion" in name
        or "Conversion Error" in text
        or "Could not convert" in text
        or (
            "InvalidOperationError" in name
            and "conversion from `" in text
            and "failed in column" in text
        )
    )


def _extract_column(exc: pe.SchemaError) -> str | None:
    if exc.column_name:
        return str(exc.column_name)
    schema_name = getattr(exc.schema, "name", None)
    if schema_name:
        return str(schema_name)
    return None


def _format_check(check: object | None) -> str:
    if check is None:
        return "validation check"
    name = getattr(check, "error", None) or getattr(check, "name", None)
    if name:
        return str(name)
    return str(check)


def _constraint_detail_from_pandera(exc: pe.SchemaError, column: str | None) -> str:
    if exc.reason_code is pe.SchemaErrorReason.SERIES_CONTAINS_NULLS and column:
        return f"column '{column}' contains null values."
    if column and exc.check is not None:
        return f"column '{column}' failed check {_format_check(exc.check)}."
    return _ensure_period(_summarize_original(exc))


def _structural_detail_from_pandera(exc: pe.SchemaError, column: str | None) -> str:
    if exc.reason_code is pe.SchemaErrorReason.COLUMN_NOT_IN_DATAFRAME:
        missing = exc.failure_cases if isinstance(exc.failure_cases, str) else column
        if missing:
            return f"missing column '{missing}'."
    if exc.reason_code is pe.SchemaErrorReason.COLUMN_NOT_IN_SCHEMA:
        extra = exc.failure_cases if isinstance(exc.failure_cases, str) else column
        if extra:
            return f"unexpected column '{extra}'."
    if exc.reason_code is pe.SchemaErrorReason.WRONG_DATATYPE:
        actual = exc.failure_cases if isinstance(exc.failure_cases, str) else "unknown"
        expected = _extract_expected_dtype(exc.check)
        if column and expected:
            return f"column '{column}' expected {expected}, got {actual}."
    return _ensure_period(_summarize_original(exc))


def _extract_expected_dtype(check: object | None) -> str | None:
    if not isinstance(check, str):
        return None
    match = re.search(r"dtype\\('([^']+)'\\)", check)
    if match:
        return match.group(1)
    return None


def _summarize_original(exc: BaseException) -> str:
    text = str(exc).strip()
    if not text:
        return exc.__class__.__name__
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    return _ensure_period(first_line)


def _ensure_period(text: str) -> str:
    return text if text.endswith(".") else f"{text}."
