"""Ad hoc comparison of tacit validation errors across ibis backends.

Examples:

    UV_CACHE_DIR=/tmp/uv-cache uv run python dev/research/validation_error_backend_matrix.py duckdb
    UV_CACHE_DIR=/tmp/uv-cache uv run --with 'ibis-framework[polars]>=12.0.0' --with 'polars>=1.0.0' python dev/research/validation_error_backend_matrix.py polars
"""

from __future__ import annotations

import sys
from typing import Annotated

import ibis

from tacit import Check, Schema
from tacit.errors import ValidationError


class Order(Schema):
    amount: Annotated[float, Check.ge(0)]
    status: str


def _connect(name: str):
    if name == "duckdb":
        return ibis.duckdb.connect()
    if name == "polars":
        return ibis.polars.connect()
    raise ValueError(f"unsupported backend: {name}")


def _table(con):
    data = {
        "amount": ["bad", "-1", "10"],
        "status": ["pending", None, "pending"],
    }
    if con.name == "polars":
        import polars as pl

        data = pl.DataFrame(data)
    return con.create_table(
        "orders_tmp",
        data,
        overwrite=True,
    )


def _print_exception(exc: BaseException) -> None:
    print("type:", type(exc).__name__)
    print("message:", str(exc))
    if isinstance(exc, ValidationError):
        print("phase:", exc.phase)
        print("schema:", exc.schema.__name__)
        print("column:", exc.column)
        print("reason_code:", exc.reason_code)
        print("boundary_label:", exc.boundary_label)
        print(
            "original:",
            type(exc.original).__name__ if exc.original is not None else None,
        )
        print(
            "cause:",
            type(exc.__cause__).__name__ if exc.__cause__ is not None else None,
        )


def main() -> int:
    backend = sys.argv[1] if len(sys.argv) > 1 else "duckdb"
    print("backend:", backend)
    con = _connect(backend)
    table = _table(con)
    print("input schema:", table.schema())

    try:
        Order.parse(table)
    except Exception as exc:  # noqa: BLE001 - ad hoc research script
        _print_exception(exc)
        return 0

    print("parse unexpectedly succeeded")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
