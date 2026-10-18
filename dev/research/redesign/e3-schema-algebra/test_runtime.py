"""Runtime behaviour of the prototypes (uv run pytest test_runtime.py)."""

import subprocess
import sys
from pathlib import Path

import ibis
import pytest

import codegen
from derive import VerifiedSchema, pick
from t1_structural import HasIdP, Orders, Products, bump_ids_retag, dedupe, dedupe_p, drop_negative
from t2_additive import ScoredCustomers, ScoredOrders, add_score_b2
from t2_additive import Orders as O2
from t4_joins import Customers as C4
from t4_joins import Orders as O4
from t4_joins import OrdersOnly, OrdersWithCustomer
from tx import DataFrame, conforms

HERE = Path(__file__).parent


@pytest.fixture
def orders() -> DataFrame[Orders]:
    t = ibis.memtable(
        {"id": [1, 1, 2], "event_ts": ["2026-01-01"] * 3, "amount": [1.0, 1.0, 3.0]}
    ).cast({"event_ts": "timestamp"})
    return Orders.cast(t)


def test_schema_preserving_ops_keep_schema(orders: DataFrame[Orders]) -> None:
    out = dedupe(orders)
    assert isinstance(out, DataFrame) and out.tacit_schema is Orders
    assert out.count().execute() == 2
    assert dedupe_p(orders).tacit_schema is Orders
    assert drop_negative(orders).tacit_schema is Orders
    assert bump_ids_retag(orders).tacit_schema is Orders


def test_retag_rejects_schema_change(orders: DataFrame[Orders]) -> None:
    with pytest.raises(TypeError, match="extra"):
        orders.retag(orders.mutate(x=ibis.literal(1)))


def test_conforms_protocol(orders: DataFrame[Orders]) -> None:
    assert conforms(orders, HasIdP).tacit_schema is HasIdP
    with pytest.raises(TypeError, match="missing"):
        conforms(Products.cast(ibis.memtable({"sku": ["a"]})), HasIdP)


def test_additive_out_schema() -> None:
    o = O2.cast(ibis.memtable({"id": [1], "amount": [2.0]}))
    assert add_score_b2(o, ScoredOrders).columns == ("id", "amount", "score")
    assert ScoredOrders.from_mutate(o, score=ibis.literal(1.0)).tacit_schema is ScoredOrders
    with pytest.raises(TypeError, match="subclass"):
        ScoredCustomers.from_mutate(o, score=ibis.literal(1.0))  # type: ignore[arg-type]


def test_join_out_schema() -> None:
    o = O4.cast(ibis.memtable({"id": [1], "customer_id": [7], "amount": [2.0]}))
    c = C4.cast(ibis.memtable({"customer_id": [7], "name": ["ann"]}))
    r = OrdersWithCustomer.from_join(o, c, "customer_id")
    assert r.execute().to_dict("records") == [{"id": 1, "customer_id": 7, "amount": 2.0, "name": "ann"}]
    with pytest.raises(TypeError, match="subclass"):
        OrdersOnly.from_join(o, c, "customer_id")  # type: ignore[arg-type]


def test_verified_schema_detects_drift() -> None:
    from t3_derived import Iris

    class Ok(VerifiedSchema, derive=pick(Iris, "species")):
        species: str

    with pytest.raises(TypeError, match="does not match"):

        class Drifted(VerifiedSchema, derive=pick(Iris, "species", "sepal_length")):
            species: str


def test_runtime_derived_class() -> None:
    from t3_derived import Iris

    Sepal = Iris.pick("sepal_length", "sepal_width")
    t = ibis.memtable({"sepal_length": [1.0], "sepal_width": [2.0]})
    assert Sepal.cast(t).tacit_schema is Sepal


def test_codegen_up_to_date_and_detects_stale(tmp_path: Path) -> None:
    assert codegen.generate("cg_spec") == (HERE / "cg_generated.py").read_text()
    stale = tmp_path / "gen.py"
    stale.write_text((HERE / "cg_generated.py").read_text().replace("    score: float\n", ""))
    proc = subprocess.run(
        [sys.executable, "codegen.py", "cg_spec", "--out", str(stale), "--check"],
        cwd=HERE, capture_output=True, text=True,
    )
    assert proc.returncode == 1 and "stale" in proc.stderr
