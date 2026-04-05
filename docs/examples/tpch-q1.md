# TPC-H Q1

[TPC-H Query 1](https://duckdb.org/docs/extensions/tpch.html) (Pricing Summary
Report) is a standard analytics benchmark. This example demonstrates tacit with
a real analytical query — filtering, aggregations, and composing multiple
`@contract` functions into a pipeline.

The full source is at
[`examples/tpch_q1.py`](https://github.com/alvaroclemente/tacit/blob/main/examples/tpch_q1.py).

## Schemas

The input and output schemas are completely different — this isn't adding
columns like the [Iris example](iris-pipeline.md), it's a full reshape via
aggregation:

```python
import ibis
import tacit


class LineItem(tacit.Schema):
    l_orderkey: int
    l_partkey: int
    l_suppkey: int
    l_linenumber: int
    l_quantity: float
    l_extendedprice: float
    l_discount: float
    l_tax: float
    l_returnflag: str
    l_linestatus: str
    l_shipdate: str
    l_commitdate: str
    l_receiptdate: str


class PricingSummary(tacit.Schema):
    l_returnflag: str
    l_linestatus: str
    sum_qty: float
    sum_base_price: float
    sum_disc_price: float
    sum_charge: float
    avg_qty: float
    avg_price: float
    avg_disc: float
    count_order: int
```

`LineItem` has 13 columns. `PricingSummary` has 10 — mostly aggregated values.
No inheritance here, just two independent schemas connected by contracts.

## Composing contracted functions

The query is split into two contracted functions — a filter and an aggregation.
Each function declares its input and output schemas, and `@contract` verifies
them at runtime. The pipeline composes them by chaining the outputs:

```python
@tacit.contract
def filter_shipped(
    lineitem: tacit.DataFrame[LineItem],
) -> tacit.DataFrame[LineItem]:
    return lineitem.filter(lineitem.l_shipdate <= "1998-09-02")


@tacit.contract
def pricing_summary_report(
    lineitem: tacit.DataFrame[LineItem],
) -> tacit.DataFrame[PricingSummary]:
    return (
        lineitem.group_by("l_returnflag", "l_linestatus")
        .agg(
            sum_qty=lineitem.l_quantity.sum(),
            sum_base_price=lineitem.l_extendedprice.sum(),
            sum_disc_price=(
                lineitem.l_extendedprice * (1 - lineitem.l_discount)
            ).sum(),
            sum_charge=(
                lineitem.l_extendedprice
                * (1 - lineitem.l_discount)
                * (1 + lineitem.l_tax)
            ).sum(),
            avg_qty=lineitem.l_quantity.mean(),
            avg_price=lineitem.l_extendedprice.mean(),
            avg_disc=lineitem.l_discount.mean(),
            count_order=lineitem.l_orderkey.count(),
        )
        .order_by("l_returnflag", "l_linestatus")
    )
```

`filter_shipped` takes `DataFrame[LineItem]` and returns `DataFrame[LineItem]`
— same schema, fewer rows. `pricing_summary_report` takes `DataFrame[LineItem]`
and returns `DataFrame[PricingSummary]` — a completely different schema.

Because both functions declare their schemas in the type annotations, they
compose naturally: the output type of one matches the input type of the next.
If you tried to pass a `DataFrame[PricingSummary]` to `filter_shipped`, the
type checker would catch it — and the contract would catch it at runtime.

## Pipeline

```python
def pipeline(path: str) -> tacit.DataFrame[PricingSummary]:
    con = ibis.duckdb.connect()
    raw = con.read_csv(path)
    lineitem = LineItem.parse(raw)
    shipped = filter_shipped(lineitem)
    return pricing_summary_report(shipped)
```

`parse()` validates the 13-column CSV input. Then the two contracted functions
chain: `LineItem` → `LineItem` → `PricingSummary`. The types guide the
composition — you can read the pipeline and know exactly what schema each
variable holds.

## Running it

```bash
uv run python examples/tpch_q1.py
```
