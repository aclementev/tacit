import pandera.ibis as pa
from pandera.ibis import Check, Column, DataFrameSchema

c = Check.ge(0)
col = Column("int64")
s = DataFrameSchema({})
