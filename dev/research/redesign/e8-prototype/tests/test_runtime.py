"""Runtime behaviour of tacit_next on duckdb (run: uv run --frozen pytest e8-prototype/tests)."""

from __future__ import annotations

import math
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Any

import ibis
import ibis.expr.types as ir
import pandas as pd
import pytest

import tacit_next as tc
from tacit_next import Column

E6 = Path(__file__).resolve().parents[2] / "e6-agent-trial"


class Orders(tc.Frame):
    order_id: Column[int] = tc.field(unique=True)
    customer_id: Column[int]
    order_ts: Column[datetime]
    status: Column[str] = tc.field(isin=["pending", "shipped", "cancelled"])
    amount: Column[float] = tc.field(ge=0)
    discount: Column[float | None]


class Customers(tc.Frame):
    customer_id: Column[int]
    name: Column[str]
    country: Annotated[Column[str], tc.length(2)]


class NetAmount(tc.Frame):
    net_amount: Column[float]


class NetOrders(Orders, NetAmount):
    pass


class Stats(tc.Frame):
    status: Column[str]
    n: Column[int]
    total: Column[float]


class OrderWithCountry(tc.Frame):
    order_id: Column[int]
    customer_id: Column[int]
    country: Column[str]


class HasTs(tc.Frame):
    order_ts: Column[datetime]


class Scored(tc.Frame):
    score: Column[float]


class ScoredOrders(Orders, Scored):
    pass


@pytest.fixture
def con() -> Any:
    return ibis.duckdb.connect()


def orders_table(**over: list[Any]) -> ir.Table:
    data: dict[str, list[Any]] = {
        "order_id": [1, 2, 3, 4],
        "customer_id": [10, 10, 20, 30],
        "order_ts": ["2024-01-01 10:00:00", "2024-01-03 10:00:00", "2024-01-02 09:00:00", "2024-02-01 00:00:00"],
        "status": ["shipped", "pending", "cancelled", "shipped"],
        "amount": ["10.5", "20", "5", "7.25"],
        "discount": ["1", None, "0.5", None],
    }
    data.update(over)
    return ibis.memtable(pd.DataFrame(data).astype(object).where(pd.DataFrame(data).notna(), None))


def customers_table() -> ir.Table:
    return ibis.memtable({"customer_id": [10, 20, 30], "name": ["a", "b", "c"], "country": ["DE", "US", "GB"]})


@pytest.fixture
def orders() -> Orders:
    return Orders.parse(orders_table())


@pytest.fixture
def customers() -> Customers:
    return Customers.parse(customers_table())


# -- columns are plain ibis expressions --------------------------------------------


def test_columns_are_plain_ibis(orders: Orders) -> None:
    assert type(orders.amount) is ir.FloatingColumn
    assert isinstance(orders.amount, tc.Column)
    assert isinstance(orders.amount.sum(), tc.Scalar)
    assert not isinstance(orders.amount.sum(), tc.Column)
    assert repr(Orders.amount) == repr(ibis._["amount"])  # class access is a deferred reference


# -- parse: coerce + validate ----------------------------------------------------


def test_parse_coerces_strings(orders: Orders) -> None:
    s = orders.ibis.schema()
    assert s["amount"].is_floating() and s["order_ts"].is_timestamp() and s["order_id"].is_integer()
    df = orders.to_pandas()
    assert df.amount.tolist() == [10.5, 20.0, 5.0, 7.25]
    assert math.isnan(df.discount[1])


def test_parse_projects_extra_columns_and_forbid() -> None:
    t = orders_table(extra=["x", "y", "z", "w"])
    assert "extra" not in Orders.parse(t).ibis.columns
    with pytest.raises(tc.ValidationError) as ei:
        Orders.parse(t, extra="forbid")
    assert ei.value.codes() == ["extra_column"]


