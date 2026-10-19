# tacit-next user guide (prototype)

tacit-next gives ibis pipelines typed, validated data contracts.
- A **Frame** class declares a table's columns.
- An instance of that class *is* the typed table.
- Every column access is typed and name-checked by pyright, mypy, ty and pyrefly.
- The data is validated with a single query when it enters the pipeline.

```python
import ibis
import tacit_next as tc
from tacit_next import Column
```

## Declaring frames

```python
from datetime import date, datetime
from decimal import Decimal

class Orders(tc.Frame):
    """Orders as delivered by the order service."""
    order_id: Column[int] = tc.field(unique=True)
    customer_id: Column[int]
    order_ts: Column[datetime]
    status: Column[str] = tc.field(isin=["pending", "shipped", "cancelled"])
    amount: Column[float] = tc.field(ge=0, description="gross amount, EUR")
    discount: Column[float | None]                    # `| None` means nullable
    price: Column[Decimal] = tc.field(dtype="decimal(12, 2)")
```

- **Value types.** `Column[T]` takes a plain Python value type: `int`, `float`, `Decimal`, `str`, `bool`, `date`, `datetime` or `time`.
- **Nullability.** Columns are non-nullable unless you add `| None`.
- **`tc.field(...)` options:**
  - Constraints: `ge`, `gt`, `le`, `lt`, `isin`, `pattern` (regex), `length` / `min_length` / `max_length`, `unique`, and `checks=[...]`.
  - `dtype="..."` sets an exact physical type, such as `"int32"`, `"decimal(12, 2)"` or `"timestamp('UTC')"`.
  - `name="..."` maps the column to a different physical column name.
  - `description="..."` documents the column.
- **Reusable constraints.** Use `Annotated[Column[float], tc.ge(0)]`, or other constraint helpers: `tc.between`, `tc.notin`, `tc.str_matches`, `tc.length`, `tc.unique()`.
- **Custom checks.** Use `tc.check(lambda c: c > 0, name="positive")`.
- **Reserved names.** A column can't share a name with a Frame member (`filter`, `ibis`, `parse`, ...). Declare it as `filter_: Column[str] = tc.field(name="filter")` instead.

## Getting data in: `parse` and `cast`

```python
con = ibis.duckdb.connect()
orders = Orders.parse(con.read_csv("orders.csv"))   # coerce types + check constraints (1 query)
orders = Orders.cast(con.table("orders"))           # structure only: names + types, no query
```

**`parse`** is for untrusted input.
- It casts strings to the declared types (for example `"2024-01-03"` to `date`).
- It checks nulls, constraints and uniqueness.
- On failure it raises `tc.ValidationError`, with the count and sample values for each issue.

**`cast`** is for trusted tables.
- It checks column names and types without executing anything.
- Both `parse` and `cast` accept tables with *extra* columns, and drop them.
- Pass `extra="forbid"` to make extra columns an error.

## Working with columns

```python
orders.amount                 # Column[float]: autocompletes, typos are type errors
orders.amount * 1.21          # Column[float]
orders.discount.fill_null(0)  # Column[float | None] -> Column[float]
orders.status == "shipped"    # Column[bool]
orders.order_ts.truncate("M").date()   # Column[date]
orders.amount.sum()           # Scalar[float]  (also mean, min, max, count, nunique, ...)
tc.cases((orders.amount > 100, "big"), else_="small")   # Column[str]
tc.lit(0)                     # a literal as a column expression
```

The type checker flags these mistakes:
- the wrong method for a column's type, for example `orders.status.mean()`;
- invalid arithmetic, for example `str + int`;
- putting a nullable value where a non-null value is required.

**Schema-preserving operations** return the same frame type:

```python
shipped: Orders = orders.filter(orders.status == "shipped").order_by(orders.order_ts.desc()).limit(10)
```

**Available methods:** `filter`, `order_by`, `limit`, `distinct(on=...)` and `cache`.
- `.ibis` returns the raw ibis table, for anything else.
- `.execute()`, `.to_pandas()`, `.to_polars()` and `.to_pyarrow()` materialize the result.

## Building output frames

The constructor of a Frame is a typed **projection**. The type checker requires every column, rejects unknown columns, and checks each expression's type.

```python
class OrderSummary(tc.Frame):
    order_id: Column[int]
    net: Column[float]

def summarize(o: Orders) -> OrderSummary:
    return OrderSummary(order_id=o.order_id, net=o.amount - o.discount.fill_null(0))
```

All expressions must come from the same frame. To combine two frames, use `tc.join` (see "Joins").

### Adding columns to an existing frame: `extend`

To add a few columns without restating the existing ones, follow these steps:
1. Declare the new columns in a small "delta" frame.
2. Compose the output frame by inheriting from both the input frame and the delta.
3. Build the output with `Output.extend(...)`.

