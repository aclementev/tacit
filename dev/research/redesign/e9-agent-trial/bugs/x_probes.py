"""Extra probes, not part of the required a-f set."""
from __future__ import annotations

from pathlib import Path

import ibis
import tacit_next as tc
from tacit_next import Column

HERE = Path(__file__).parent.parent


class Drivers(tc.Frame):
    driver_id: Column[int]
    rating: Column[float | None]


class Other(tc.Frame):
    x: Column[int]


def needs_nonnull(c: Column[float]) -> Column[float]:
    return c * 2


def plain_step(o: Other) -> Other:  # no @tc.step
    return o.filter(o.x > 0)


class AvgRating(tc.Frame):
    avg_rating: Column[float]  # non-null, but a group can be all-null


def avg_rating(d: Drivers) -> AvgRating:
    return AvgRating.aggregate(by=[])(avg_rating=d.rating.mean())


con = ibis.duckdb.connect()
drivers = Drivers.parse(con.read_csv(HERE / "drivers.csv"))
print(avg_rating(drivers).execute())  # P3 mean over nullable declared non-null
