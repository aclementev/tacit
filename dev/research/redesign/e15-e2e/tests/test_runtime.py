"""Runtime behaviour of tacit_t3 (the T3 prototype) and of examples/e2e.py."""

import pickle
import sys
from datetime import datetime
from pathlib import Path

import ibis
import ibis.expr.types as ir
import pandera.ibis as pa
import pytest

HERE = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(HERE / "src"), str(HERE / "examples")]

import tacit_t3 as tacit  # noqa: E402
from tacit_t3 import Column, DataFrame, field  # noqa: E402


class Trips(tacit.Schema):
    trip_id: Column[int] = field(unique=True)
    driver_id: Column[int]
    fare: Column[float] = field(ge=0)
    tip: Column[float | None]
    started_at: Column[datetime]
    ended_at: Column[datetime | None]
    city: Column[str] = field(checks=[pa.Check.str_length(2, 10)])


class Drivers(tacit.Schema):
    driver_id: Column[int]
    name: Column[str]


class Fare(tacit.Schema):
    driver_id: Column[int]
    name: Column[str]
    total: Column[float]


class Minutes(tacit.Schema):
    minutes: Column[int]


ROWS = [
    (1, 10, 12.5, None, datetime(2024, 1, 1, 8), datetime(2024, 1, 1, 8, 30), "Madrid"),
    (2, 10, 7.0, 1.0, datetime(2024, 1, 1, 9), None, "Madrid"),
    (3, 11, 20.0, 2.0, datetime(2024, 1, 2, 9), datetime(2024, 1, 2, 9, 45), "Paris"),
]


@pytest.fixture
def con():
    c = ibis.duckdb.connect()
    c.raw_sql("CALL enable_logging('QueryLog')")
    return c


def raw(con, rows=ROWS):
    cols = ["trip_id", "driver_id", "fare", "tip", "started_at", "ended_at", "city"]
    # unique names: create_table(overwrite=True) is broken on ibis 12 + sqlglot 30 (renders "DROP TABLE IF EXISTS")
    name = f"trips_src_{len(con.list_tables())}"
    return con.create_table(name, ibis.memtable([dict(zip(cols, r, strict=True)) for r in rows]))


def n_queries(con) -> int:
    rows = con.raw_sql("SELECT message FROM duckdb_logs WHERE type = 'QueryLog'").fetchall()
    return sum(1 for (m,) in rows if m.lstrip().startswith(("SELECT sum", "WITH", "SELECT count")))


def drivers(con) -> DataFrame[Drivers]:
    return Drivers.parse(ibis.memtable({"driver_id": [10, 11], "name": ["Ana", "Bo"]}))


def test_frame_is_ibis_table_and_pickles(con):
    t = Trips.parse(raw(con))
    assert isinstance(t, ir.Table) and type(t).__name__ == "DataFrame"
    assert t._schema is Trips and t.filter(t.c.fare > 1)._schema is Trips
    assert type(t.mutate(x=1)) is ir.Table
    back = pickle.loads(pickle.dumps(t))
    assert back._schema is Trips and back.columns == t.columns
    assert dir(t.c) == sorted(Trips.__tacit_fields__)


def test_parse_happy_path_is_one_query(con):
    src = raw(con)
    con.raw_sql("CALL truncate_duckdb_logs()")
    Trips.parse(src)
    assert n_queries(con) == 1


def test_parse_reports_every_issue_with_counts_and_samples(con):
    bad = raw(con, ROWS + [(3, 12, -1.0, None, datetime(2024, 1, 3), None, "X")])
    with pytest.raises(tacit.ValidationError) as ei:
        Trips.parse(bad)
    got = {(i.code, i.column): (i.count, i.samples) for i in ei.value.issues}
    assert got[("unique", "trip_id")] == (1, ("3",))
    assert got[("constraint", "fare")] == (1, ("-1.0",))
    assert got[("constraint", "city")][0] == 1  # pandera passthrough check, fused in the same query