```python
class NetAmount(tc.Frame):
    net_amount: Column[float]

class NetOrders(Orders, NetAmount):   # all Orders columns + net_amount
    pass

def add_net(o: Orders) -> NetOrders:
    return NetOrders.extend(o, NetAmount(net_amount=o.amount - o.discount.fill_null(0)))
```

The type checker verifies that `NetOrders` is a subclass of both `Orders` and `NetAmount`.

### Aggregation: `aggregate(by=...)`

```python
class DailyRevenue(tc.Frame):
    day: Column[date]
    status: Column[str]
    orders: Column[int]
    revenue: Column[float]

def daily(o: Orders) -> DailyRevenue:
    day = o.order_ts.date()
    return DailyRevenue.aggregate(by=[day, o.status])(
        day=day, status=o.status, orders=o.order_id.count(), revenue=o.amount.sum(),
    )
```

Every argument that is not a `by` key must be a reduction, such as `.sum()`, `.count()` or `.mean()`. If you forget one, you get a runtime error.

## Joins

```python
class Customers(tc.Frame):
    customer_id: Column[int]
    country: Column[str]

class OrderCountry(tc.Frame):
    order_id: Column[int]
    country: Column[str]
    amount: Column[float]

def with_country(o: Orders, c: Customers) -> OrderCountry:
    j = tc.join(o, c, on=lambda o, c: o.customer_id == c.customer_id)   # how="inner" | "left" | ...
    return OrderCountry(order_id=j.left.order_id, country=j.right.country, amount=j.left.amount)
```

- `j.left` and `j.right` are typed views of the joined table.
- The output constructor names every column, so name collisions can't happen.
- `on=` also accepts column pairs, e.g. `on=[(o.customer_id, c.customer_id)]`.
- An aggregate can be built from the join views, e.g. `Out.aggregate(by=[j.right.country])(...)`.

## Generic, reusable steps

**Same frame in and out.** Pass the columns the step needs as typed handles:

```python
from typing import Any

def latest_per_key[F: tc.Frame](df: F, key: Column[Any], ts: Column[datetime]) -> F:
    return df.filter(tc.row_number().over(group_by=key, order_by=ts.desc()) == 0)

latest = latest_per_key(orders, key=orders.customer_id, ts=orders.order_ts)   # -> Orders
```

**Mixin column sets.** A step can require "any frame that has these columns":

```python
class HasEventTs(tc.Frame):
    event_ts: Column[datetime]

def recent[F: HasEventTs](df: F, since: datetime) -> F:
    return df.filter(df.event_ts >= since)

class Clicks(HasEventTs):
    user_id: Column[int]
```

**Steps that add columns.** The caller names the output class, and the step uses `tc.Into`:

```python
class Scored(tc.Frame):
    score: Column[float]

def add_score[O: Scored](df: tc.Into[O], amount: Column[float], out: type[O]) -> O:
    return out.extend(df, Scored(score=amount * 0.1))

class ScoredOrders(Orders, Scored): pass
scored = add_score(orders, orders.amount, ScoredOrders)
```

## Optional: `@tc.step`

```python
@tc.step                       # runtime check of frame arguments/returns + step name in errors
def add_net(o: Orders) -> NetOrders: ...

@tc.step(validate=True)        # also run the data checks (one query per frame) at the boundary
def ingest(raw: Orders) -> Orders: ...
```

Steps don't need `@tc.step` for type safety, because construction already guarantees structure. Use it at pipeline boundaries:
- to get data validation (`validate=True`);
- to get step names in error messages;
- when callers are untyped.

## Errors

Validation failures from `parse`, `cast`, frame constructors and `@tc.step` raise `tc.ValidationError`. Its `.issues` attribute is a list of issues, each with a code, column, expected value, actual value, count and samples. Other mistakes raise Python's usual errors. For example, a typo in a column name raises `AttributeError` (the type checker flags it first), and mixing columns from two frames inside a step body raises ibis's own error.

```
Orders.parse: 2 issues for Orders
  - amount: constraint ge(0) failed; 3 rows; e.g. ['-33.74', '-1.0', '-5.5']
  - status: constraint isin(['pending', 'shipped', 'cancelled']) failed; 1 row; e.g. ['refunded']
```

## Type checker setup

The package ships `py.typed`.

**mypy:** add this to the mypy config, because ibis ships no `py.typed`:

```ini
[mypy]
follow_untyped_imports = True
```

**pyright, ty and pyrefly** need no configuration.

## Escape hatches

- `frame.ibis` gives the raw ibis table. Operations on it are not schema-checked.
- `tc.as_ibis(col)` turns a typed column into a raw ibis expression.
- `tc.as_column(expr)` does the reverse.
- To get back into typed territory, call `Frame.cast(table)` or use a constructor.
