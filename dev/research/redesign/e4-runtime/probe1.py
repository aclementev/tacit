from common import *
con, t = make_con(100_000)
print(t.schema())
log_reset(con)
df = Customer.parse(t)
qs = log_queries(con)
print(len(qs), "data queries; describes:", log_describe_count(con))
for q in qs: print("---", q[:300].replace("\n"," "))
