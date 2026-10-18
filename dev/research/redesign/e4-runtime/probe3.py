from common import *
from ibisval import *
con, t = make_con(100_000, bad_rate=0.01)
log_reset(con)
r = validate(Customer, t, unique=["id"])
print(r)
print(len(log_queries(con)), "queries")
for q in log_queries(con): print(q[:600]); print()
con2, t2 = make_con(100_000)
log_reset(con2)
r = validate(Customer, t2, unique=["id"]); print(r, len(log_queries(con2)))
