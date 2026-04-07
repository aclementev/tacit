"""Explore validation error shapes across tacit, pandera, and ibis.

Run with:

    UV_CACHE_DIR=/tmp/uv-cache uv run python dev/research/validation_error_scenarios.py
"""

from __future__ import annotations

from typing import Annotated, Any, Callable

import ibis
import pandera.ibis as pa

from tacit import Check, DataFrame, Schema, contract


class Order(Schema):
    amount: Annotated[float, Check.ge(0), Check.le(100)]
    status: str


def _print_exception(exc: BaseException) -> None:
    print(f"type: {type(exc).__module__}.{type(exc).__qualname__}")
    print(f"message: {exc}")

    for attr in [
        "reason_code",
        "column_name",
        "check",
        "failure_cases",
        "schema_errors",
    ]:
        if hasattr(exc, attr):
            value = getattr(exc, attr)
            print(f"{attr}: {type(value).__module__}.{type(value).__qualname__}")
            print(repr(value)[:1000])

    if exc.__cause__ is not None:
        print(
            "cause:",
            f"{type(exc.__cause__).__module__}.{type(exc.__cause__).__qualname__}",
        )
        print(repr(exc.__cause__)[:1000])


def _run(name: str, fn: Callable[[], Any]) -> None:
    print(f"=== {name} ===")
    try:
        result = fn()
        print("result:", type(result))
    except Exception as exc:  # noqa: BLE001 - research script
        _print_exception(exc)
    print()


schema = pa.DataFrameSchema(
    {
        "amount": pa.Column(
            float,
            checks=[pa.Check.ge(0), pa.Check.le(100)],
            nullable=False,
        ),
        "status": pa.Column(
            str,
            checks=[pa.Check.isin(["pending", "shipped"])],
            nullable=False,
        ),
    },
    strict=True,
)


@contract(validate=True)
def validated_identity(df: DataFrame[Order]) -> DataFrame[Order]:
    return df


def main() -> None:
    _run(
        "tacit.cast structural mismatch",
        lambda: Order.cast(ibis.memtable({"amount": ["bad"], "status": ["pending"]})),
    )

    _run(
        "tacit.parse coercion failure",
        lambda: Order.parse(
            ibis.memtable({"amount": ["bad"], "status": ["pending"]})
        ),
    )

    _run(
        "tacit.parse constraint failure",
        lambda: Order.parse(
            ibis.memtable({"amount": [-1.0], "status": ["pending"]})
        ),
    )

    _run(
        "pandera eager missing column",
        lambda: schema.validate(ibis.memtable({"amount": [1.0]})),
    )

    _run(
        "pandera eager extra column",
        lambda: schema.validate(
            ibis.memtable(
                {"amount": [1.0], "status": ["pending"], "extra": [1]}
            )
        ),
    )

    _run(
        "pandera eager wrong dtype",
        lambda: schema.validate(
            ibis.memtable({"amount": ["bad"], "status": ["pending"]})
        ),
    )

    _run(
        "pandera eager check failure",
        lambda: schema.validate(
            ibis.memtable({"amount": [-1.0], "status": ["pending"]})
        ),
    )

    _run(
        "pandera lazy aggregated errors",
        lambda: schema.validate(
            ibis.memtable({"amount": [-1.0, 101.0], "status": ["bad", None]}),
            lazy=True,
        ),
    )

    _run(
        "pandera custom check execution error",
        lambda: pa.DataFrameSchema(
            {
                "a": pa.Column(
                    int,
                    checks=[pa.Check(lambda _: 1 / 0, error="boom")],
                )
            }
        ).validate(ibis.memtable({"a": [1, 2, 3]})),
    )

    _run(
        "contract(validate=True) input coercion failure",
        lambda: validated_identity(
            ibis.memtable({"amount": ["bad"], "status": ["pending"]})
        ),
    )

    _run(
        "contract(validate=True) input check failure",
        lambda: validated_identity(
            ibis.memtable({"amount": [-1.0], "status": ["pending"]})
        ),
    )


if __name__ == "__main__":
    main()
