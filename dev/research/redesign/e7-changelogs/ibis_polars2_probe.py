import ibis, polars as pl
print("polars", pl.__version__, "ibis", ibis.__version__)
con = ibis.polars.connect()
df = pl.DataFrame({"a": [1, 2, 3], "s": ["2020-01-01", "2020-01-02", "2020-01-03"], "t": ["01:02:03"]*3})
t = con.create_table("x", df)
def tryit(label, fn):
    try: print(label, "OK", fn())
    except Exception as e: print(label, "FAIL", type(e).__name__, str(e)[:160].replace("\n", " "))
tryit("execute", lambda: t.a.sum().execute())
tryit("cast str->date", lambda: t.mutate(d=t.s.cast("date")).execute()["d"].to_list())
tryit("cast str->time", lambda: t.mutate(d=t.t.cast("time")).execute()["d"].to_list())
tryit("as_timestamp", lambda: t.mutate(d=t.s.as_timestamp("%Y-%m-%d")).execute()["d"].to_list())
tryit("group_by", lambda: t.group_by("s").agg(n=t.a.sum()).execute().shape)
tryit("memtable via polars", lambda: ibis.memtable(df).execute().shape)
