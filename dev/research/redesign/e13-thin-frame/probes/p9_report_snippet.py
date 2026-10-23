"""The before/after snippet used in REPORT.html, T2 spelling. Expected: 2 errors (typo, nullable)."""
import tacit_t2 as tacit
from tacit_t2 import Column, DataFrame
from tacit_thin import field


class RawOrder(tacit.Schema):
    status: Column[str] = field(isin=["pending", "shipped", "cancelled"])
    amount: Column[float] = field(ge=0)
    discount: Column[float | None]


class NetAmount(tacit.Schema):
    net_amount: Column[float]


class Order(RawOrder, NetAmount):
    pass


def clean(o: DataFrame[RawOrder]) -> DataFrame[Order]:
    kept = o.filter(o.c.statu != "cancelled")
    return Order.extend(kept, NetAmount.build(net_amount=kept.c.amount - kept.c.discount))


def clean_ok(o: DataFrame[RawOrder]) -> DataFrame[Order]:
    kept = o.filter(o.c.status != "cancelled")
    return Order.extend(kept, NetAmount.build(net_amount=kept.c.amount - kept.c.discount.fill_null(0)))


def forgot(o: DataFrame[RawOrder]) -> DataFrame[Order]:
    return o.mutate(net_amount=o.c.amount)
