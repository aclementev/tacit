"""Run pyright / mypy / ty / pyrefly on marked case files for one configuration; print a matrix.

    uv run --frozen python e17-lean-typing/tools/run_matrix.py --layer l1 [--nostub] [--patched] FILES...

Markers (one statement per line, as in E13's runner):
    expr  # E: [cat] reason           a bug: an error is expected on this line
    reveal_type(x)  # R: T3 ;; l1,l2=T  expected revealed type (default ;; per-layer overrides)
    # @feature name                    following lines belong to this feature
Any error on an unmarked line is a false positive. `--nostub` checks the same files against
`tacit_t2n` (DataFrame statically subclasses ir.Table: no generated Table stub). `--patched`
puts E3's patched ibis (the two upstream one-line fixes) ahead of site-packages.

Writes out/<cfg>/{matrix,details,cells}.txt (+ raw_<checker>.txt); cells.txt is one
tab-separated line per expectation: file line kind cat checker result.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]  # e17-lean-typing
ROOT = HERE.parent  # dev/research/redesign (uv project)
PATCHED = ROOT / "e3-schema-algebra" / "_patched"
CHECKERS = ["pyright", "mypy", "ty", "pyrefly"]


def run(cmd: list[str]) -> str:
    p = subprocess.run(["uv", "run", "--frozen", *cmd], cwd=ROOT, capture_output=True, text=True)
    return p.stdout + p.stderr


def norm(t: str) -> str:
    t = t.strip().strip('"`')
    t = re.sub(r"\b(?:[a-z_][\w]*\.)+(?=[A-Za-z_])", "", t)
    t = t.replace("typing.", "").replace("float*", "float")
    return re.sub(r"\s+", " ", t)


def configs(cfg_dir: Path, search: list[Path]) -> None:
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "pyrightconfig.json").write_text(json.dumps({
        "pythonVersion": "3.13", "venvPath": str(ROOT), "venv": ".venv",
        "extraPaths": [str(s) for s in search], "typeCheckingMode": "standard",
        "reportMissingModuleSource": False,
    }))
    (cfg_dir / "mypy.ini").write_text("\n".join([
        "[mypy]", "python_version = 3.13", "follow_untyped_imports = True", "check_untyped_defs = True",
        "mypy_path = " + ":".join(str(s) for s in search), f"cache_dir = {cfg_dir / '.mypy_cache'}",
        "[mypy-tacit_thin.*]", "ignore_errors = True", "[mypy-tacit_t2.*]", "ignore_errors = True",
        "[mypy-tacit_t2n.*]", "ignore_errors = True", "[mypy-ibis.*]", "ignore_errors = True", "",
    ]))


def collect(files: list[Path], search: list[Path], cfg_dir: Path) -> tuple[dict, dict[str, str]]:
    fs = [str(f) for f in files]
    configs(cfg_dir, search)
    raw: dict[str, str] = {}
    raw["pyright"] = run(["pyright", "-p", str(cfg_dir / "pyrightconfig.json"), "--outputjson", *fs])
    raw["mypy"] = run(["mypy", "--config-file", str(cfg_dir / "mypy.ini"), "--show-error-codes",
                       "--no-error-summary", *fs])
    raw["ty"] = run(["ty", "check", "--python", ".venv", *[a for s in search for a in ("--extra-search-path", str(s))],
                     "--output-format", "concise", *fs])
    raw["pyrefly"] = run(["pyrefly", "check", "--python-interpreter-path", ".venv/bin/python",
                          *[a for s in search for a in ("--search-path", str(s))], "--output-format", "min-text", *fs])
    res: dict = {c: defaultdict(lambda: defaultdict(list)) for c in CHECKERS}
    names = {Path(f).name for f in fs}

    def key(path: str, line: int) -> tuple[str, int] | None:
        n = Path(path).name
        return (n, line) if n in names else None

    js = raw["pyright"][raw["pyright"].find("{"):]
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


def expectations(f: Path, layer: str) -> list[tuple[int, str, str, str | None, str, str]]:
    """(line, feature, kind 'E'|'R'|'-', expected, category, source)."""
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
            cat = re.match(r"\[([\w-]+)\]", m[1])
            out.append((i, feature, "E", m[1].strip(), cat[1] if cat else "-", s))
        elif m := re.search(r"#\s*R:\s*(.*)$", src):
            parts = [p.strip() for p in m[1].split(";;")]
            exp = parts[0]
            for p in parts[1:]:
                ls, t = p.split("=", 1)
                if layer in [x.strip() for x in ls.split(",")]:
                    exp = t
            out.append((i, feature, "R", norm(exp), "reveal", s))
        else:
            out.append((i, feature, "-", None, "ok", s))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", required=True, choices=["l1", "l2", "l3"])
    ap.add_argument("--nostub", action="store_true")
    ap.add_argument("--patched", action="store_true")
    ap.add_argument("--tag", default="")
    ap.add_argument("files", nargs="+")
    a = ap.parse_args()
    cfg = f"{a.layer}-{'nostub' if a.nostub else 'stub'}-{'patched' if a.patched else 'stock'}{a.tag}"
    out = HERE / "out" / cfg
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    src_files = [Path(f).resolve() for f in a.files]
    files = src_files
    if a.nostub:  # same files, importing tacit_t2n
        tmp = out / "_files"
        tmp.mkdir()
        files = []
        for f in src_files:
            t = tmp / f.name
            t.write_text(re.sub(r"\btacit_t2\b", "tacit_t2n", f.read_text()))
            files.append(t)
        for extra in {f.parent for f in src_files}:  # sibling helper modules (_schemas.py, ...)
            for h in extra.glob("_*.py"):
                if not (tmp / h.name).exists():
                    (tmp / h.name).write_text(re.sub(r"\btacit_t2\b", "tacit_t2n", h.read_text()))
    search = ([PATCHED] if a.patched else []) + [HERE / "layers" / a.layer] + sorted({f.parent for f in files})
    res, raw = collect(files, search, out / "cfg")
    for c, text in raw.items():
        (out / f"raw_{c}.txt").write_text(text)
    feats: dict = defaultdict(lambda: {c: defaultdict(int) for c in CHECKERS})
    order: list[str] = []
    details: list[str] = []
    cells: list[str] = []
    for f in files:
        for line, feat, kind, exp, cat, src in expectations(f, a.layer):
            fk = f"{f.stem}: {feat}"
            if fk not in order:
                order.append(fk)
            for c in CHECKERS:
                d = res[c].get((f.name, line), {"E": [], "R": []})
                errs, revs = d.get("E", []), d.get("R", [])
                cnt = feats[fk][c]
                if kind == "E":
                    cnt["cases"] += 1
                    r = "caught" if errs else "MISSED"
                    cnt["ok" if errs else "missed"] += 1
                    if not errs:
                        details.append(f"MISSED  {c:8} {f.name}:{line}  {src}")
                elif kind == "R":
                    cnt["cases"] += 1
                    if errs:
                        cnt["fp"] += 1
                        r = "FP"
                        details.append(f"FP      {c:8} {f.name}:{line}  {src}\n          -> {errs[0][:220]}")
                    elif revs and revs[0] == exp:
                        cnt["ok"] += 1
                        r = "ok"
                    else:
                        cnt["wrong"] += 1
                        r = f"WRONG:{revs[0] if revs else None}"
                        details.append(f"TYPE    {c:8} {f.name}:{line}  expected {exp}, got {revs[0] if revs else None}")
                else:
                    r = "FP" if errs else "ok"
                    if errs:
                        cnt["fp"] += 1
                        details.append(f"FP      {c:8} {f.name}:{line}  {src}\n          -> {errs[0][:220]}")
                cells.append("\t".join([f.name, str(line), kind, cat, c, r, src[:120]]))
    lines = [f"[{cfg}]", f"{'feature':58} " + " ".join(f"{c:>13}" for c in CHECKERS)]
    totals = {c: defaultdict(int) for c in CHECKERS}
    for fk in order:
        row = []
        for c in CHECKERS:
            cnt = feats[fk][c]
            for k, v in cnt.items():
                totals[c][k] += v
            row.append(cell(cnt))
        lines.append(f"{fk[:58]:58} " + " ".join(f"{x:>13}" for x in row))
    lines.append(f"{'TOTAL':58} " + " ".join(f"{cell(totals[c]):>13}" for c in CHECKERS))
    lines.append("cell = ok/cases [mN = missed errors, wN = wrong revealed type, fN = false positives]")
    text = "\n".join(lines)
    (out / "matrix.txt").write_text(text + "\n")
    (out / "details.txt").write_text("\n".join(details) + "\n")
    (out / "cells.txt").write_text("\n".join(cells) + "\n")
    print(text)
    print(f"{len(details)} non-ok cells; see {out / 'details.txt'}")


def cell(cnt: dict[str, int]) -> str:
    s = f"{cnt['ok']}/{cnt['cases']}"
    return s + "".join(f" {p}{cnt[k]}" for k, p in (("missed", "m"), ("wrong", "w"), ("fp", "f")) if cnt[k])


if __name__ == "__main__":
    main()
