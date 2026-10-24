"""Runtime tests for the tacit_nw prototype across narwhals backends.  uv run pytest tests/test_runtime.py
(E16_SPARK=1 adds pyspark.)"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

import narwhals.stable.v2 as nw
import polars as pl
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

import tacit_nw as tc  # noqa: E402
from common import to_native  # noqa: E402
from tacit_nw import Column, DataFrame, PolarsFrame  # noqa: E402

BACKENDS = ["polars-eager", "polars-lazy", "duckdb", "duckdb-conn", "sqlframe-duckdb", "ibis-duckdb"] + (["pyspark"] if os.environ.get("E16_SPARK") else [])


class Orders(tc.Schema):
    order_id: Column[int] = tc.field(unique=True)
    status: Column[str] = tc.field(isin=["pending", "shipped"])
    amount: Column[float] = tc.field(ge=0)
    discount: Column[float | None]
    ts: Column[datetime]


class Net(tc.Schema):
    net: Column[float]


class NetOrders(Orders, Net):
    pass


class Stats(tc.Schema):
    status: Column[str]
    n: Column[int]
    total: Column[float]


GOOD = pl.DataFrame({"order_id": [1, 2, 3], "status": ["shipped", "pending", "shipped"], "amount": [1.0, 2.0, 3.0],
                     "discount": [None, 0.5, 1.0], "ts": [datetime(2024, 1, d) for d in (1, 2, 3)], "extra": [1, 1, 1]})
BAD = GOOD.with_columns(amount=pl.Series([1.0, -2.0, 3.0]), status=pl.Series(["shipped", "x", "shipped"]), order_id=pl.Series([1, 1, 3]))


@pytest.fixture(params=BACKENDS)
def backend(request: pytest.FixtureRequest) -> str:
    return request.param


def test_parse_ok_projects_and_types(backend: str) -> None:
    o = Orders.parse(to_native(backend, "good", GOOD))
    assert isinstance(o, DataFrame) and isinstance(o, nw.LazyFrame)
    assert o.columns == ["order_id", "status", "amount", "discount", "ts"]
    assert type(o.filter(o.c.amount > 1)) is DataFrame  # schema-preserving keeps the tag
    assert type(o.with_columns(x=o.c.amount)) is nw.LazyFrame  # schema-changing drops it
    assert nw.to_native(o) is not None


def test_parse_reports_all_issues_in_one_query(backend: str) -> None:
    from tacit_nw._validate import STATS

    STATS["queries"] = 0
    with pytest.raises(tc.ValidationError) as ei:
        Orders.parse(to_native(backend, "bad", BAD))
    codes = sorted(i.code for i in ei.value.issues)
    assert codes == ["ge(0)", "isin(['pending', 'shipped'])", "unique"]
    assert STATS["queries"] == 1 + 2  # 1 fused query + 1 sample query per failing check


def test_structural_errors(backend: str) -> None:
    with pytest.raises(tc.ValidationError, match="missing_column"):
        Orders.conform(to_native(backend, "g2", GOOD.drop("amount")))
    with pytest.raises(tc.ValidationError, match="dtype"):
        Orders.conform(to_native(backend, "g3", GOOD.with_columns(amount=pl.col("amount").cast(pl.String))))
    o = Orders.parse(to_native(backend, "g4", GOOD.with_columns(amount=pl.col("amount").cast(pl.String))), coerce=True)
    assert o.collect_schema()["amount"] == nw.Float64


def test_build_extend_aggregate(backend: str) -> None:
    o = Orders.parse(to_native(backend, "g5", GOOD))
    n = NetOrders.extend(o, Net.build(o, net=o.c.amount - o.c.discount.fill_null(0)))
    assert sorted(n.collect()["net"].to_list()) == [1.0, 1.5, 2.0]
    s = Stats.build(o.group_by("status"), status=o.c.status, n=o.c.order_id.count(), total=o.c.amount.sum())
    assert dict(zip(*[s.sort("status").collect()[k].to_list() for k in ("status", "total")])) == {"pending": 2.0, "shipped": 4.0}
    with pytest.raises(tc.ValidationError, match="missing_column"):
        Net.build(o)  # type: ignore[call-arg]


def test_native_tag_and_step() -> None:
    @tc.step
    def net(o: PolarsFrame[Orders]) -> PolarsFrame[NetOrders]:
        return tc.tag(NetOrders, o.with_columns(net=pl.col(Orders.amount) * 1.0))

    out = net(tc.tag(Orders, GOOD))
    assert isinstance(out, pl.DataFrame) and out.columns[-1] == "net"

    @tc.step
    def broken(o: PolarsFrame[Orders]) -> PolarsFrame[NetOrders]:
        return o.with_columns(net=pl.lit("x"))  # type: ignore[return-value]

    with pytest.raises(tc.ValidationError, match="step broken: return value"):
        broken(tc.tag(Orders, GOOD))
    with pytest.raises(tc.ValidationError, match="step net: argument 'o'"):
        net(GOOD.drop("amount"))  # type: ignore[arg-type]
