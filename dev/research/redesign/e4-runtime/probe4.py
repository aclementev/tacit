import traceback
from common import *
con, t = make_con(100000, bad_rate=0.001)
try:
    Customer.parse(t)
except Exception as e:
    traceback.print_exc()
con, t = make_con(100000)
try:
    Customer._pandera_schema().validate(t, lazy=True)
except Exception as e:
    print(str(e)[:1500])
