import ibis.expr.datatypes as dt
from ibis.common.annotations import attribute
from ibis.common.temporal import DateUnit, IntervalUnit, TimeUnit, TimestampUnit
from ibis.expr.operations.core import Binary, Scalar, Unary, Value
from ibis.expr.operations.logical import Between

__all__ = ['TimestampTruncate', 'DateTruncate', 'TimeTruncate', 'TimestampBucket', 'Strftime', 'StringToTimestamp', 'StringToDate', 'StringToTime', 'ExtractTemporalField', 'ExtractDateField', 'ExtractTimeField', 'ExtractYear', 'ExtractIsoYear', 'ExtractMonth', 'ExtractDay', 'ExtractDayOfYear', 'ExtractQuarter', 'ExtractEpochSeconds', 'ExtractWeekOfYear', 'ExtractHour', 'ExtractMinute', 'ExtractSecond', 'ExtractMillisecond', 'ExtractMicrosecond', 'DayOfWeekIndex', 'DayOfWeekName', 'Time', 'Date', 'DateFromYMD', 'TimeFromHMS', 'TimestampFromYMDHMS', 'TimestampFromUNIX', 'DateAdd', 'DateSub', 'DateDiff', 'TimeAdd', 'TimeSub', 'TimeDiff', 'TimestampAdd', 'TimestampSub', 'TimestampDiff', 'IntervalBinary', 'IntervalAdd', 'IntervalSubtract', 'IntervalMultiply', 'IntervalFloorDivide', 'IntervalFromInteger', 'BetweenTime', 'TimeDelta', 'DateDelta', 'TimestampDelta', 'ExtractTimestampField']

class TimestampTruncate(Value):
    arg: Value[dt.Timestamp]
    unit: IntervalUnit
    shape = ...
    dtype = ...

class DateTruncate(Value):
    arg: Value[dt.Date]
    unit: DateUnit
    shape = ...
    dtype = ...

class TimeTruncate(Value):
    arg: Value[dt.Time]
    unit: TimeUnit
    shape = ...
    dtype = ...

class TimestampBucket(Value):
    arg: Value[dt.Timestamp]
    interval: Scalar[dt.Interval]
    offset: Scalar[dt.Interval] | None = ...
    shape = ...
    dtype = ...

class Strftime(Value):
    arg: Value[dt.Temporal]
    format_str: Value[dt.String]
    shape = ...
    dtype = ...

class StringToTimestamp(Value):
    arg: Value[dt.String]
    format_str: Value[dt.String]
    shape = ...
    dtype = ...

class StringToDate(Value):
    arg: Value[dt.String]
    format_str: Value[dt.String]
    shape = ...
    dtype = ...

class StringToTime(Value):
    arg: Value[dt.String]
    format_str: Value[dt.String]
    shape = ...
    dtype = ...

class ExtractTemporalField(Unary):
    arg: Value[dt.Temporal]
    dtype = ...

class ExtractDateField(ExtractTemporalField):
    arg: Value[dt.Date | dt.Timestamp]

class ExtractTimeField(ExtractTemporalField):
    arg: Value[dt.Time | dt.Timestamp]

class ExtractYear(ExtractDateField): ...
class ExtractIsoYear(ExtractDateField): ...
class ExtractMonth(ExtractDateField): ...
class ExtractDay(ExtractDateField): ...
class ExtractDayOfYear(ExtractDateField): ...
class ExtractQuarter(ExtractDateField): ...
class ExtractEpochSeconds(ExtractDateField): ...
class ExtractWeekOfYear(ExtractDateField): ...
class ExtractHour(ExtractTimeField): ...
class ExtractMinute(ExtractTimeField): ...
class ExtractSecond(ExtractTimeField): ...
class ExtractMillisecond(ExtractTimeField): ...
class ExtractMicrosecond(ExtractTimeField): ...

class DayOfWeekIndex(Unary):
    arg: Value[dt.Date | dt.Timestamp]
    dtype = ...

class DayOfWeekName(Unary):
    arg: Value[dt.Date | dt.Timestamp]
    dtype = ...

class Time(Unary):
    dtype = ...

class Date(Unary):
    dtype = ...

class DateFromYMD(Value):
    year: Value[dt.Integer]
    month: Value[dt.Integer]
    day: Value[dt.Integer]
    dtype = ...
    shape = ...

class TimeFromHMS(Value):
    hours: Value[dt.Integer]
    minutes: Value[dt.Integer]
    seconds: Value[dt.Integer]
    dtype = ...
    shape = ...

class TimestampFromYMDHMS(Value):
    year: Value[dt.Integer]
    month: Value[dt.Integer]
    day: Value[dt.Integer]
    hours: Value[dt.Integer]
    minutes: Value[dt.Integer]
    seconds: Value[dt.Integer]
    dtype = ...
    shape = ...

class TimestampFromUNIX(Value):
    arg: Value
    unit: TimestampUnit
    dtype = ...
    shape = ...

class DateAdd(Binary):
    left: Value[dt.Date]
    right: Value[DateInterval]
    dtype = ...

class DateSub(Binary):
    left: Value[dt.Date]
    right: Value[DateInterval]
    dtype = ...

class DateDiff(Binary):
    left: Value[dt.Date]
    right: Value[dt.Date]
    dtype = ...

class TimeAdd(Binary):
    left: Value[dt.Time]
    right: Value[TimeInterval]
    dtype = ...

class TimeSub(Binary):
    left: Value[dt.Time]
    right: Value[TimeInterval]
    dtype = ...

class TimeDiff(Binary):
    left: Value[dt.Time]
    right: Value[dt.Time]
    dtype = ...

class TimestampAdd(Binary):
    left: Value[dt.Timestamp]
    right: Value[dt.Interval]
    dtype = ...

class TimestampSub(Binary):
    left: Value[dt.Timestamp]
    right: Value[dt.Interval]
    dtype = ...

class TimestampDiff(Binary):
    left: Value[dt.Timestamp]
    right: Value[dt.Timestamp]
    dtype = ...

class IntervalBinary(Binary):
    @attribute
    def dtype(self): ...

class IntervalAdd(IntervalBinary):
    left: Value[dt.Interval]
    right: Value[dt.Interval]
    op = ...

class IntervalSubtract(IntervalBinary):
    left: Value[dt.Interval]
    right: Value[dt.Interval]
    op = ...

class IntervalMultiply(IntervalBinary):
    left: Value[dt.Interval]
    right: Value[dt.Numeric | dt.Boolean]
    op = ...

class IntervalFloorDivide(IntervalBinary):
    left: Value[dt.Interval]
    right: Value[dt.Numeric | dt.Boolean]
    op = ...

class IntervalFromInteger(Value):
    arg: Value[dt.Integer]
    unit: IntervalUnit
    shape = ...
    @attribute
    def dtype(self): ...
    @property
    def resolution(self): ...

class BetweenTime(Between):
    arg: Value[dt.Time | dt.Timestamp]
    lower_bound: Value[dt.Time | dt.String]
    upper_bound: Value[dt.Time | dt.String]

class TemporalDelta(Value):
    part: Value[dt.String]
    shape = ...
    dtype = ...

class TimeDelta(TemporalDelta):
    left: Value[dt.Time]
    right: Value[dt.Time]

class DateDelta(TemporalDelta):
    left: Value[dt.Date]
    right: Value[dt.Date]

class TimestampDelta(TemporalDelta):
    left: Value[dt.Timestamp]
    right: Value[dt.Timestamp]

# Names in __all__ with no definition:
#   ExtractTimestampField
