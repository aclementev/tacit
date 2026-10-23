"""Q2: run E4's ibisval predicates and E8's _check_expr over the Q4 builtin battery, vs pandera.

usage: uv run --frozen python cov_e4_e8.py
For each (dtype, builtin check, data with/without NULL): failing-row count per implementation.
pandera's count = len(failure_cases) of its SchemaError (CHECK_ERROR -> 'ERR').
"""
import sys
import warnings
from collections import Counter

sys.argv = [sys.argv[0], "duckdb"]
warnings.simplefilter("ignore")
sys.path.insert(0, "../e4-runtime")
sys.path.insert(0, "../e8-prototype/src")

import ibis  # noqa: E402
import pandas as pd  # noqa: E402

import pandera.errors as pe  # noqa: E402
import pandera.ibis as pa  # noqa: E402
from ibisval import BUILTIN  # noqa: E402
from tacit_next._validate import _check_expr  # noqa: E402

import parity as P  # noqa: E402  (re-uses the battery; its own run also executes on import)

E8_MAP = {  # pandera check name -> (E8 kind, value builder)
    "greater_than_or_equal_to": ("ge", lambda s: s["min_value"]),
    "greater_than": ("gt", lambda s: s["min_value"]),
    "less_than_or_equal_to": ("le", lambda s: s["max_value"]),
    "less_than": ("lt", lambda s: s["max_value"]),
    "in_range": ("between", lambda s: (s["min_value"], s["max_value"]) if s.get("include_min", True) and s.get("include_max", True) else None),
    "isin": ("isin", lambda s: list(s["allowed_values"])),
    "notin": ("notin", lambda s: list(s["forbidden_values"])),
    "str_matches": ("str_matches", lambda s: s["pattern"] if str(s["pattern"]).startswith("^") else "^" + str(s["pattern"])),
    "str_length": ("length", lambda s: (s.get("exact_value"), s.get("min_value"), s.get("max_value"))),
}


def pandera_count(ck, t):
    schema = pa.DataFrameSchema({"x": pa.Column(t.schema()["x"], checks=[ck], nullable=True)})
    try:
        schema.validate(t, lazy=True)
        return 0
    except pe.SchemaErrors as e:
        err = e.schema_errors[0]
        if err.reason_code.name == "CHECK_ERROR":
            return "ERR"
        return len(err.failure_cases) if isinstance(err.failure_cases, pd.DataFrame) else "FAIL(scalar)"


def e4_count(ck, t):
    fn = BUILTIN.get(ck.name)
    if fn is None or not ck.ignore_na:
        return "unsupported"
    try:
        return int((~fn(t.x, **ck.statistics)).cast("int64").sum().execute() or 0)
    except Exception:  # noqa: BLE001
        return "ERR"


def e8_count(ck, t):
    m = E8_MAP.get(ck.name)
    if m is None or not ck.ignore_na:
        return "unsupported"
    val = m[1](ck.statistics)
    if val is None:
        return "unsupported"
    try:
        return int(_check_expr(None, t.x, m[0], val).fill_null(False).cast("int64").sum().execute() or 0)
    except Exception:  # noqa: BLE001
        return "ERR"


rows = []
for dk in P.DTYPES:
    for with_null in (True, False):
        t = P.make_table(dk, with_null)
        for ck in P.builtin_checks(dk):
            p = pandera_count(ck, t)
            rows.append((dk, with_null, ck, p, e4_count(ck, t), e8_count(ck, t)))


def cls(impl, p):
    if impl == "unsupported":
        return "unsupported"
    if impl == p == "ERR":
        return "both-ERR"
    if impl == p or (p == "FAIL(scalar)" and impl not in (0, "ERR")):
        return "agree"
    return "DISAGREE"


total = len(rows)
print(f"### E4 ibisval / E8 _validate vs pandera on the builtin battery ({total} check x dtype x null cases)")
for name, idx in (("E4 ibisval", 4), ("E8 _validate", 5)):
    c = Counter(cls(r[idx], r[3]) for r in rows)
    print(f"{name}: {dict(c)}")
names = sorted({r[2].name for r in rows})
print("\nper builtin (E4 / E8 coverage of pandera's ibis builtins):")
for n in names:
    rs = [r for r in rows if r[2].name == n]
    e4 = Counter(cls(r[4], r[3]) for r in rs)
    e8 = Counter(cls(r[5], r[3]) for r in rs)
    print(f"  {n:<26} cases={len(rs):<3} E4={dict(e4)}  E8={dict(e8)}")
print("\nDISAGREEMENTS (dtype, null, check, pandera, E4, E8):")
for r in rows:
    if "DISAGREE" in (cls(r[4], r[3]), cls(r[5], r[3])):
        print(f"  {r[0]:<11} null={int(r[1])} {r[2].error:<60.60} pandera={r[3]!s:<6} E4={r[4]!s:<12} E8={r[5]}")
