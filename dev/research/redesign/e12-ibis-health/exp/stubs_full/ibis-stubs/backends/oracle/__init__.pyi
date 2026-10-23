import contextlib
import ibis.expr.datatypes as dt
import ibis.expr.schema as sch
import ibis.expr.types as ir
import oracledb
import pandas as pd
import polars as pl
import pyarrow as pa
import sqlglot as sg
from _typeshed import Incomplete
from collections.abc import Callable as Callable, Generator
from functools import cached_property as cached_property
from ibis import util as util
from ibis.backends import CanListDatabase as CanListDatabase, HasCurrentCatalog as HasCurrentCatalog, HasCurrentDatabase as HasCurrentDatabase, PyArrowExampleLoader as PyArrowExampleLoader
from ibis.backends.sql import SQLBackend as SQLBackend
from ibis.backends.sql.compilers.base import C as C, STAR as STAR
from typing import Any
from urllib.parse import ParseResult as ParseResult

def metadata_row_to_type(*, type_mapper, type_string, precision, scale, nullable) -> dt.DataType: ...

class Backend(SQLBackend, CanListDatabase, HasCurrentDatabase, HasCurrentCatalog, PyArrowExampleLoader):
    name: str
    compiler: Incomplete
    supports_temporary_tables: bool
    @cached_property
    def version(self): ...
    con: Incomplete
    def do_connect(self, *, user: str, password: str, host: str = 'localhost', port: int = 1521, database: str | None = None, sid: str | None = None, service_name: str | None = None, dsn: str | None = None, **_: Any) -> None: ...
    @util.experimental
    @classmethod
    def from_connection(cls, con: oracledb.Connection, /) -> Backend: ...
    @property
    def current_catalog(self) -> str: ...
    @property
    def current_database(self) -> str: ...
    @contextlib.contextmanager
    def begin(self) -> Generator[Incomplete]: ...
    def raw_sql(self, query: str | sg.Expression, **kwargs: Any) -> Any: ...
    def list_tables(self, *, like: str | None = None, database: tuple[str, str] | str | None = None) -> list[str]: ...
    def list_databases(self, *, like: str | None = None, catalog: str | None = None) -> list[str]: ...
    def get_schema(self, name: str, *, catalog: str | None = None, database: str | None = None) -> sch.Schema: ...
    def create_table(self, name: str, /, obj: ir.Table | pd.DataFrame | pa.Table | pl.DataFrame | pl.LazyFrame | None = None, *, schema: sch.IntoSchema | None = None, database: str | None = None, temp: bool = False, overwrite: bool = False): ...
    def drop_table(self, name: str, /, *, database: tuple[str, str] | str | None = None, force: bool = False) -> None: ...
