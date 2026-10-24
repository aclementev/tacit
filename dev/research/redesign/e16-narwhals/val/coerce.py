"""Q4 coercion: what does a narwhals `cast` do with unparseable values on each backend?
And does pandera's narwhals backend coerce at all?  usage: uv run python val/coerce.py <backend...>"""

from __future__ import annotations

import os
import sys
import warnings
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent)]
warnings.filterwarnings("ignore")

import narwhals.stable.v2 as nw  # noqa: E402
import polars as pl  # noqa: E402

from common import collect_polars, to_native  # noqa: E402

DF = pl.DataFrame({"s_int": ["1", "2", "x"], "s_float": ["1.5", "2", "y"], "s_date": ["2024-01-31", "2024-02-30", "z"], "i": [1, 300, -5]})
CASES = {
    "str->Int64 ('x')": nw.col("s_int").cast(nw.Int64),
    "str->Float64 ('y')": nw.col("s_float").cast(nw.Float64),
    "str->Date cast ('2024-02-30','z')": nw.col("s_date").cast(nw.Date),
    "str.to_date ('2024-02-30','z')": nw.col("s_date").str.to_date("%Y-%m-%d"),
    "Int64->Int8 overflow (300)": nw.col("i").cast(nw.Int8),
    "Int64->UInt8 negative (-5)": nw.col("i").cast(nw.UInt8),
}

if __name__ == "__main__":
    for b in sys.argv[1:]:
        lf = nw.from_native(to_native(b, "coerce", DF))
        print(f"== {b}")
        for name, e in CASES.items():
            try:
                v = collect_polars(lf.select(e.alias("v")))["v"].to_list()
                print(f"   {name:36s} -> {v}  ({'NULLS (silent)' if None in v else 'values'})")
            except Exception as ex:  # noqa: BLE001
                print(f"   {name:36s} -> RAISES {type(ex).__name__}: {str(ex).splitlines()[0][:90]}")
    if os.environ.get("PANDERA_USE_NARWHALS_BACKEND"):
        import pandera.polars as pa

        sch = pa.DataFrameSchema({"s_int": pa.Column(int, coerce=True)})
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            try:
                out = sch.validate(DF.select("s_int").head(2))
                print("pandera-narwhals coerce=True on polars ->", out.schema, [str(x.message)[:120] for x in w][:2])
            except Exception as ex:  # noqa: BLE001
                print("pandera-narwhals coerce=True on polars -> RAISES", type(ex).__name__, str(ex).splitlines()[0][:150])
