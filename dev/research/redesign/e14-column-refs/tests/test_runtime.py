"""E14 runtime (duckdb): refs, string keys, and the join pitfalls."""

import ibis
import pytest
from ibis import Deferred

import tacit_r as tr
from gen_schemas import Customers, Net, NetOrders, Orders


@pytest.fixture
def frames():
    con = ibis.duckdb.connect()
    o = con.create_table(
        "o",
        ibis.memtable(
            {
                "order_id": [1, 2, 3, 4],
                "customer_id": [10, 10, 20, 30],
                "order_ts": ["2024-01-01", "2024-01-03", "2024-01-02", "2024-01-05"],
                "status": ["a", "b", "a", "c"],
                "amount": [1.0, -2.0, 3.0, 4.0],
                "discount": [0.5, None, None, 1.0],
            }
        ).cast({"order_ts": "timestamp"}),
    )
    c = con.create_table("c", ibis.memtable({"customer_id": [10, 20], "country": ["DE", "US"]}))
    return Orders.parse(o), Customers.parse(c)


def test_ref_is_deferred(frames):
    assert isinstance(Orders.amount, Deferred)
    assert isinstance(Orders.amount, tr.Ref)
    assert repr(NetOrders.amount) == "_['amount']"


def test_frame_methods(frames):
    o, _ = frames
    f = o.filter(Orders.amount > 0).order_by(Orders.order_ts.desc())
    assert isinstance(f, tr.DataFrame) and f._schema is Orders
    assert f.order_id.execute().tolist() == [4, 3, 1]
    assert o.distinct(on=Orders.customer_id).count().execute() == 3
    g = o.group_by(Orders.status).agg(total=Orders.amount.sum(), n=Orders.order_id.count()).order_by("status")
    assert g.total.execute().tolist() == [4.0, -2.0, 4.0]
    m = o.mutate(x=Orders.amount * 2, y=Orders.amount / Orders.amount.sum())
    assert m.x.execute().tolist() == [2.0, -4.0, 6.0, 8.0]
    assert o.select(Orders.order_id, Orders.amount).columns == ("order_id", "amount")


def test_window_with_refs(frames):
    o, _ = frames
    latest = o.filter(tr.row_number().over(group_by=Orders.customer_id, order_by=Orders.order_ts.desc()) == 0)
    assert sorted(latest.order_id.execute().tolist()) == [2, 3, 4]


def test_build_and_extend(frames):
    o, _ = frames
    d = Net.build(o, net_amount=Orders.amount - Orders.discount.fill_null(0))
    n = NetOrders.extend(o, d)
    assert n._schema is NetOrders
    assert n.net_amount.execute().tolist() == [0.5, -2.0, 3.0, 3.0]
    assert n.filter(Orders.amount > 0).filter(NetOrders.net_amount > 1).count().execute() == 2


def test_join_key_pairs(frames):
    o, c = frames
    j = o.join(c, [(Orders.customer_id, Customers.customer_id)])
    assert j.count().execute() == 3
    # self-join: the pair is positional, so the same schema on both sides is unambiguous
    o2 = o.view()
    sj = o.join(o2, [(Orders.customer_id, Orders.customer_id)])
    assert sj.count().execute() == 6  # 2x2 for customer 10, 1 for 20, 1 for 30


def test_join_mixed_owner_predicate_is_silently_wrong(frames):
    """Why the checker MUST reject `Orders.x == Customers.x`: ibis resolves a Deferred predicate on the
    LEFT table, so both sides become o.customer_id -> a tautology -> a cross join, no error."""
    o, c = frames
    bad = o.join(c, Orders.customer_id == Customers.customer_id)  # statically rejected (two owners)
    assert bad.count().execute() == 8  # 4 x 2: cross join


def test_string_keys(frames):
    o, _ = frames
    assert o.c["amount"].execute().tolist() == [1.0, -2.0, 3.0, 4.0]
    assert o["amount"].execute().tolist() == [1.0, -2.0, 3.0, 4.0]
    assert o.filter(Orders.col("amount") > 0).count().execute() == 3
    with pytest.raises(KeyError, match="did you mean 'amount'"):
        o.c["amout"]
    with pytest.raises(KeyError, match="did you mean 'amount'"):
        Orders.col("amout")


def test_runtime_typo_on_ref_class_access():
    with pytest.raises(AttributeError):
        Orders.amout  # noqa: B018


def test_examples_agree():
    import s_attr
    import s_ibis
    import s_ref
    import s_str

    outs = [m.main() for m in (s_attr, s_ref, s_str, s_ibis)]
    assert all(x == outs[0] for x in outs)
