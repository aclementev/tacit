"""Q3: import-time. usage: uv run python bench_import.py"""
import subprocess, sys, time, re
PY = sys.executable
def wall(stmt, n=7):
    ts = []
    for _ in range(n):
        t0 = time.perf_counter(); subprocess.run([PY, "-c", stmt], check=True, capture_output=True); ts.append(time.perf_counter() - t0)
    return min(ts), sorted(ts)[len(ts)//2]
print("| statement | min wall (s) | median (s) |\n|---|---|---|")
for stmt in ["pass", "import ibis", "import pandera.ibis", "import ibis, pandera.ibis", "import tacit", "import tacit; tacit.Schema", ]:
    a, b = wall(stmt); print(f"| `{stmt}` | {a:.3f} | {b:.3f} |")
# top-level contributors (cumulative us), -X importtime
r = subprocess.run([PY, "-X", "importtime", "-c", "import tacit"], capture_output=True, text=True)
rows = []
for l in r.stderr.splitlines():
    m = re.match(r"import time:\s+(\d+) \|\s+(\d+) \| (\s*)(\S.*)", l)
    if m: rows.append((int(m[2]), len(m[3]) // 2, m[4]))
total = [c for c, d, n in rows if n == "tacit"][0]
print(f"\nimport tacit total (cumulative, -X importtime run): {total/1000:.0f} ms")
def top(depth, k, label):
    print(f"\n{label}")
    for c, d, n in sorted([x for x in rows if x[1] == depth], reverse=True)[:k]: print(f"  {c/1000:7.1f} ms  {n}")
top(1, 8, "direct children of tacit:")
top(2, 12, "second level (under tacit.* / ibis / pandera):")
named = {}
for c, d, n in rows:
    if n.split(".")[0] in ("pandas", "numpy", "pyarrow", "pydantic", "typeguard", "duckdb", "pandera", "ibis", "sqlglot", "rich", "polars") and "." not in n:
        named[n] = c
print("\nlibraries imported by `import tacit` (cumulative ms of the top-level module):")
for n, c in sorted(named.items(), key=lambda x: -x[1]): print(f"  {c/1000:7.1f} ms  {n}")
import subprocess as sp
mods = sp.run([PY, "-c", "import sys, tacit; m=sys.modules; print({k: (k in m) for k in ['pandas','numpy','pyarrow','duckdb','polars','pydantic','typeguard','narwhals','rich']}); print(len(m),'modules')"], capture_output=True, text=True).stdout
print("\nmodules loaded after `import tacit`:", mods)
