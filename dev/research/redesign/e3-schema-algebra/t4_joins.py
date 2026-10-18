"""4. Joins: join(DataFrame[A], DataFrame[B]) -> ?"""

from typing import Protocol, reveal_type

from tx import DataFrame, Schema, SchemaLike, join


class Orders(Schema):
    id: int
    customer_id: int
    amount: float


class Customers(Schema):
    customer_id: int
    name: str


class Products(Schema):
    sku: str


class OrdersWithCustomer(Orders, Customers):  # explicit output schema: A & B by inheritance
    pass


class OrdersOnly(Orders):
    name: str


class Clash(Schema):
    customer_id: str  # same name, different type


class HasNameP(SchemaLike, Protocol):
    name: str


def needs_name[S: HasNameP](df: DataFrame[S]) -> None: ...


def use(o: DataFrame[Orders], c: DataFrame[Customers], p: DataFrame[Products]) -> None:
    r = join(o, c, OrdersWithCustomer, "customer_id")
    reveal_type(r)  # case: J1 join(o, c, OrdersWithCustomer) expect: ok
    needs_name(r)  # case: J1 result usable by generic steps expect: ok
    join(o, c, OrdersOnly, "customer_id")  # case: J1 out not a subclass of right (has the columns though) expect: err
    join(o, p, OrdersWithCustomer, "customer_id")  # case: J1 wrong right input expect: err
    join(c, o, OrdersWithCustomer, "customer_id")  # case: J1 argument order irrelevant expect: ok


def use_classmethod(o: DataFrame[Orders], c: DataFrame[Customers], p: DataFrame[Products]) -> None:
    reveal_type(OrdersWithCustomer.from_join(o, c, "customer_id"))  # case: J1c Out.from_join(o, c) expect: ok
    OrdersOnly.from_join(o, c, "customer_id")  # case: J1c out not a subclass of right expect: err
    OrdersWithCustomer.from_join(o, p, "customer_id")  # case: J1c wrong right input expect: err
    OrdersWithCustomer.from_join(c, o, "customer_id")  # case: J1c argument order irrelevant expect: ok


class BadJoin(Orders, Clash):  # case: J1 conflicting column types in out schema expect: err
    pass


# J2: generic tag type, no named output schema
class Joined[A: SchemaLike, B: SchemaLike](DataFrame[A]):  # statically "is a" DataFrame[A] only
    pass


def join2[A: SchemaLike, B: SchemaLike](left: DataFrame[A], right: DataFrame[B], on: str) -> Joined[A, B]:
    raise NotImplementedError


def use2(o: DataFrame[Orders], c: DataFrame[Customers]) -> None:
    r = join2(o, c, "customer_id")
    reveal_type(r)  # case: J2 join2(o, c)
    needs_name(r)  # case: J2 right-side columns invisible to generic steps (want ok) expect: ok
