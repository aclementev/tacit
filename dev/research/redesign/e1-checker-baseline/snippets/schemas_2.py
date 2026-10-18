import ibis

table = ibis.memtable({
    "sepal_length": [5.1],
    "sepal_width": [3.5],
    "petal_length": [1.4],
    "petal_width": [0.2],
    "species": ["setosa"],
    "row_id": [1],  # not in the schema
})

Iris.cast(table)
# ValueError: Extra columns: ['row_id']
