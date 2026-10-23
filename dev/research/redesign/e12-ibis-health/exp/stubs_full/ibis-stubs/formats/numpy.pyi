import ibis.expr.datatypes as dt
import ibis.expr.schema as sch
import numpy as np
from collections.abc import Iterable
from ibis.formats import SchemaMapper as SchemaMapper, TypeMapper as TypeMapper

class NumpyType(TypeMapper[np.dtype]):
    @classmethod
    def to_ibis(cls, typ: np.dtype, nullable: bool = True) -> dt.DataType: ...
    @classmethod
    def from_ibis(cls, dtype: dt.DataType) -> np.dtype: ...

class NumpySchema(SchemaMapper):
    @classmethod
    def from_ibis(cls, schema) -> list[tuple[str, np.dtype]]: ...
    @classmethod
    def to_ibis(cls, schema: Iterable[tuple[str, np.dtype]]) -> sch.Schema: ...
