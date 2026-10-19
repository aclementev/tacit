"""Run pyright, mypy, ty and pyrefly on files with expected-result markers; print a matrix.

Markers (one statement per line):
    expr  # E: <reason>          an error is expected on this line
    reveal_type(x)  # R: <type>   revealed type must equal <type> (module prefixes stripped)
    # @feature <name>             following lines belong to this feature
Any error on a line without `# E:` is a false positive.

Usage (from anywhere):
    python tests/typecheck/run_matrix.py [files...]      default: tests/typecheck/t*.py
Writes raw checker output to out/typecheck/raw_<checker>.txt, the matrix to
out/typecheck/matrix.txt and per-line details to out/typecheck/details.txt.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTO = HERE.parent.parent  # e8-prototype
ROOT = PROTO.parent  # dev/research/redesign (uv project)
OUT = PROTO / "out" / "typecheck"
CHECKERS = ["pyright", "mypy", "ty", "pyrefly"]


def run(cmd: list[str]) -> str:
    p = subprocess.run(["uv", "run", "--frozen", *cmd], cwd=ROOT, capture_output=True, text=True)
    return p.stdout + p.stderr


def norm(t: str) -> str:
    t = t.strip().strip('"`')
    t = re.sub(r"\b(?:[a-z_][\w]*\.)+(?=[A-Za-z_])", "", t)  # module qualifiers
    t = t.replace("typing.", "").replace("float*", "float")  # ty prints the int|float promotion as float*
    return re.sub(r"\s+", " ", t)


Diag = dict[tuple[str, int], dict[str, list[str]]]  # (file, line) -> {"E": [...], "R": [...]}


def collect(files: list[Path], search: list[Path]) -> tuple[dict[str, Diag], dict[str, str]]:
    fs = [str(f) for f in files]
    sp = [str(s) for s in search]
    raw: dict[str, str] = {}
    raw["pyright"] = run(["pyright", "-p", str(PROTO / "pyrightconfig.json"), "--outputjson", *fs])
    raw["mypy"] = run(["mypy", "--config-file", str(PROTO / "mypy.ini"), "--show-error-codes", "--no-error-summary", *fs])
    ty_sp = [a for s in sp for a in ("--extra-search-path", s)]
    raw["ty"] = run(["ty", "check", "--python", ".venv", *ty_sp, "--output-format", "concise", *fs])
    py_sp = [a for s in sp for a in ("--search-path", s)]
    raw["pyrefly"] = run(
        ["pyrefly", "check", "--python-interpreter-path", ".venv/bin/python", *py_sp, "--output-format", "min-text", *fs]
    )
    res: dict[str, Diag] = {c: defaultdict(lambda: defaultdict(list)) for c in CHECKERS}
    names = {Path(f).name for f in fs}

    def key(path: str, line: int) -> tuple[str, int] | None:
        n = Path(path).name
        return (n, line) if n in names else None

    js = raw["pyright"][raw["pyright"].find("{") :]
    for d in json.loads(js).get("generalDiagnostics", []):
        k = key(d["file"], d["range"]["start"]["line"] + 1)
        if not k:
            continue
        if d["severity"] == "error":
            res["pyright"][k]["E"].append(d["message"].splitlines()[0] + f" ({d.get('rule', '')})")
        elif d["severity"] == "information" and (m := re.search(r'^Type of ".*" is "(.*)"$', d["message"], re.S)):
            res["pyright"][k]["R"].append(norm(m[1]))
    for line in raw["mypy"].splitlines():
        m = re.match(r"(.+?):(\d+): (error|note): (.*)", line)
        if not m or not (k := key(m[1], int(m[2]))):
            continue
        if m[3] == "error":
            res["mypy"][k]["E"].append(m[4])
        elif r := re.match(r'Revealed type is "(.*)"', m[4]):
            res["mypy"][k]["R"].append(norm(r[1]))
    for line in raw["ty"].splitlines():
        m = re.match(r"(.+?):(\d+):\d+: (\w+)\[([\w-]+)\] (.*)", line)
        if not m or not (k := key(m[1], int(m[2]))):
            continue
        if m[4] == "revealed-type":
            res["ty"][k]["R"].append(norm(m[5].split(":", 1)[1]))
        elif m[3] == "error":
            res["ty"][k]["E"].append(f"{m[4]}: {m[5]}")
    for line in raw["pyrefly"].splitlines():
        m = re.match(r"\s*(ERROR|INFO|WARN)\s+(.+?):(\d+):[\d:-]+: (.*) \[([\w-]+)\]$", line)
        if not m or not (k := key(m[2], int(m[3]))):
            continue
        if m[5] == "reveal-type":
            res["pyrefly"][k]["R"].append(norm(m[4].split(":", 1)[1]))
        elif m[1] == "ERROR":
            res["pyrefly"][k]["E"].append(f"{m[5]}: {m[4]}")
    return res, raw


def expectations(f: Path) -> list[tuple[int, str, str, str | None, str]]:
    """(line, feature, kind 'E'|'R'|'-', expected, source) for every code line."""
    out = []
    feature = "(module)"
    for i, src in enumerate(f.read_text().splitlines(), 1):
        s = src.strip()
        if m := re.match(r"# @feature (.*)", s):
            feature = m[1].strip()
            continue
        if not s or s.startswith("#") or s.startswith('"""'):
            continue
        if m := re.search(r"#\s*E:\s*(.*)$", src):
            out.append((i, feature, "E", m[1].strip(), s))
        elif m := re.search(r"#\s*R:\s*(.*)$", src):
            out.append((i, feature, "R", norm(m[1]), s))
        else:
            out.append((i, feature, "-", None, s))
    return out


