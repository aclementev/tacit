import ibis
con = ibis.duckdb.connect()
con.raw_sql("CALL enable_logging('QueryLog')")
t = con.create_table("t", ibis.memtable({"a":[1,2,3]}))
print(t.a.sum().execute())
print(t.a.max().to_pyarrow())
print(con.raw_sql("select message from duckdb_logs where type='QueryLog'").fetchall())
