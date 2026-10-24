# ruff: noqa: B015, B018
"""T3 additions: derived facade nullability, join scope, aggregate(by=), @step, assume_not_null,
durations, pandera passthrough checks."""

from datetime import date, datetime
from typing import Any, reveal_type

import ibis.expr.types as ir
import pandera.ibis as pa

import tacit_t3 as tacit
from tacit_t3 import Column, DataFrame, field


class Trips(tacit.Schema):
    trip_id: Column[int] = field(unique=True)
    driver_id: Column[int]
    fare: Column[float] = field(ge=0)
    tip: Column[float | None]
    started_at: Column[datetime]
    ended_at: Column[datetime | None]
    city: Column[str] = field(checks=[pa.Check.str_length(2, 40)])


class Drivers(tacit.Schema):
    driver_id: Column[int]
    name: Column[str]
    rating: Column[float | None]


class TripDriver(tacit.Schema):
    trip_id: Column[int]
    name: Column[str]
    fare: Column[float]


class CityStats(tacit.Schema):
    city: Column[str]
    trips: Column[int]
    revenue: Column[float]


class Minutes(tacit.Schema):
    minutes: Column[int]


class Day(tacit.Schema):
    day: Column[date]


def nullability(t: DataFrame[Trips]) -> None:
    # @feature derived facade: nullability propagates through comparisons and reductions
    reveal_type(t.c.tip > 0)  # R: Column[bool | None]
    reveal_type(t.c.fare > 0)  # R: Column[bool]
    reveal_type(t.c.tip.sum())  # R: Scalar[float | None]
    reveal_type(t.c.fare.mean())  # R: Scalar[float]
    reveal_type(t.filter(t.c.tip > 0))  # R: DataFrame[Trips]
    reveal_type(t.c.tip.fill_null(0))  # R: Column[float]
    reveal_type(t.c.fare.log())  # R: Column[float]
    reveal_type(t.c.fare.sum(where=t.c.tip > 1))  # R: Scalar[float | None]
    reveal_type(t.c.city.split(","))  # R: ArrayColumn
    t.c.city.mean()  # E: no mean on str
    reveal_type(tacit.cases((t.c.tip > 5, "big"), else_="small"))  # R: Column[str]
    # @feature assume_not_null and durations
    reveal_type(t.c.ended_at.assume_not_null())  # R: Column[datetime]
    reveal_type(t.c.tip.sum().assume_not_null())  # R: Scalar[float]
    reveal_type(t.c.ended_at.delta(t.c.started_at, unit="minute"))  # R: Column[int | None]
    reveal_type(t.c.ended_at.assume_not_null().delta(t.c.started_at, unit="minute"))  # R: Column[int]
    reveal_type(t.c.started_at.epoch_seconds())  # R: Column[int]
    Minutes.build(minutes=t.c.ended_at.delta(t.c.started_at, unit="minute"))  # E: nullable into int
    Minutes.build(minutes=t.c.ended_at.assume_not_null().delta(t.c.started_at, unit="minute"))
    reveal_type(t.c.started_at.date())  # R: Column[date]
    Day.build(day=t.c.started_at)  # E: datetime into date (known hole: datetime subclasses date; runtime dtype check catches it)


def joins(t: DataFrame[Trips], d: DataFrame[Drivers]) -> None:
    # @feature typed join scope
    j = tacit.join(t, d, on=lambda a, b: a.driver_id == b.driver_id)
    reveal_type(j)  # R: Join[Trips, Drivers]
    reveal_type(j.left.fare)  # R: Column[float]
    reveal_type(j.right.rating)  # R: Column[float | None]
    j.right.fare  # E: Drivers has no fare
    tacit.join(t, d, on=lambda a, b: a.driver_idd == b.driver_id)  # E: typo in predicate
    tacit.join(t, d, on=lambda a, b: a.tip > b.rating)  # nullable predicate is fine
    tacit.join(t, d, on=lambda a, b: a.driver_id == b.name)  # E: int == str key
    tacit.join(t, d, on=[(t.c.driver_id, d.c.driver_id)], how="left")
    reveal_type(TripDriver.build(trip_id=j.left.trip_id, name=j.right.name, fare=j.left.fare))  # R: DataFrame[TripDriver]
    TripDriver.build(trip_id=j.left.trip_id, name=j.right.name, fare=j.left.tip)  # E: nullable fare
    TripDriver.build(trip_id=j.left.trip_id, name=j.left.city)  # E: missing fare
    tacit.join(t, t.mutate(x=1), on=lambda a, b: a.trip_id == b.trip_id)  # E: right is not a frame


def aggregation(t: DataFrame[Trips]) -> None:
    # @feature explicit aggregate(by=)
    agg = CityStats.aggregate(by=[t.c.city])
    reveal_type(agg(city=t.c.city, trips=t.c.trip_id.count(), revenue=t.c.fare.sum()))  # R: DataFrame[CityStats]
    agg(city=t.c.city, trips=t.c.fare.sum(), revenue=t.c.fare.sum())  # E: float into int
    agg(city=t.c.city, trips=t.c.trip_id.count(), revenue=t.c.tip.sum())  # E: nullable reduction
    agg(city=t.c.city, trips=t.c.trip_id.count())  # E: missing revenue
    CityStats.aggregate(by=t.c.city)  # E: by must be a sequence
    CityStats.aggregate(by=[t.c.city])(city=t.c.city, trips=t.c.trip_id.count(), revenue=t.c.tip.sum().fill_null(0))


@tacit.step
def clean(t: DataFrame[Trips]) -> DataFrame[Trips]:
    return t.filter(t.c.fare > 0)


@tacit.step(validate=True)
def ingest(raw: ir.Table) -> DataFrame[Trips]:
    return Trips.parse(raw)


def steps(t: DataFrame[Trips], d: DataFrame[Drivers], raw: ir.Table) -> None:
    # @feature @step preserves signatures
    reveal_type(clean(t))  # R: DataFrame[Trips]
    clean(d)  # E: wrong frame through @step
    reveal_type(ingest(raw))  # R: DataFrame[Trips]
    ingest(t.c)  # E: not a table


def generic_handles[S: tacit.Schema](df: DataFrame[S], key: Column[Any], ts: Column[datetime]) -> DataFrame[S]:
    return df.filter(tacit.row_number().over(group_by=key, order_by=ts.desc()) == 0)


def generic(t: DataFrame[Trips]) -> None:
    # @feature generic steps
    reveal_type(generic_handles(t, t.c.trip_id, t.c.started_at))  # R: DataFrame[Trips]
    generic_handles(t, t.c.trip_id, t.c.ended_at)  # E: nullable ts handle
    generic_handles(t, t.c.trip_id, t.c.fare)  # E: float handle for datetime
    reveal_type(t.c.started_at >= datetime(2024, 1, 1))  # R: Column[bool]
    reveal_type(t.c.started_at.date() < date(2024, 1, 1))  # R: Column[bool]
