import sqlglot.expressions as sge
from _typeshed import Incomplete
from sqlglot.dialects import ClickHouse as _ClickHouse, Hive, Postgres, Spark, TSQL

class ClickHouse(_ClickHouse):
    class Generator(_ClickHouse.Generator):
        def except_op(self, expression: sge.Except) -> str: ...
        def intersect_op(self, expression: sge.Intersect) -> str: ...

class DataFusion(Postgres):
    class Generator(Postgres.Generator):
        TRANSFORMS: Incomplete

class Druid(Postgres):
    class Generator(Postgres.Generator):
        TRANSFORMS: Incomplete

class Exasol(Postgres):
    class Generator(Postgres.Generator):
        TRANSFORMS: Incomplete
        TYPE_MAPPING: Incomplete

class Flink(Hive):
    UNESCAPED_SEQUENCES: Incomplete
    REGEXP_EXTRACT_DEFAULT_GROUP: int
    class Generator(Hive.Generator):
        WITH_PROPERTIES_PREFIX: str
        UNNEST_WITH_ORDINALITY: bool
        TYPE_MAPPING: Incomplete
        TRANSFORMS: Incomplete
        def columndef_sql(self, expression: sge.ColumnDef, sep: str = ' ') -> str: ...
        def unnest_sql(self, expression: sge.Unnest) -> str: ...
        def struct_sql(self, expression: sge.Struct) -> str: ...
        def array_sql(self, expression: sge.Array) -> str: ...
    class Tokenizer(Hive.Tokenizer):
        STRING_ESCAPES: Incomplete

def tablesample_percent_to_int(self, expr): ...

class Impala(Hive):
    NULL_ORDERING: str
    REGEXP_EXTRACT_DEFAULT_GROUP: int
    TABLESAMPLE_SIZE_IS_PERCENT: bool
    ALIAS_POST_TABLESAMPLE: bool
    class Generator(Hive.Generator):
        TABLESAMPLE_WITH_METHOD: bool
        TRANSFORMS: Incomplete

class MSSQL(TSQL):
    class Generator(TSQL.Generator):
        TRANSFORMS: Incomplete

class Polars(Postgres): ...
class PySpark(Spark): ...

class RisingWave(Postgres):
    class Generator(Postgres.Generator):
        SINGLE_STRING_INTERVAL: bool
        RENAME_TABLE_WITH_DB: bool
        LOCKING_READS_SUPPORTED: bool
        JOIN_HINTS: bool
        TABLE_HINTS: bool
        QUERY_HINTS: bool
        NVL2_SUPPORTED: bool
        PARAMETER_TOKEN: str
        TABLESAMPLE_SIZE_IS_ROWS: bool
        TABLESAMPLE_SEED_KEYWORD: str
        SUPPORTS_SELECT_INTO: bool
        JSON_TYPE_REQUIRED_FOR_EXTRACTION: bool
        SUPPORTS_UNLOGGED_TABLES: bool
        TYPE_MAPPING: Incomplete
        STRUCT_DELIMITER: Incomplete
        def datatype_sql(self, expression: sge.DataType) -> str: ...
