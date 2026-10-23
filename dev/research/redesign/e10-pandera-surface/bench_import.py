"""Q3 import cost: what a lazy pandera import saves, and what the hybrid still pays on first parse.

usage: uv run --frozen python bench_import.py
"""
import subprocess
import sys

PY = sys.executable
STMTS = [
    "import ibis",
    "import ibis, duckdb",
    "import tacit",
    "import pandera.ibis",
    "import ibis; import pandera.api.checks",
    "import ibis; import pandera.api.checks, pandera.api.ibis.types, pandera.config, pandera.errors",
    "import ibis; import pandera.ibis; import hybrid",
]


def wall(stmt, n=7):
    import time
    ts = []
    for _ in range(n):
        t0 = time.perf_counter()
        subprocess.run([PY, "-c", stmt], check=True, capture_output=True, cwd=".")
        ts.append(time.perf_counter() - t0)
    return min(ts), sorted(ts)[n // 2]


print("| statement | min wall (s) | median (s) | pandas loaded |\n|---|---|---|---|")
for s in STMTS:
    a, b = wall(s)
    pd = subprocess.run([PY, "-c", s + "; import sys; print('pandas' in sys.modules)"], capture_output=True, text=True).stdout.strip()
    print(f"| `{s}` | {a:.2f} | {b:.2f} | {pd} |")
