"""Re-inject E6's five bug classes into the tacit-next pipeline; record static + runtime detection.

Writes bugs/<id>.py (one textual mutation of pipeline.py each), runs pyright, mypy,
ty and pyrefly on every variant (the unmutated pipeline is clean on all four, so any
diagnostic is a detection), then runs main() and records the exception.
Bad-CSV variants (bug e) run the unmodified pipeline on e6-agent-trial/bad/*.csv.

Run from dev/research/redesign:  uv run --frozen python e8-prototype/examples/ecommerce/inject_bugs.py
Output: e8-prototype/out/bugs/{matrix.txt,<id>.<checker>.txt}
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTO = HERE.parents[1]
ROOT = PROTO.parent
OUT = PROTO / "out" / "bugs"
SRC = (HERE / "pipeline.py").read_text()
E6 = ROOT / "e6-agent-trial"

MUTATIONS: dict[str, tuple[str, str, str]] = {
    # id: (description, old, new)
    "a1_typo_attr": ("typo kept.discont", "kept.discount.fill_null(0)", "kept.discont.fill_null(0)"),
    "a2_typo_filter": ("typo orders.statu", 'orders.status != "cancelled"', 'orders.statu != "cancelled"'),
    "a3_typo_joined": ("typo o.ordr_id after join", "o.order_id.count()", "o.ordr_id.count()"),
    "a4_typo_join_key": ("typo c.custmer_id in join key", "o.customer_id == c.customer_id", "o.customer_id == c.custmer_id"),
    "b1_wrong_frame": ("customers passed to clean_orders", "cleaned = clean_orders(orders)", "cleaned = clean_orders(customers)"),
    "b2_swapped_args": ("swapped stats args", "country_month_stats(cleaned, customers)", "country_month_stats(customers, cleaned)"),
    "b3_raw_into_stats": ("raw orders into stats", "country_month_stats(cleaned, customers)", "country_month_stats(orders, customers)"),
    "c1_return_kept": ("forgot net_amount: return kept", "return Order.extend(kept, NetAmount(net_amount=kept.amount - kept.discount.fill_null(0)))", "return kept"),
    "c2_extend_no_delta": ("forgot net_amount: extend without delta", "return Order.extend(kept, NetAmount(net_amount=kept.amount - kept.discount.fill_null(0)))", "return Order.extend(kept)"),
    "c3_missing_output_col": ("forgot an output column", "        avg_net=o.net_amount.mean(),\n", ""),
    "d1_cast_str_dtype": ('order_count .cast("float64")', "order_count=o.order_id.count(),", 'order_count=o.order_id.count().cast("float64"),'),
    "d1b_cast_type": ("order_count .cast(float)", "order_count=o.order_id.count(),", "order_count=o.order_id.count().cast(float),"),
    "d2_times_float": ("order_count count() * 1.0", "order_count=o.order_id.count(),", "order_count=o.net_amount.count() * 1.0,"),
    "d3_schema_float": ("schema says order_count: float", "    order_count: Column[int]", "    order_count: Column[float]"),
    "n1_nullable_into_net": ("forgot fill_null (bonus: null safety)", "kept.discount.fill_null(0)", "kept.discount"),
}

CHECKERS = {
    "pyright": ["pyright", "-p", str(PROTO / "pyrightconfig.json")],
    "mypy": ["mypy", "--config-file", str(PROTO / "mypy.ini"), "--no-error-summary"],
    "ty": ["ty", "check", "--python", ".venv", "--extra-search-path", str(PROTO / "src"), "--output-format", "concise"],
    "pyrefly": ["pyrefly", "check", "--python-interpreter-path", ".venv/bin/python", "--search-path", str(PROTO / "src"), "--output-format", "min-text"],
}


def static(path: Path) -> dict[str, str]:
    res: dict[str, str] = {}
    for name, cmd in CHECKERS.items():
        p = subprocess.run(["uv", "run", "--frozen", *cmd, str(path)], cwd=ROOT, capture_output=True, text=True)
        text = p.stdout + p.stderr
        (OUT / f"{path.stem}.{name}.txt").write_text(text)
        errs = [ln for ln in text.splitlines() if re.search(r"(- error:|: error|error\[|^\s*ERROR )", ln) and path.name in ln]
        res[name] = shorten(errs[0]) if errs else "-"
    return res


def shorten(line: str) -> str:
    line = re.sub(r"^.*?\.py:(\d+):[\d:-]*\s*", r"L\1 ", line.strip())
    line = re.sub(r"^ERROR\s+", "", line)
    return line[:110]


def runtime(path: Path, args: list[str] | None = None) -> str:
    code = (
        "import sys, runpy; sys.argv=['x'];"
        f"ns = runpy.run_path({str(path)!r});"
        + (f"ns['main']({args[0]!r}, {args[1]!r})" if args else "ns['main']()")
    )
    env = {**os.environ, "PYTHONPATH": str(PROTO / "src")}
    p = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, env=env)
    if p.returncode == 0:
        return "-"
    tail = [ln for ln in p.stderr.strip().splitlines() if ln.strip()]
    i = next((k for k, ln in enumerate(tail) if re.match(r"^[\w.]+(Error|Exception)\b", ln)), len(tail) - 1)
    return " | ".join(tail[i : i + 3])[:300]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (HERE / "bugs").mkdir(exist_ok=True)
    rows = []
    for bid, (desc, old, new) in MUTATIONS.items():
        assert old in SRC, bid
        path = HERE / "bugs" / f"{bid}.py"
        path.write_text(SRC.replace(old, new, 1).replace('parents[3] / "e6-agent-trial"', 'parents[4] / "e6-agent-trial"'))
        rows.append((bid, desc, static(path), runtime(path)))
    for csv in sorted((E6 / "bad").glob("*.csv")):
        cust, orders = (csv, E6 / "orders.csv") if csv.name.startswith("cust") else (E6 / "customers.csv", csv)
        rows.append((f"e_{csv.stem}", f"bad CSV {csv.name}", dict.fromkeys(CHECKERS, "n/a"), runtime(HERE / "pipeline.py", [str(cust), str(orders)])))
    lines = []
    for bid, desc, st, rt in rows:
        lines.append(f"## {bid}: {desc}")
        for c in CHECKERS:
            lines.append(f"  {c:8} {st[c]}")
        lines.append(f"  runtime  {rt}")
    text = "\n".join(lines)
    (OUT / "matrix.txt").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
