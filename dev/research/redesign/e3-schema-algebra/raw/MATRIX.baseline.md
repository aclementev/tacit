
### baseline.py (stock ibis 12.0.0)

| case | expect | pyright | mypy | ty | pyrefly |
|---|---|---|---|---|---|
| df |  | DataFrame[Orders] | tacit.schema.DataFrame[baseline.Orders] | DataFrame[Orders] | DataFrame[Orders] |
| df.id |  | Column | Any | Unknown | Unknown |
| df.nonexistent (no name checking) |  | Column | Any | Unknown | Unknown |
| df.filter(...) drops S |  | Table | Any | Table | Table |
| Orders.cast(df) |  | DataFrame[Orders] | tacit.schema.DataFrame[baseline.Orders] | DataFrame[Orders] | DataFrame[Orders] |
| ir.Table -> DataFrame[Orders] | err | ERR(reportReturnType) | ok ! | ok ! | ok ! |
| DataFrame[Customers] -> DataFrame[Orders] | err | ERR(reportReturnType) | ok ! | ERR(invalid-return-type) | ERR(bad-return) |
| DataFrame[BigOrders] -> DataFrame[Orders] (invariant) | err | ERR(reportReturnType) | ok ! | ERR(invalid-return-type) | ERR(bad-return) |
| DataFrame[Orders] -> int | err | ERR(reportReturnType) | ok ! | ok ! | ok ! |

### baseline.py (patched ibis)

| case | expect | pyright | mypy | ty | pyrefly |
|---|---|---|---|---|---|
| df |  | DataFrame[Orders] | tacit.schema.DataFrame[baseline.Orders] | DataFrame[Orders] | DataFrame[Orders] |
| df.id |  | Column | ibis.expr.types.generic.Column | Column | Column |
| df.nonexistent (no name checking) |  | Column | ibis.expr.types.generic.Column | Column | Column |
| df.filter(...) drops S |  | Table | ibis.expr.types.relations.Table | Table | Table |
| Orders.cast(df) |  | DataFrame[Orders] | tacit.schema.DataFrame[baseline.Orders] | DataFrame[Orders] | DataFrame[Orders] |
| ir.Table -> DataFrame[Orders] | err | ERR(reportReturnType) | ERR(return-value) | ERR(invalid-return-type) | ERR(bad-return) |
| DataFrame[Customers] -> DataFrame[Orders] | err | ERR(reportReturnType) | ERR(return-value) | ERR(invalid-return-type) | ERR(bad-return) |
| DataFrame[BigOrders] -> DataFrame[Orders] (invariant) | err | ERR(reportReturnType) | ERR(return-value) | ERR(invalid-return-type) | ERR(bad-return) |
| DataFrame[Orders] -> int | err | ERR(reportReturnType) | ERR(return-value) | ERR(invalid-return-type) | ERR(bad-return) |
