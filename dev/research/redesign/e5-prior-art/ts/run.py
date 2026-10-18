from pyspark.sql import SparkSession
from pyspark.sql.types import LongType, StringType, DoubleType
from typedspark import Column, DataSet, DataSetImplements, Schema, transform_to_schema, create_partially_filled_dataset, create_schema

spark = SparkSession.builder.master("local[1]").config("spark.ui.enabled","false").getOrCreate()
spark.sparkContext.setLogLevel("ERROR")

class Raw(Schema):
    id: Column[LongType]
    amount: Column[DoubleType]
    status: Column[StringType]

class Enriched(Raw):
    amount_tax: Column[DoubleType]

df = spark.createDataFrame([(1, 2.0, "a")], "id long, amount double, status string")
ds = DataSet[Raw](df)           # runtime validation of columns/types
print(type(ds))
out = transform_to_schema(ds, Enriched, {Enriched.amount_tax: Raw.amount * 1.2})
out.show()
try:
    DataSet[Enriched](df)
except Exception as e:
    print("ERR", type(e).__name__, str(e)[:200])
try:
    Raw.amnt
except Exception as e:
    print("ERR typo", type(e).__name__, str(e)[:200])
print(ds.typedspark_schema)
gen = create_schema(df, "Gen")
print(gen[1] if isinstance(gen, tuple) else gen)
print(create_partially_filled_dataset(spark, Raw, {Raw.id: [1,2], Raw.amount: [1.0, 2.0]}).collect())
