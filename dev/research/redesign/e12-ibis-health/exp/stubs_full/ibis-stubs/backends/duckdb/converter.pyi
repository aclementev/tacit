import ibis.expr.datatypes as dt
import pyarrow as pa
from ibis.formats.pandas import PandasData as PandasData
from ibis.formats.pyarrow import PyArrowData as PyArrowData

class DuckDBPandasData(PandasData):
    @staticmethod
    def convert_Array(s, dtype, pandas_type): ...

class DuckDBPyArrowData(PyArrowData):
    @classmethod
    def convert_scalar(cls, scalar: pa.Scalar, dtype: dt.DataType) -> pa.Scalar: ...
    @classmethod
    def convert_column(cls, column: pa.Array, dtype: dt.DataType) -> pa.Array: ...
