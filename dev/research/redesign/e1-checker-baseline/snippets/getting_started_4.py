con = ibis.duckdb.connect()
raw = con.read_csv("iris.csv")

iris = Iris.parse(raw)