def main() -> None:
    args = [Path(a).resolve() for a in sys.argv[1:]] or sorted(HERE.glob("t*.py"))
    files = args
    search = [PROTO / "src", HERE] + sorted({f.parent for f in files})
    res, raw = collect(files, search)
    OUT.mkdir(parents=True, exist_ok=True)
    for c, text in raw.items():
        (OUT / f"raw_{c}.txt").write_text(text)

    # feature -> checker -> counters
    feats: dict[str, dict[str, dict[str, int]]] = defaultdict(lambda: {c: defaultdict(int) for c in CHECKERS})
    order: list[str] = []
    details: list[str] = []
    for f in files:
        for line, feat, kind, exp, src in expectations(f):
            fk = f"{f.stem}: {feat}"
            if fk not in order:
                order.append(fk)
            for c in CHECKERS:
                d = res[c].get((f.name, line), {"E": [], "R": []})
                errs, revs = d.get("E", []), d.get("R", [])
                cnt = feats[fk][c]
                if kind == "E":
                    cnt["cases"] += 1
                    if errs:
                        cnt["ok"] += 1
                    else:
                        cnt["missed"] += 1
                        details.append(f"MISSED  {c:8} {f.name}:{line}  {src}")
                elif kind == "R":
                    cnt["cases"] += 1
                    if errs:
                        cnt["fp"] += 1
                        details.append(f"FP      {c:8} {f.name}:{line}  {src}\n          -> {errs[0][:200]}")
                    elif revs and revs[0] == exp:
                        cnt["ok"] += 1
                    else:
                        cnt["wrong"] += 1
                        details.append(f"TYPE    {c:8} {f.name}:{line}  expected {exp}, got {revs[0] if revs else None}")
                elif errs:
                    cnt["fp"] += 1
                    details.append(f"FP      {c:8} {f.name}:{line}  {src}\n          -> {errs[0][:200]}")
    lines = [f"{'feature':62} " + " ".join(f"{c:>14}" for c in CHECKERS)]
    totals = {c: defaultdict(int) for c in CHECKERS}
    for fk in order:
        cells = []
        for c in CHECKERS:
            cnt = feats[fk][c]
            for k, v in cnt.items():
                totals[c][k] += v
            cells.append(cell(cnt))
        lines.append(f"{fk[:62]:62} " + " ".join(f"{x:>14}" for x in cells))
    lines.append(f"{'TOTAL':62} " + " ".join(f"{cell(totals[c]):>14}" for c in CHECKERS))
    lines.append("cell = ok/cases [mN = missed errors, wN = wrong revealed type, fN = false positives]")
    text = "\n".join(lines)
    (OUT / "matrix.txt").write_text(text + "\n")
    (OUT / "details.txt").write_text("\n".join(details) + "\n")
    print(text)
    print(f"\n{len(details)} non-ok cells; see {OUT / 'details.txt'}")


def cell(cnt: dict[str, int]) -> str:
    s = f"{cnt['ok']}/{cnt['cases']}"
    extra = "".join(f" {p}{cnt[k]}" for k, p in (("missed", "m"), ("wrong", "w"), ("fp", "f")) if cnt[k])
    return s + extra


if __name__ == "__main__":
    main()
