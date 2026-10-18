import ibis
from ibis.expr.types import Table
from pandera.api.ibis.types import IbisData

from common import *
from tacit import Check
import pandera.backends.ibis.builtin_checks
con, t = make_con(1000)
for c in [Check.ge(0), Check.isin(["a"]), Check.str_length(2,2), Check.str_matches("x")]:
    print(c.name, c.statistics, c.ignore_na, c.element_wise)
col = "age"
c=Check.ge(0); out = c._check_fn(IbisData(t, col), **c._check_kwargs)
print(type(out)); 
v = out.op().values[col]
pred = v.to_expr()
print(pred.type(), pred.op().relations if hasattr(pred.op(),'relations') else '')
print(t.aggregate(bad=(~pred).sum()).execute())
print(ibis.to_sql(t.aggregate(bad=(~pred).sum())))
