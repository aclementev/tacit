"""Score marker files against pyright, mypy, ty and pyrefly.

Markers: `# E ...` expected error; `# E (ideal) ...` error a perfect system would give (upstream
limit, scored separately); `# R: X` reveal must contain X; anything else must be clean.
usage: uv run python tests/score.py tests/typecheck/t_nw.py [...]  -> out/typecheck_<file>.txt
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


def run(checker: str, f: str) -> tuple[dict[int, list[str]], dict[int, list[str]]]:
    errs: dict[int, list[str]] = defaultdict(list)
    reveals: dict[int, list[str]] = defaultdict(list)
    if checker == "pyright":
        p = subprocess.run(["uv", "run", "--frozen", "pyright", "-p", "pyrightconfig.json", "--outputjson", f], cwd=HERE, capture_output=True, text=True)
        for d in json.loads(p.stdout)["generalDiagnostics"]:
            ln = d["range"]["start"]["line"] + 1
            if d["severity"] == "error":
                errs[ln].append(d["message"].split("\n")[0])
            elif d["severity"] == "information" and "Type of" in d["message"]:
                reveals[ln].append(d["message"].split(" is ", 1)[-1].strip('"'))
    elif checker == "mypy":
        p = subprocess.run(["uv", "run", "--frozen", "mypy", "--config-file", "mypy.ini", "--no-pretty", "--show-error-codes", "--no-error-summary", f], cwd=HERE, capture_output=True, text=True)
        for line in p.stdout.splitlines():
            m = re.match(r"^\S+?:(\d+): (error|note): (.*)$", line)
            if not m:
                continue
            ln, kind, msg = int(m[1]), m[2], m[3]
            if kind == "error":
                errs[ln].append(msg)
            elif msg.startswith("Revealed type is"):
                reveals[ln].append(msg.split("is ", 1)[1].strip('"'))
    elif checker == "ty":
        p = subprocess.run(["uv", "run", "--frozen", "ty", "check", "--config-file", "ty.toml", "--output-format", "concise", "--color", "never", f], cwd=HERE, capture_output=True, text=True)
        for line in p.stdout.splitlines():
            m = re.match(r"^\S+?:(\d+):\d+: (\w+)\[([\w-]+)\] (.*)$", line)
            if not m:
                continue
            ln, sev, code, msg = int(m[1]), m[2], m[3], m[4]
            if code == "revealed-type":
                reveals[ln].append(msg.split(":", 1)[1].strip().strip("`"))
            elif sev in ("error", "warning") and code not in ("unused-ignore-comment",):
                errs[ln].append(f"{msg} [{code}]")
    elif checker == "pyrefly":
        p = subprocess.run(["uv", "run", "--frozen", "pyrefly", "check", "--config", "pyrefly.toml", "--output-format", "min-text", f], cwd=HERE, capture_output=True, text=True)
        for line in (p.stdout + p.stderr).splitlines():
            m = re.match(r"^\s*(ERROR|INFO|WARN)\s+\S+?:(\d+):[\d:-]+: (.*)$", line)
            if not m:
                continue
            ln = int(m[2])
            if m[1] == "INFO" and "revealed type:" in m[3]:
                reveals[ln].append(m[3].split("revealed type:", 1)[1].rsplit("[", 1)[0].strip())
            elif m[1] == "ERROR":
                errs[ln].append(m[3])
    return errs, reveals


def norm(t: str) -> str:
    t = re.sub(r"\b[a-z_][\w]*\.", "", t)  # drop module prefixes
    return t.replace("Optional[", "").replace(" ", "")


def score(f: str) -> str:
    lines = (HERE / f).read_text().splitlines()
    exp: dict[int, tuple[str, str]] = {}
    for i, line in enumerate(lines, 1):
        code = line.split("#", 1)[1] if "#" in line and not line.strip().startswith("#") and "`#" not in line else ""
        if re.match(r"\s*E \(ideal\)", code):
            exp[i] = ("ideal", code)
        elif re.match(r"\s*E\b", code):
            exp[i] = ("E", code)
        elif "R:" in code:
            exp[i] = ("R", code.split("R:", 1)[1].split("(")[0].strip())
    out = [f"## {f}"]
    summary = []
    for ck in ("pyright", "mypy", "ty", "pyrefly"):
        errs, reveals = run(ck, f)
        hit = miss = fp = rok = rbad = ideal_hit = ideal_n = 0
        notes = []
        n_e = sum(1 for k in exp.values() if k[0] == "E")
        for ln in range(1, len(lines) + 1):
            kind = exp.get(ln, ("", ""))[0]
            if kind == "E":
                if errs.get(ln):
                    hit += 1
                else:
                    miss += 1
                    notes.append(f"  MISS {ln}: {lines[ln - 1].strip()[:110]}")
            elif kind == "ideal":
                ideal_n += 1
                ideal_hit += bool(errs.get(ln))
            else:
                if errs.get(ln):
                    fp += 1
                    notes.append(f"  FP   {ln}: {lines[ln - 1].strip()[:80]} -> {errs[ln][0][:120]}")
                if kind == "R":
                    want = norm(exp[ln][1])
                    got = [norm(r) for r in reveals.get(ln, [])]
                    if any(want in g for g in got):
                        rok += 1
                    else:
                        rbad += 1
                        notes.append(f"  WRONG-R {ln}: want {exp[ln][1]} got {reveals.get(ln)}")
        n_r = sum(1 for k in exp.values() if k[0] == "R")
        summary.append(f"{ck:8s} errors {hit}/{n_e} caught, {fp} false pos | reveals {rok}/{n_r} | ideal-only {ideal_hit}/{ideal_n}")
        out.append(f"### {ck}: caught {hit}/{n_e}, missed {miss}, false positives {fp}, reveals ok {rok}/{n_r}, ideal-only caught {ideal_hit}/{ideal_n}")
        out += notes
    return "\n".join(summary) + "\n\n" + "\n".join(out)


if __name__ == "__main__":
    for f in sys.argv[1:]:
        txt = score(f)
        (HERE / "out" / f"typecheck_{Path(f).stem}.txt").write_text(txt + "\n")
        print(txt)
