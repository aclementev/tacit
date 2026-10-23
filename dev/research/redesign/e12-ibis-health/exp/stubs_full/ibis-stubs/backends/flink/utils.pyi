import abc
import ibis.expr.operations as ops
from _typeshed import Incomplete
from abc import ABC, abstractmethod
from ibis.backends.flink.datatypes import FlinkType as FlinkType
from ibis.common.temporal import IntervalUnit as IntervalUnit, normalize_timezone as normalize_timezone
from ibis.util import convert_unit as convert_unit

MIN_ALLOWED_PRECISION: Incomplete
MAX_ALLOWED_PRECISION: Incomplete
MICROSECONDS_IN_UNIT: Incomplete

def format_precision(precision: int, unit: IntervalUnit) -> str: ...

class FlinkIntervalType(ABC, metaclass=abc.ABCMeta):
    value: Incomplete
    unit: Incomplete
    interval_segments: Incomplete
    precisions: Incomplete
    def __init__(self, value: int, unit: str) -> None: ...
    @classmethod
    @property
    @abstractmethod
    def units(self): ...
    @classmethod
    @property
    @abstractmethod
    def factors(self): ...
    @abstractmethod
    def format_as_string(self, interval_segments: dict, precisions: dict) -> str: ...

class YearsToMonthsInterval(FlinkIntervalType):
    units: Incomplete
    factors: Incomplete
    def format_as_string(self) -> str: ...

class DaysToSecondsInterval(FlinkIntervalType):
    units: Incomplete
    factors: Incomplete
    def format_as_string(self) -> str: ...

def translate_literal(op: ops.Literal) -> str: ...
