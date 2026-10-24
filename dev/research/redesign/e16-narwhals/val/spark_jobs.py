"""How many Spark jobs does ONE fused aggregate query cost?  uv run python val/spark_jobs.py"""
import sys
import warnings
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
warnings.filterwarnings("ignore")
import narwhals.stable.v2 as nw  # noqa: E402

from common import spark  # noqa: E402
from run_validation import make  # noqa: E402

s = spark("pyspark")
sc = s.sparkContext
sdf = s.createDataFrame(make(1_000_000, False).to_arrow()).cache()
sdf.count()
lf = nw.from_native(sdf)


def jobs(label, fn, conf=None):
    for k, v in (conf or {}).items():
        s.conf.set(k, v)
    g = f"g{label}"
    sc.setJobGroup(g, g)
    fn()
    print(f"{label:58s} jobs={len(sc.statusTracker().getJobIdsForGroup(g))}")
    for k in conf or {}:
        s.conf.unset(k)


m = lambda e: nw.when(e).then(nw.lit(1)).otherwise(nw.lit(0)).sum()  # noqa: E731
simple = [m(nw.col("amount") < 0).alias("a"), m(~nw.col("status").is_in(["pending", "shipped", "cancelled"])).alias("b"), m(nw.col("order_id").is_null()).alias("c")]
uniq = [(nw.len() - nw.col("order_id").n_unique()).alias("u")]
jobs("count() on cached df", lambda: sdf.count())
jobs("fused checks, no unique: narwhals collect()", lambda: lf.select(*simple).collect())
jobs("fused checks, no unique: native .collect() rows", lambda: nw.to_native(lf.select(*simple)).collect())
jobs("fused checks + unique (count distinct)", lambda: lf.select(*simple, *uniq).collect())
jobs("fused checks + unique, AQE off", lambda: lf.select(*simple, *uniq).collect(), {"spark.sql.adaptive.enabled": "false"})
jobs("checks one-per-query (3 queries, pandera-style)", lambda: [lf.select(e).collect() for e in simple])
