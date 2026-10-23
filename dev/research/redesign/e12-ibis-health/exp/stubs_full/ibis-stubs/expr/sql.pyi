import ibis.expr.datatypes as dt
import ibis.expr.schema as sch
import ibis.expr.types as ir
from _typeshed import Incomplete
from functools import singledispatch
from ibis.util import experimental
from public import public

__all__ = ['parse_sql', 'to_sql']

class Catalog(dict[str, sch.Schema]):
    typemap: Incomplete
    def to_sqlglot_dtype(self, dtype: dt.DataType) -> str: ...
    def to_sqlglot_schema(self, schema: sch.Schema) -> dict[str, str]: ...
    def to_sqlglot(self): ...
    def overlay(self, step): ...

@public
@experimental
def parse_sql(sqlstring, catalog, dialect=None): ...

class SQLString(str): ...

@public
def to_sql(expr: ir.Expr, dialect: str | None = None, pretty: bool = True, **kwargs) -> SQLString: ...
