import ibis.expr.datatypes as dt
import ibis.expr.schema as sch
from ibis.formats import SchemaMapper as SchemaMapper, TypeMapper as TypeMapper
from pyflink.table import TableSchema as TableSchema
from pyflink.table.types import DataType, RowType

class FlinkRowSchema(SchemaMapper):
    @classmethod
    def from_ibis(cls, schema: sch.Schema | None) -> list[RowType]: ...

class FlinkType(TypeMapper):
    @classmethod
    def to_ibis(cls, typ: DataType) -> dt.DataType: ...
    @classmethod
    def from_ibis(cls, dtype: dt.DataType) -> DataType: ...
    @classmethod
    def to_string(cls, dtype: dt.DataType) -> str: ...

def get_field_data_types(pyflink_schema: TableSchema) -> list[DataType]: ...
