"""Fold out/<cfg>/cells.txt into out/summary.txt: bug classes x (layer, checker), plus false positives.

    uv run --frozen python e17-lean-typing/tools/summarize.py
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
CHECKERS = ["pyright", "mypy", "ty", "pyrefly"]
ORDER = ["typo-c", "typo-df", "typo-deferred", "wrong-method", "bad-operator", "wrong-frame", "forgot-cast",
         "raw-table", "build-missing", "build-extra", "build-family", "int-float", "nullable"]


def group(fname: str) -> str:
    if fname.startswith("b_"):
        return "bugs"
    if fname in ("t2_cases.py", "t_columns.py"):
        return "cases"
    return "examples"


def main() -> None:
    out: list[str] = []
    cfgs = sorted(p.name for p in (HERE / "out").iterdir() if (p / "cells.txt").exists() and p.name.count("-") == 2)
    for cfg in cfgs:
        caught: dict[tuple[str, str], dict[str, list[int]]] = defaultdict(lambda: {c: [0, 0] for c in CHECKERS})
        fp: dict[str, dict[str, int]] = defaultdict(lambda: {c: 0 for c in CHECKERS})
        wrong: dict[str, int] = {c: 0 for c in CHECKERS}
        for row in (HERE / "out" / cfg / "cells.txt").read_text().splitlines():
            fname, _line, kind, cat, chk, res, _src = row.split("\t")
            g = group(fname)
            if kind == "E":
                cell = caught[cat, g][chk]
                cell[1] += 1
                cell[0] += res == "caught"
            elif res == "FP" and g != "bugs":
                fp[fname if g == "examples" else "cases (correct lines)"][chk] += 1
            elif res.startswith("WRONG") and g == "cases":
                wrong[chk] += 1
        out.append(f"[{cfg}]  caught/planted per checker: " + " ".join(f"{c:>8}" for c in CHECKERS))
        for cat in ORDER:
            for g in ("cases", "bugs"):
                if (cat, g) in caught:
                    cells = " ".join(f"{f'{a}/{b}':>8}" for a, b in (caught[cat, g][c] for c in CHECKERS))
                    out.append(f"  {cat:16} {g:6}                  {cells}")
        for k, v in sorted(fp.items()):
            out.append(f"  FP {k:40} " + " ".join(f"{v[c]:>8}" for c in CHECKERS))
        out.append("  reveal mismatches (cases)                   " + " ".join(f"{wrong[c]:>8}" for c in CHECKERS))
        out.append("")
    (HERE / "out" / "summary.txt").write_text("\n".join(out))
    print("\n".join(out))


if __name__ == "__main__":
    main()
