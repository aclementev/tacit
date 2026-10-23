"""Runtime side of `_ibis_api.pyi`: the real ibis classes.

Checkers read the generated `.pyi` (a clean mirror of the ibis Table API with no
`__getattr__` and no base class); at runtime `tc.Table` IS `ibis.expr.types.Table`.
"""

from ibis.expr.types import Table
from ibis.expr.types.groupby import GroupedTable

TableAPI = Table  # static: the frame base (no __getattr__); runtime: the same ibis class

__all__ = ["GroupedTable", "Table", "TableAPI"]
