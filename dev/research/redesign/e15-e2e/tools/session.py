"""Replay an interactive (REPL / notebook-style) session against examples/e2e.py and record it.

    cd dev/research/redesign && uv run --frozen python e15-e2e/tools/session.py > e15-e2e/out/session.txt

Every block is fed to `code.InteractiveConsole`, so values echo and tracebacks print exactly
as in `python -i`. Nothing is edited after the fact.
"""

import code
import contextlib
import io
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
os.chdir(HERE)
sys.path[:0] = [str(HERE / "src"), str(HERE / "examples")]
os.environ["PAGER"] = "cat"

BLOCKS = [
    ("setup", """
import ibis
import ibis.expr.types as ir
from ibis import _
import tacit_t3 as tacit
from e2e import *
con = ibis.duckdb.connect()
events = OrderEvents.parse(con.read_csv("examples/sources/orders.csv"))
customers = Customers.parse(con.read_csv("examples/sources/customers.csv"))
orders = add_metrics(keep_latest(events, key=events.c.order_id, ts=events.c.updated_at))
facts = with_customer(delivered(orders), customers)
"""),
    ("what is a frame", """
type(events), isinstance(events, ir.Table)
events
events.head()
events.head(3).execute()
ibis.options.interactive = True
events.head(3)
ibis.options.interactive = False
"""),
    ("columns, schema, docs", """
events.c
dir(events.c)
events.c.amount
events.c.amount.sum().execute()
events.schema()
OrderEvents
OrderEvents.__tacit_fields__["amount"]
help(OrderEvents)
"""),
    ("plain ibis on the frame", """
type(events.mutate(x=1))
events.group_by("status").agg(n=_.count()).order_by("status").execute()
ibis.union(events, events).count().execute()
"""),
    ("error: bad CSV rows at ingestion", """
OrderEvents.parse(con.read_csv("examples/sources/orders_bad.csv"))
"""),
    ("error: structured issues", """
try:
    OrderEvents.parse(con.read_csv("examples/sources/orders_bad.csv"))
except tacit.ValidationError as e:
    err = e

[(i.code, i.column, i.count, i.samples) for i in err.issues]
"""),
    ("error: wrong frame passed to a step (with and without @tacit.step)", """
customer_value(orders)
monthly_revenue(orders)
"""),
    ("error: missing column after a raw-ibis detour", """
per_customer = facts.group_by("customer_id", "country").agg(revenue=_.net_amount.sum())
CustomerValue.conform(per_customer)
"""),
    ("error: typo at runtime", """
events.c.amout
events.amout
"""),
    ("error: null in a non-null output", """
DeliveredOrders.extend(orders, DeliveryTime.build(delivery_hours=orders.c.delivered_at.assume_not_null().delta(orders.c.ordered_at, unit="hour")))
leaky = facts.group_by("customer_id", "country").agg(orders=_.order_id.count(), revenue=_.net_amount.sum(), first_month=_.order_month.min()).mutate(share_of_country=ibis.null("float64"))
accepted = CustomerValue.conform(leaky)          # structural only: no query, NULLs pass
accepted.c.share_of_country.isnull().sum().execute()
CustomerValue.parse(leaky)
"""),
    ("error: join on the wrong key", """
j = tacit.join(orders, customers, on=lambda o, c: o.order_id == c.customer_id)
j
tacit.join(orders, customers, on=[(orders.c.customer_id, events.c.customer_id)])
tacit.join(orders, customers, on=lambda o, c: o.customer_id == c.country)
"""),
    ("error: forgotten reduction / mixed build", """
MonthlyRevenue.aggregate(by=[facts.c.country])(country=facts.c.country, order_month=facts.c.order_month, orders=facts.c.order_id.count(), app_orders=facts.c.order_id.count(), revenue=facts.c.net_amount.sum(), avg_order_value=facts.c.net_amount.mean(), avg_delivery_hours=facts.c.delivery_hours.mean())
MonthlyRevenue.build(country=facts.c.country, order_month=facts.c.order_month, orders=facts.c.order_id.count(), app_orders=facts.c.order_id.count(), revenue=facts.c.net_amount.sum(), avg_order_value=facts.c.net_amount.mean(), avg_delivery_hours=facts.c.delivery_hours.mean())
"""),
    ("error: handle from another frame in a generic step", """
keep_latest(events, key=customers.c.customer_id, ts=events.c.updated_at)
"""),
]


def main() -> None:
    console = code.InteractiveConsole(locals={"__name__": "__console__"})
    for title, block in BLOCKS:
        print(f"\n# ---- {title} " + "-" * max(0, 80 - len(title)))
        buf_lines: list[str] = []
        lines = block.strip("\n").splitlines()
        for i, line in enumerate(lines):
            print(("... " if buf_lines else ">>> ") + line)
            buf_lines.append(line)
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                more = console.push(line)
            # a blank line closes a compound statement in the REPL
            if more and (i + 1 == len(lines) or not lines[i + 1].startswith((" ", "except", "else", "finally"))):
                print("... ")
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                    more = console.push("")
            text = out.getvalue()
            if text:
                print(text, end="" if text.endswith("\n") else "\n")
            if not more:
                buf_lines = []


if __name__ == "__main__":
    main()
