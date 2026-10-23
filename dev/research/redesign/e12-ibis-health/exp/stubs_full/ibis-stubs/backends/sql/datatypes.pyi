import ibis.expr.datatypes as dt
import sqlglot as sg
import sqlglot.expressions as sge
from _typeshed import Incomplete
from ibis.common.collections import FrozenDict as FrozenDict
from ibis.formats import TypeMapper as TypeMapper
from ibis.util import get_subclasses as get_subclasses

typecode: Incomplete

class SqlglotType(TypeMapper):
    dialect: str | None
    default_nullable: bool
    default_decimal_precision: int | None
    default_decimal_scale: int | None
    default_temporal_scale: int | None
    default_interval_precision: str | None
    unknown_type_strings: dict[str, dt.DataType]
    @classmethod
    def to_ibis(cls, typ: sge.DataType, nullable: bool | None = None) -> dt.DataType: ...
    @classmethod
    def from_ibis(cls, dtype: dt.DataType) -> sge.DataType: ...
    @classmethod
    def from_string(cls, text: str, nullable: bool | None = None) -> dt.DataType: ...
    @classmethod
    def to_string(cls, dtype: dt.DataType) -> str: ...

class PostgresType(SqlglotType):
    dialect: str
    default_interval_precision: str
    default_temporal_scale: int
    unknown_type_strings: Incomplete
    @classmethod
    def from_string(cls, text: str, nullable: bool | None = None) -> dt.DataType: ...

class RisingWaveType(PostgresType):
    dialect: str

class DataFusionType(PostgresType):
    dialect: str
    unknown_type_strings: Incomplete

class MaterializeType(PostgresType):
    dialect: str
    @classmethod
    def from_string(cls, text: str, nullable: bool | None = None) -> dt.DataType: ...

class MySQLType(SqlglotType):
    dialect: str
    default_decimal_precision: int
    default_decimal_scale: int
    unknown_type_strings: Incomplete

class DuckDBType(SqlglotType):
    dialect: str
    default_decimal_precision: int
    default_decimal_scale: int
    default_interval_precision: str
    unknown_type_strings: Incomplete

class TrinoType(SqlglotType):
    dialect: str
    default_decimal_precision: int
    default_decimal_scale: int
    default_temporal_scale: int
    unknown_type_strings: Incomplete

class DruidType(SqlglotType):
    dialect: str
    unknown_type_strings: Incomplete

class OracleType(SqlglotType):
    dialect: str
    default_decimal_precision: int
    default_decimal_scale: int
    default_temporal_scale: int
    unknown_type_strings: Incomplete

class SnowflakeType(SqlglotType):
    dialect: str
    default_decimal_precision: int
    default_decimal_scale: int
    default_temporal_scale: int

class SQLiteType(SqlglotType):
    dialect: str

class ImpalaType(SqlglotType):
    dialect: str
    default_decimal_precision: int
    default_decimal_scale: int

class PySparkType(SqlglotType):
    dialect: str
    default_decimal_precision: int
    default_decimal_scale: int

class BigQueryType(SqlglotType):
    dialect: str
    default_decimal_precision: int
    default_decimal_scale: int

class BigQueryUDFType(BigQueryType): ...

class ExasolType(SqlglotType):
    dialect: str
    default_temporal_scale: int
    default_decimal_precision: int
    default_decimal_scale: int

class MSSQLType(SqlglotType):
    dialect: str
    unknown_type_strings: Incomplete

class ClickHouseType(SqlglotType):
    dialect: str
    default_decimal_precision: Incomplete
    default_decimal_scale: Incomplete
    default_nullable: bool
    unknown_type_strings: Incomplete
    @classmethod
    def from_ibis(cls, dtype: dt.DataType) -> sge.DataType: ...

class FlinkType(SqlglotType):
    dialect: str
    default_decimal_precision: int
    default_decimal_scale: int

class DatabricksType(SqlglotType):
    dialect: str

class AthenaType(SqlglotType):
    dialect: str

class SingleStoreDBType(MySQLType):
    dialect: str
    @classmethod
    def to_ibis(cls, typ, nullable: bool = True): ...
    @classmethod
    def from_ibis(cls, dtype): ...
    @classmethod
    def from_string(cls, type_string, nullable: bool = True): ...

def get_type_mapper(dialect: str | sg.Dialect, /) -> type[SqlglotType]: ...