def test_parse_reports_all_issues_with_counts_and_samples() -> None:
    t = orders_table(
        amount=["-1", "abc", "5", "-3"],
        status=["shipped", "lost", "cancelled", "shipped"],
        order_id=[1, 1, 2, 3],
        customer_id=[10, None, 20, 30],
    )
    with pytest.raises(tc.ValidationError) as ei:
        Orders.parse(t)
    err = ei.value
    by = {(i.code, i.column): i for i in err.issues}
    assert by[("coercion", "amount")].count == 1 and by[("coercion", "amount")].samples == ("abc",)
    assert by[("constraint", "amount")].count == 2 and set(by[("constraint", "amount")].samples) == {"-1.0", "-3.0"}
    assert by[("constraint", "status")].samples == ("lost",)
    assert by[("null", "customer_id")].count == 1
    assert by[("unique", "order_id")].count == 1 and by[("unique", "order_id")].samples == ("1",)
    msg = str(err)
    assert msg.startswith("Orders.parse: 5 issues for Orders")
    assert "amount: constraint ge(0) failed; 2 rows; e.g." in msg and "'lost'" in msg


def test_parse_nan_is_null_for_non_nullable_float() -> None:
    class F(tc.Frame):
        x: Column[float]

    with pytest.raises(tc.ValidationError) as ei:
        F.parse(ibis.memtable({"x": [1.0, float("nan")]}))
    assert ei.value.codes() == ["null"]


def test_parse_custom_check_and_str_matches() -> None:
    def even(c: Column[int]) -> Column[bool]:
        return c % 2 == 0

    class F(tc.Frame):
        n: Column[int] = tc.field(checks=[tc.check(even)])
        email: Annotated[Column[str], tc.str_matches(r"[^@]+@[^@]+$")]

    t = ibis.memtable({"n": [2, 3], "email": ["a@b", "nope"]})
    with pytest.raises(tc.ValidationError) as ei:
        F.parse(t)
    labels = {i.expected for i in ei.value.issues}
    assert labels == {"check(even)", "str_matches('^[^@]+@[^@]+$')"}


def test_parse_e6_csvs_and_bad_csv(con: Any) -> None:
    from ecommerce.pipeline import RawOrder

    RawOrder.parse(con.read_csv(E6 / "orders.csv"))
    with pytest.raises(tc.ValidationError) as ei:
        RawOrder.parse(con.read_csv(E6 / "bad" / "orders_neg_amount.csv"))
    (issue,) = ei.value.issues
    assert (issue.code, issue.column, issue.expected, issue.count) == ("constraint", "amount", "ge(0)", 1)
    assert issue.samples  # the failing value is in the message


# -- cast: structural only ----------------------------------------------------------


def test_cast_accepts_not_null_and_timestamp6(con: Any) -> None:
    con.raw_sql("create table t (x double not null, ts timestamp not null, n bigint)")

    class F(tc.Frame):
        x: Column[float]
        ts: Column[datetime]
        n: Column[int | None]

    t = con.table("t")
    assert str(t.schema()["x"]) == "!float64"
    F.cast(t)  # tacit 0.2 rejected !float64 and timestamp(6)
    F.cast(con.read_csv(E6 / "orders.csv").select(x="amount", ts="order_ts", n="order_id"))


def test_cast_reports_missing_and_dtype() -> None:
    with pytest.raises(tc.ValidationError) as ei:
        Customers.cast(ibis.memtable({"customer_id": ["x"], "name": ["a"]}))
    assert sorted(ei.value.codes()) == ["dtype", "missing_column"]


def test_explicit_dtype_override() -> None:
    class F(tc.Frame):
        x: Column[float] = tc.field(dtype="float32")
        ts: Column[datetime] = tc.field(dtype="timestamp('UTC')")

    t = ibis.memtable({"x": [1.0], "ts": [datetime(2024, 1, 1)]})
    with pytest.raises(tc.ValidationError):
        F.cast(t)  # float64 / naive timestamp do not match the explicit dtypes
    parsed = F.parse(t)
    assert str(parsed.ibis.schema()["x"]) == "float32"
    assert parsed.ibis.schema()["ts"].timezone == "UTC"


