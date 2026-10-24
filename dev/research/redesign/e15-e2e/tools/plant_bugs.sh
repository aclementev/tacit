#!/usr/bin/env bash
# Plant 8 bugs into a copy of examples/e2e.py and record what each checker reports.
#   ./e15-e2e/tools/plant_bugs.sh   (from anywhere)
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
sed \
  -e 's/net_amount=e.amount - e.discount.fill_null(0)/net_amount=e.amount - e.discount/' \
  -e 's/facts = with_customer(delivered(orders), customers)/facts = with_customer(orders, customers)/' \
  -e 's/f.delivery_hours.mean()/f.delivery_hour.mean()/' \
  -e 's/    return CustomerValue.conform(/    return (/' \
  -e 's/on=lambda o, c: o.customer_id == c.customer_id/on=lambda o, c: o.customer_id == c.country/' \
  -e 's/orders=f.order_id.count(),/orders=f.net_amount.sum(),/' \
  -e 's/events = OrderEvents.parse(con.read_csv(sources \/ "orders.csv"))/events = OrderEvents.parse(con.read_csv(sources \/ "orders.csv"))\n    events.order_id/' \
  -e 's/order_month=e.ordered_at.truncate("M").date(),/order_month=e.ordered_at.truncate("M"),/' \
  "$HERE/examples/e2e.py" > "$HERE/tests/bugs/e2e_bugs.py"
echo "planted: nullable->non-null, wrong frame, typo, forgot conform, int==str join key, float count, column on frame (no .c), datetime->date"
"$HERE/chk.sh" "$HERE/tests/bugs/e2e_bugs.py" 2>&1 | sed "s|$HERE/||" | cut -c1-200
