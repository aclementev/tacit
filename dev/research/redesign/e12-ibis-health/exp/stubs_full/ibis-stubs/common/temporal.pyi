from enum import Enum, EnumMeta
from ibis.common.bases import AbstractMeta
from ibis.common.dispatch import lazy_singledispatch
from ibis.common.patterns import Coercible

__all__ = ['DateUnit', 'TimeUnit', 'TimestampUnit', 'IntervalUnit']

class AbstractEnumMeta(EnumMeta, AbstractMeta): ...

class Unit(Coercible, Enum, metaclass=AbstractEnumMeta):
    @classmethod
    def __coerce__(cls, value): ...
    @classmethod
    def from_string(cls, value): ...
    @classmethod
    def aliases(cls): ...
    @property
    def singular(self) -> str: ...
    @property
    def plural(self) -> str: ...
    @property
    def short(self) -> str: ...

class TemporalUnit(Unit):
    @classmethod
    def aliases(cls): ...

class DateUnit(TemporalUnit):
    YEAR = 'Y'
    QUARTER = 'Q'
    MONTH = 'M'
    WEEK = 'W'
    DAY = 'D'

class TimeUnit(TemporalUnit):
    HOUR = 'h'
    MINUTE = 'm'
    SECOND = 's'
    MILLISECOND = 'ms'
    MICROSECOND = 'us'
    NANOSECOND = 'ns'

class TimestampUnit(TemporalUnit):
    SECOND = 's'
    MILLISECOND = 'ms'
    MICROSECOND = 'us'
    NANOSECOND = 'ns'
    @staticmethod
    def to_scale(unit: str) -> int: ...

class IntervalUnit(TemporalUnit):
    YEAR = 'Y'
    QUARTER = 'Q'
    MONTH = 'M'
    WEEK = 'W'
    DAY = 'D'
    HOUR = 'h'
    MINUTE = 'm'
    SECOND = 's'
    MILLISECOND = 'ms'
    MICROSECOND = 'us'
    NANOSECOND = 'ns'
    def is_date(self) -> bool: ...
    def is_time(self) -> bool: ...
