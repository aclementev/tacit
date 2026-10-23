import ibis
t = ibis.table({"x": "int"})
reveal_type(t)
reveal_type(t.x)
reveal_type(t.filter(t.x > 1))
