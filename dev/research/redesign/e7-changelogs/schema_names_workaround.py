import ibis
s = ibis.schema({"a": "int64", "b": "string"})
a = set(s)              # Schema is a Mapping[str, DataType]
b = list(s.keys())
c = set(s.fields)       # alt
reveal_type(a); reveal_type(b)
