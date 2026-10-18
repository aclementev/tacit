import dataframely as dy
import polars as pl
from dataframely.experimental.infer_schema import infer_schema


class Users(dy.Schema):
    user_id = dy.Int64(primary_key=True)
    name = dy.String()

class Orders(dy.Schema):
    user_id = dy.Int64(primary_key=True)
    order_no = dy.Int64(primary_key=True)

class Shop(dy.Collection):
    users: dy.LazyFrame[Users]
    orders: dy.LazyFrame[Orders]

    @dy.filter()
    def every_user_has_order(self) -> pl.LazyFrame:
        return dy.functional.require_relationship_one_to_at_least_one(self.users, self.orders, on="user_id")

u = pl.LazyFrame({"user_id": [1, 2], "name": ["a", "b"]})
o = pl.LazyFrame({"user_id": [1], "order_no": [10]})
res, failure = Shop.filter({"users": u, "orders": o}, cast=True)
print(res.users.collect(), {k: v.counts() for k, v in failure.items()})
s = Shop.sample(overrides=[{"orders": [{}]} for _ in range(3)])
print(s.users.collect(), s.orders.collect())
print(infer_schema(pl.DataFrame({"a": [1], "b": ["x"]}), "Gen"))
print(Users.to_pydantic_model())
