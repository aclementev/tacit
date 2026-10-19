from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

import ibis
import tacit_next as tc
from tacit_next import Column

HERE = Path(__file__).parent.parent


class Drivers(tc.Frame):
    driver_id: Column[int] = tc.field(unique=True, ge=1)
    name: Column[str]
    city: Column[str] = tc.field(isin=["Berlin", "Lisbon", "Madrid", "Paris"])
    vehicle_type: Column[str] = tc.field(isin=["economy", "comfort", "xl"])
    rating: Column[float | None] = tc.field(ge=1, le=5)
    joined_on: Column[date]


class Trips(tc.Frame):
    trip_id: Column[int] = tc.field(unique=True)
    driver_id: Column[int]
    requested_at: Column[datetime]
    completed_at: Column[datetime | None]
    status: Column[str] = tc.field(isin=["completed", "cancelled", "no_show"])
    distance_km: Column[float] = tc.field(ge=0)
    fare: Column[float] = tc.field(ge=0)
    tip: Column[float | None] = tc.field(ge=0)


class Derived(tc.Frame):
    duration_min: Column[float | None]
    total: Column[float]


class CompletedTrips(Trips, Derived):
    pass


@tc.step
def completed_trips(t: Trips) -> CompletedTrips:
    done = t.filter(t.status == "completed")
    duration = (done.completed_at.epoch_seconds() - done.requested_at.epoch_seconds()) / 60
    return CompletedTrips.extend(
        done,
        Derived(duration_min=duration, total=done.fare + done.tip.fill_null(0)),
    )


class CityVehicleStats(tc.Frame):
    city: Column[str]
    vehicle_type: Column[str]
    trip_count: Column[int]
    total_revenue: Column[float]
    avg_distance: Column[float]
    avg_rating_of_drivers: Column[float]
    distinct_drivers: Column[int]


@tc.step
def city_vehicle_stats(t: CompletedTrips, d: Drivers) -> CityVehicleStats:
    j = tc.join(t, d, on=lambda t, d: t.driver_id == d.driver_id)
    return CityVehicleStats.aggregate(by=[j.right.city, j.right.vehicle_type])(
        city=j.right.city,
        vehicle_type=j.right.vehicle_type,
        trip_count=j.left.trip_id.count(),
        total_revenue=j.left.total.sum(),
        avg_distance=j.left.distance_km.mean(),
        avg_rating_of_drivers=j.right.rating.mean(),
        distinct_drivers=j.left.driver_id.nunique(),
    )


def top_n_per_group[F: tc.Frame](
    df: F, group: Column[Any], order_by: Column[Any], n: int = 1
) -> F:
    rank = tc.row_number().over(group_by=group, order_by=order_by.desc())
    return df.filter(rank < n)


def main() -> None:
    con = ibis.duckdb.connect()
    drivers = Drivers.parse(con.read_csv(HERE / "drivers.csv"))
    trips = Trips.parse(con.read_csv(HERE / "trips.csv"))
    done = completed_trips(trips)
    stats = city_vehicle_stats(done, drivers)
    print(stats.order_by(stats.city, stats.vehicle_type).execute())
    best = top_n_per_group(done, done.driver_id, done.total, n=1)
    print(best.order_by(best.driver_id).execute().head())


if __name__ == "__main__":
    main()
