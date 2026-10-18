import cProfile, pstats, warnings
from common import *
warnings.filterwarnings("ignore")
con, t = make_con(1000)
Customer.parse(t)
pr = cProfile.Profile(); pr.enable()
for _ in range(5): Customer.parse(t)
pr.disable()
st = pstats.Stats(pr); st.sort_stats("cumulative")
import io; s = io.StringIO(); st.stream = s; st.print_stats(45); 
out = s.getvalue().splitlines()
import re; print("\n".join(re.sub(r"/home/\S*?(site-packages|lib/python3.13)/", "", l)[:150] for l in out[:60]))