def test_csv_coercion_and_materialisation(con, tmp_path):
    p = tmp_path / "t.csv"
    p.write_text("trip_id,driver_id,fare,tip,started_at,ended_at,city\n1,10,12.5,,2024-01-01 08:00,,Rome\n2,10,x,,2024-01-01 09:00,,Rome\n")
    with pytest.raises(tacit.ValidationError) as ei:
        Trips.parse(con.read_csv(p))
    assert [(i.code, i.samples) for i in ei.value.issues] == [("coercion", ("x",))]
    p.write_text("trip_id,driver_id,fare,tip,started_at,ended_at,city\n1,10,12.5,,2024-01-01 08:00,,Rome\n")
    t = Trips.parse(con.read_csv(p))
    assert "tacit_parsed_" in repr(t)  # the CSV is read once into a temp table


def test_join_scope_and_aggregate(con):
    t = Trips.parse(raw(con))
    j = tacit.join(t, drivers(con), on=lambda a, b: a.driver_id == b.driver_id)
    out = Fare.aggregate(by=[j.left.driver_id, j.right.name])(
        driver_id=j.left.driver_id, name=j.right.name, total=j.left.fare.sum()
    ).order_by(Fare.driver_id).execute()
    assert out.to_dict("list") == {"driver_id": [10, 11], "name": ["Ana", "Bo"], "total": [19.5, 20.0]}
    d = drivers(con)
    j2 = tacit.join(t, d, on=[(t.c.driver_id, d.c.driver_id)])
    with pytest.raises(tacit.ValidationError, match="not a column of the right frame"):
        tacit.join(t, d, on=[(t.c.driver_id, t.c.driver_id)])
    assert j2.left.trip_id is not None


def test_aggregate_rejects_forgotten_reduction(con):
    t = Trips.parse(raw(con))
    with pytest.raises(tacit.ValidationError, match="not a reduction"):
        Fare.aggregate(by=[t.c.driver_id])(driver_id=t.c.driver_id, name=t.c.city, total=t.c.fare.sum())
    with pytest.raises(tacit.ValidationError, match="use Fare.aggregate"):
        Fare.build(driver_id=t.c.driver_id, name=t.c.city, total=t.c.fare.sum())


def test_assume_not_null_is_checked_at_construction(con):
    t = Trips.parse(raw(con))
    with pytest.raises(tacit.ValidationError) as ei:
        Minutes.build(minutes=t.c.ended_at.assume_not_null().delta(t.c.started_at, unit="minute"))
    assert [(i.code, i.column, i.count) for i in ei.value.issues] == [("assumption", "ended_at", 1)]
    done = t.filter(t.c.ended_at.notnull())
    m = Minutes.build(minutes=done.c.ended_at.assume_not_null().delta(done.c.started_at, unit="minute"))
    assert sorted(m.execute()["minutes"]) == [30, 45]


def test_step_checks_frames_and_validates(con):
    @tacit.step(validate=True)
    def keep(df: DataFrame[Trips]) -> DataFrame[Trips]:
        return df

    @tacit.step
    def generic[S: tacit.Schema](df: DataFrame[S]) -> DataFrame[S]:
        return df

    t = Trips.parse(raw(con))
    assert keep(t) is t and generic(t) is t
    with pytest.raises(tacit.ValidationError, match=r"(?s)step .*keep\(\), argument 'df'.*expected DataFrame\[Trips\]; got DataFrame\[Drivers\]"):
        keep(drivers(con))  # type: ignore[arg-type]
    leaky = Trips.conform(t.mutate(fare=-t.c.fare))  # conform is structural only
    with pytest.raises(tacit.ValidationError, match="fare: constraint ge"):
        keep(leaky)


def test_typo_and_foreign_handles(con):
    t = Trips.parse(raw(con))
    with pytest.raises(AttributeError, match="Trips has no column 'fair'"):
        t.c.fair  # type: ignore[attr-defined]  # noqa: B018
    other = drivers(con)
    with pytest.raises(tacit.ValidationError, match="not derived from this DataFrame"):
        t.filter(other.c.driver_id > 1)


def test_e2e_runs(tmp_path):
    import e2e

    monthly, top = e2e.run(HERE / "examples" / "sources", tmp_path)
    assert (tmp_path / "monthly_revenue.parquet").exists() and (tmp_path / "top_customers.csv").exists()
    m = monthly.execute()
    assert len(m) == 30 and m["orders"].sum() == 851 - 0  # delivered orders that have a customer
    assert top.execute().groupby("country").size().max() == 3
