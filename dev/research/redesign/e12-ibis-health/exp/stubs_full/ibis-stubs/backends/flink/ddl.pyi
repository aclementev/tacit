import ibis.expr.schema as sch
from _typeshed import Incomplete
from collections.abc import Generator, Sequence
from ibis.backends.sql.datatypes import FlinkType as FlinkType
from ibis.backends.sql.ddl import CreateDDL as CreateDDL, DDL as DDL, DML as DML, DropObject as DropObject
from ibis.expr.api import Watermark as Watermark
from ibis.util import promote_list as promote_list

class FlinkBase:
    dialect: str
    def format_dtype(self, dtype): ...
    def format_properties(self, props): ...
    def format_watermark_strategy(self, watermark: Watermark) -> str: ...
    def format_schema_with_watermark(self, schema: sch.Schema, watermark: Watermark | None = None, primary_keys: Sequence[str] | None = None) -> str: ...

class CreateTableWithSchema(FlinkBase, CreateDDL):
    can_exist: Incomplete
    catalog: Incomplete
    database: Incomplete
    partition: Incomplete
    primary_keys: Incomplete
    schema: Incomplete
    table_name: Incomplete
    tbl_properties: Incomplete
    temporary: Incomplete
    watermark: Incomplete
    def __init__(self, table_name: str, schema: sch.Schema, database=None, catalog=None, can_exist: bool = False, external: bool = False, partition=None, primary_key: str | Sequence[str] | None = None, tbl_properties=None, temporary: bool = False, watermark: Watermark | None = None) -> None: ...
    @property
    def pieces(self) -> Generator[Incomplete, Incomplete]: ...
    def compile(self): ...

class CreateView(FlinkBase, CreateDDL):
    name: Incomplete
    query_expression: Incomplete
    catalog: Incomplete
    temporary: Incomplete
    def __init__(self, name: str, query_expression: str, database: str | None = None, catalog: str | None = None, can_exist: bool = False, temporary: bool = False) -> None: ...
    @property
    def pieces(self) -> Generator[Incomplete]: ...
    def compile(self): ...

class DropTable(FlinkBase, DropObject):
    table_name: Incomplete
    database: Incomplete
    catalog: Incomplete
    temporary: Incomplete
    def __init__(self, table_name: str, database: str | None = None, catalog: str | None = None, must_exist: bool = True, temporary: bool = False) -> None: ...
    def compile(self): ...

class DropView(DropTable):
    def __init__(self, name: str, database: str | None = None, catalog: str | None = None, must_exist: bool = True, temporary: bool = False) -> None: ...

class RenameTable(FlinkBase, DDL):
    old_name: Incomplete
    new_name: Incomplete
    must_exist: Incomplete
    def __init__(self, old_name: str, new_name: str, must_exist: bool = True) -> None: ...
    def compile(self): ...

class _DatabaseObject: ...

class CreateDatabase(FlinkBase, _DatabaseObject, CreateDDL):
    name: Incomplete
    db_properties: Incomplete
    catalog: Incomplete
    can_exist: Incomplete
    def __init__(self, name: str, db_properties: dict | None, catalog: str | None = None, can_exist: bool = False) -> None: ...
    def compile(self): ...

class DropDatabase(FlinkBase, _DatabaseObject, DropObject):
    name: Incomplete
    catalog: Incomplete
    def __init__(self, name: str, catalog: str | None = None, must_exist: bool = True) -> None: ...

class InsertSelect(FlinkBase, DML):
    table_name: Incomplete
    database: Incomplete
    catalog: Incomplete
    select: Incomplete
    partition: Incomplete
    partition_schema: Incomplete
    overwrite: Incomplete
    def __init__(self, table_name, select_expr, database: str | None = None, catalog: str | None = None, partition=None, partition_schema=None, overwrite: bool = False) -> None: ...
    def compile(self): ...