# -- construction ---------------------------------------------------------------------


def test_constructor_projection_and_widening(orders: Orders) -> None:
    class P(tc.Frame):
        order_id: Column[int]
        amount: Column[float]
        label: Column[str]

    p = P(order_id=orders.order_id, amount=orders.customer_id, label="web")  # int -> float widened
    assert p.ibis.columns == ("order_id", "amount", "label")
    assert p.ibis.schema()["amount"].is_floating()
    assert p.to_pandas().label.tolist() == ["web"] * 4


def test_constructor_runtime_errors(orders: Orders, customers: Customers) -> None:
    kw: dict[str, Any] = {"net_amount": orders.status}
    with pytest.raises(tc.ValidationError) as ei:
        NetAmount(**kw)
    assert ei.value.codes() == ["dtype"]
    with pytest.raises(tc.ValidationError) as ei:
        NetAmount(**{})
    assert ei.value.codes() == ["missing_column"]
    with pytest.raises(tc.ValidationError) as ei:
        OrderWithCountry(order_id=orders.order_id, customer_id=orders.customer_id, country=customers.country)
    assert ei.value.codes() == ["relation"] and "tc.join" in str(ei.value)


def test_constructor_resolves_class_level_refs(orders: Orders) -> None:
    class P(tc.Frame):
        order_id: Column[int]
        amount: Column[float]

    p = P(order_id=orders.order_id, amount=Orders.amount * 2)  # deferred ref bound to orders' table
    assert p.to_pandas().amount.tolist() == [21.0, 40.0, 10.0, 14.5]
    # Known hole: statically Column[float], at runtime a Deferred -> cannot be mixed with bound columns.
    with pytest.raises(ibis.common.exceptions.InputTypeError):
        orders.amount + Orders.amount


def test_implicit_group_by(orders: Orders) -> None:
    s = Stats(status=orders.status, n=orders.order_id.count(), total=orders.amount.sum())
    got = s.to_pandas().set_index("status")
    assert got.loc["shipped"].tolist() == [2, 17.75]


def test_global_aggregate_and_literal(orders: Orders) -> None:
    s = Stats(status="all", n=orders.order_id.count(), total=orders.amount.sum())
    assert s.to_pandas().iloc[0].tolist() == ["all", 4, 42.75]


def test_explicit_aggregate_by(orders: Orders) -> None:
    s = Stats.aggregate(by=[orders.status])(status=orders.status, n=orders.order_id.count(), total=orders.amount.sum())
    assert len(s.to_pandas()) == 3
    with pytest.raises(tc.ValidationError) as ei:  # forgot .sum(): implicit form would group by amount
        Stats.aggregate(by=[orders.status])(status=orders.status, n=orders.order_id.count(), total=orders.amount)
    assert ei.value.issues[0].code == "not_a_reduction" and ei.value.issues[0].column == "total"
    silently_wrong = Stats(status=orders.status, n=orders.order_id.count(), total=orders.amount)
    assert len(silently_wrong.to_pandas()) == 4  # the implicit form's documented trap


# -- extend -----------------------------------------------------------------------------


def test_extend(orders: Orders) -> None:
    kept = orders.filter(orders.status != "cancelled")
    net = NetOrders.extend(kept, NetAmount(net_amount=kept.amount - kept.discount.fill_null(0)))
    assert net.ibis.columns == (*tc.fields(Orders), "net_amount")
    assert net.to_pandas().net_amount.tolist() == [9.5, 20.0, 7.25]


def test_extend_missing_delta_and_foreign_delta(orders: Orders, customers: Customers) -> None:
    with pytest.raises(tc.ValidationError) as ei:
        NetOrders.extend(orders, Scored(score=orders.amount))  # type: ignore[arg-type]
    assert ei.value.issues[0].code == "missing_column" and ei.value.issues[0].column == "net_amount"
    with pytest.raises(tc.ValidationError) as ei:
        NetOrders.extend(orders, NetAmount(net_amount=customers.customer_id))
    assert ei.value.codes() == ["relation"]


