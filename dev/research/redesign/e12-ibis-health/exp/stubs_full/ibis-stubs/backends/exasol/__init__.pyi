import contextlib
import ibis.expr.schema as sch
import ibis.expr.types as ir
import pandas as pd
import polars as pl
import pyarrow as pa
import pyexasol
from _typeshed import Incomplete
from collections.abc import Callable as Callable, Generator, Mapping
from ibis import util as util
from ibis.backends import BaseBackend as BaseBackend, CanCreateDatabase as CanCreateDatabase, NoExampleLoader as NoExampleLoader
from ibis.backends.sql import SQLBackend as SQLBackend
from ibis.backends.sql.compilers.base import C as C, STAR as STAR
from typing import Any
from urllib.parse import ParseResult as ParseResult

class Backend(SQLBackend, CanCreateDatabase, NoExampleLoader):
    name: str
    compiler: Incomplete
    supports_create_or_replace: bool
    supports_python_udfs: bool
    @property
    def version(self) -> str: ...
    con: Incomplete
    def do_connect(self, user: str, password: str, host: str = 'localhost', port: int = 8563, timezone: str = 'UTC', websocket_sslopt: Mapping[str, int] | None = None, **kwargs: Any) -> None: ...
    @util.experimental
    @classmethod
    def from_connection(cls, con: pyexasol.ExaConnection, /, *, timezone: str | None = None) -> Backend: ...
    @contextlib.contextmanager
    def begin(self) -> Generator[Incomplete]: ...
    def list_tables(self, *, like: str | None = None, database: str | tuple[str, str] | None = None) -> list[str]: ...
    def get_schema(self, table_name: str, *, catalog: str | None = None, database: str | None = None) -> sch.Schema: ...
    def create_table(self, name: str, /, obj: ir.Table | pd.DataFrame | pa.Table | pl.DataFrame | pl.LazyFrame | None = None, *, schema: sch.IntoSchema | None = None, database: str | None = None, overwrite: bool = False, temp: bool = False) -> ir.Table: ...
    @property
    def current_database(self) -> str: ...
    def drop_database(self, name: str, /, *, catalog: str | None = None, force: bool = False) -> None: ...
    def create_database(self, name: str, /, *, catalog: str | None = None, force: bool = False) -> None: ...
    def list_databases(self, *, like: str | None = None, catalog: str | None = None) -> list[str]: ...
