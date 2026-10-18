import sys, ibis
import pandera.ibis as pa
class M(pa.DataFrameModel):
    age: int          # bare annotation, no pa.Field()
t = ibis.memtable({"age": [1, 2]})
print(sys.version.split()[0], "columns detected:", list(M.to_schema().columns))
