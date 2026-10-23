import ibis.expr.schema as sch
import ibis.expr.types as ir
import pandas as pd
import pyarrow as pa
import pydruid.db
from _typeshed import Incomplete
from ibis import util as util
from ibis.backends import HasCurrentCatalog as HasCurrentCatalog, HasCurrentDatabase as HasCurrentDatabase, NoExampleLoader as NoExampleLoader
from ibis.backends.sql import SQLBackend as SQLBackend
from ibis.backends.sql.compilers.base import STAR as STAR
from ibis.backends.sql.datatypes import DruidType as DruidType
from ibis.backends.tests.errors import PyDruidProgrammingError as PyDruidProgrammingError
from typing import Any
from urllib.parse import ParseResult as ParseResult

class Backend(SQLBackend, HasCurrentCatalog, HasCurrentDatabase, NoExampleLoader):
    name: str
    compiler: Incomplete
    supports_create_or_replace: bool
    @property
    def version(self) -> str: ...
    @property
    def current_database(self) -> str: ...
    @property
    def current_catalog(self) -> str: ...
    con: Incomplete
    def do_connect(self, **kwargs: Any) -> None: ...
    @util.experimental
    @classmethod
    def from_connection(cls, con: pydruid.db.api.Connection, /) -> Backend: ...
    def get_schema(self, table_name: str, *, catalog: str | None = None, database: str | None = None) -> sch.Schema: ...
    def create_table(self, name: str, /, obj: pd.DataFrame | pa.Table | ir.Table | None = None, *, schema: sch.Schema | None = None, database: str | None = None, temp: bool = False, overwrite: bool = False) -> ir.Table: ...
    def drop_table(self, *args, **kwargs) -> None: ...
    def list_tables(self, *, like: str | None = None, database: str | None = None) -> list[str]: ...