def test_additive_generic_step(orders: Orders) -> None:
    def add_score[O: Scored](df: tc.Into[O], amount: Column[float], out: type[O]) -> O:
        return out.extend(df, Scored(score=amount * 0.1))

    s = add_score(orders, orders.amount, ScoredOrders)
    assert isinstance(s, ScoredOrders) and s.ibis.columns[-1] == "score"


# -- joins --------------------------------------------------------------------------------


def test_join_lambda_and_pairs(orders: Orders, customers: Customers) -> None:
    for on in (
        lambda o, c: o.customer_id == c.customer_id,
        [(orders.customer_id, customers.customer_id)],
    ):
        j = tc.join(orders, customers, on=on)
        out = OrderWithCountry(order_id=j.left.order_id, customer_id=j.right.customer_id, country=j.right.country)
        got = out.order_by(out.order_id).to_pandas()
        assert got.country.tolist() == ["DE", "DE", "US", "GB"]
        assert out.ibis.columns == ("order_id", "customer_id", "country")  # no customer_id_right


def test_left_join_and_self_join(orders: Orders, customers: Customers) -> None:
    few = customers.filter(customers.country == "DE")
    j = tc.join(orders, few, on=lambda o, c: o.customer_id == c.customer_id, how="left")
    out = OrderWithCountry(order_id=j.left.order_id, customer_id=j.left.customer_id, country=j.right.country)
    assert out.to_pandas().country.isna().sum() == 2  # nullable at runtime, not in the static type
    s = tc.join(orders, orders, on=lambda a, b: a.customer_id == b.customer_id)
    assert s.table.count().execute() == 6


def test_join_pair_from_wrong_frame(orders: Orders, customers: Customers) -> None:
    with pytest.raises(ValueError, match="not a column of this Customers"):
        tc.join(orders, customers, on=[(orders.customer_id, orders.customer_id)])


# -- generic steps -------------------------------------------------------------------------


def test_latest_per_key_with_handles(orders: Orders, customers: Customers) -> None:
    from ecommerce.pipeline import latest_per_key

    latest = latest_per_key(orders, key=orders.customer_id, ts=orders.order_ts)
    assert isinstance(latest, Orders)
    assert sorted(latest.to_pandas().order_id.tolist()) == [2, 3, 4]
    kept = orders.filter(orders.amount > 6)  # handles of the parent frame dereference through filter
    assert latest_per_key(kept, key=orders.customer_id, ts=orders.order_ts).ibis.count().execute() == 2
    # A handle from another frame: ibis rejects it while the step builds its window expression.
    with pytest.raises(ibis.common.exceptions.IbisError, match="single relation"):
        latest_per_key(orders, key=customers.customer_id, ts=orders.order_ts)
    # ... and tacit's own Frame methods turn it into a ValidationError.
    with pytest.raises(tc.ValidationError, match="not derived from this frame"):
        orders.filter(customers.customer_id > 1)


def test_mixin_bound_generic(orders: Orders) -> None:
    def recent[F: HasTs](df: F, since: datetime) -> F:
        return df.filter(df.order_ts >= since)

    class OrdersTs(Orders, HasTs):
        pass

    o = OrdersTs.cast(orders)
    r = recent(o, datetime(2024, 1, 2))
    assert isinstance(r, OrdersTs) and r.ibis.count().execute() == 3


def test_distinct_on_handle(orders: Orders) -> None:
    assert orders.distinct(on=orders.customer_id).ibis.count().execute() == 3


# -- @step ----------------------------------------------------------------------------------


