iris = Iris.parse(table)          # DataFrame[Iris]
result = iris.mutate(x=iris.sepal_length * 2)  # ir.Table — no longer typed
