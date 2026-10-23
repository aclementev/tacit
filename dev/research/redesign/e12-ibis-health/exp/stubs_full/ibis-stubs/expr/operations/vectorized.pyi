import abc
import ibis.expr.datatypes as dt
from ibis.common.typing import VarTuple
from ibis.expr.operations.analytic import Analytic
from ibis.expr.operations.core import Column, Value
from ibis.expr.operations.reductions import Reduction
from types import FunctionType, LambdaType

__all__ = ['ElementWiseVectorizedUDF', 'ReductionVectorizedUDF', 'AnalyticVectorizedUDF']

class VectorizedUDF(Value, metaclass=abc.ABCMeta):
    func: FunctionType | LambdaType
    func_args: VarTuple[Column]
    input_type: VarTuple[dt.DataType]
    return_type: dt.DataType
    @property
    def dtype(self): ...

class ElementWiseVectorizedUDF(VectorizedUDF):
    shape = ...

class ReductionVectorizedUDF(VectorizedUDF, Reduction):
    shape = ...

class AnalyticVectorizedUDF(VectorizedUDF, Analytic):
    shape = ...
