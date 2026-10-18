import warnings
warnings.simplefilter("always")
import ibis
t = ibis.memtable({"a": [1, 2]})
con = ibis.duckdb.connect()
print(con.create_table("x", t).execute())
print(con.sql("select 1 as a").execute())
import duckdb
print(duckdb.__version__)
r = duckdb.sql("select 1")
print(hasattr(r, "fetch_arrow_table"), hasattr(r, "to_arrow_table"))