def test_step_checks_frames_and_names_the_step(orders: Orders, customers: Customers) -> None:
    @tc.step
    def clean(o: Orders, c: Customers | None = None) -> NetOrders:
        return NetOrders.extend(o, NetAmount(net_amount=o.amount))

    assert isinstance(clean(orders), NetOrders)
    clean(orders, None)
    bad: Any = customers
    with pytest.raises(tc.ValidationError, match=r"step .*clean\(\), argument 'o'") as ei:
        clean(bad)
    assert ei.value.codes() == ["wrong_frame"]
    with pytest.raises(tc.ValidationError, match="raw ibis Table"):
        clean(orders.ibis)  # type: ignore[arg-type]
    with pytest.raises(tc.ValidationError, match="argument 'c'"):
        clean(orders, orders)  # type: ignore[arg-type]


def test_step_wraps_body_errors_with_step_name(orders: Orders) -> None:
    @tc.step
    def forgot(o: Orders) -> NetOrders:
        return NetOrders.extend(o, Scored(score=o.amount))  # type: ignore[arg-type]

    with pytest.raises(tc.ValidationError, match=r"^step .*forgot\(\): NetOrders.extend"):
        forgot(orders)


def test_step_typevar_return_must_match_argument_class(orders: Orders) -> None:
    @tc.step
    def same[F: tc.Frame](df: F) -> F:
        return df

    @tc.step
    def liar[F: tc.Frame](df: F) -> F:
        bad: Any = Customers.parse(customers_table())
        return bad  # type: ignore[no-any-return]

    same(orders)
    with pytest.raises(tc.ValidationError, match="return value"):
        liar(orders)


def test_step_validate_true_runs_data_checks() -> None:
    @tc.step(validate=True)
    def ident(o: Orders) -> Orders:
        return o

    unchecked = Orders.cast(Orders.parse(orders_table()).ibis.mutate(amount=-ibis._.amount))
    with pytest.raises(tc.ValidationError, match=r"(?s)step .*ident\(\), argument 'o'.*ge\(0\)"):
        ident(unchecked)


def test_step_lazy_annotations_type_checking_import(orders: Orders) -> None:
    import _late_step

    assert _late_step.passthrough(orders) is orders
    with pytest.raises(tc.ValidationError):
        _late_step.passthrough(Customers.parse(customers_table()))  # type: ignore[arg-type]


def test_step_rejects_unenforceable_annotation(orders: Orders) -> None:
    @tc.step
    def f(d: dict[str, Orders]) -> None: ...

    with pytest.raises(TypeError, match="cannot enforce"):
        f({"a": orders})


# -- class creation -----------------------------------------------------------------------


def test_reserved_names_and_physical_name_mapping() -> None:
    with pytest.raises(TypeError, match="Frame method name"):

        class Bad(tc.Frame):
            filter: Column[str]

    class Ok(tc.Frame):
        filter_: Column[str] = tc.field(name="filter")
        count_: Column[int] = tc.field(name="count")

    ok = Ok.parse(ibis.memtable({"filter": ["a"], "count": [1]}))
    assert ok.to_pandas().columns.tolist() == ["filter", "count"]
    assert ok.filter_.get_name() == "filter"


def test_conflicting_bases_and_bad_annotations() -> None:
    class A(tc.Frame):
        x: Column[int]

    class B(tc.Frame):
        x: Column[str]

    with pytest.raises(TypeError, match="conflicting"):

        class AB(A, B):
            x: Column[int]

    with pytest.raises(TypeError, match=r"annotate frame columns as Column\[T\]"):

        class Plain(tc.Frame):
            x: float

    with pytest.raises(TypeError, match="does not match"):

        class WrongDtype(tc.Frame):
            x: Column[int] = tc.field(dtype="string")


def test_field_order_follows_bases(orders: Orders) -> None:
    assert list(tc.fields(NetOrders)) == [*tc.fields(Orders), "net_amount"]
    assert tc.fields(Orders)["discount"].nullable and not tc.fields(Orders)["amount"].nullable
    assert str(tc.schema(Customers)["country"]) == "string"


def test_e6_pipeline_end_to_end() -> None:
    from ecommerce import pipeline

    pipeline.main()
