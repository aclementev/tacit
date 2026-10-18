"""Run pyright, mypy, ty and pyrefly on a prototype file and tabulate per-case results.

A "case" is a line carrying `# case: <name>` and optionally `expect: err|ok`.
Each cell shows `ok`, `ERR(<code>)`, or the revealed type for reveal_type lines.
A trailing `!` marks a mismatch with the expectation.

Usage: uv run python matrix.py [--stock] file.py [...]   (raw outputs go to raw/)

Default runs against _patched/ibis (two small upstream fixes, see FINDINGS.md);
--stock runs against the installed ibis 12.0.0.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
RAW = HERE / "raw"

CHECKERS = {
    "pyright": ["pyright"],
    "mypy": ["mypy", "--config-file", "mypy.ini", "--no-error-summary", "--hide-error-context", "--show-error-codes"],
    "ty": ["ty", "check", "--output-format", "concise"],
    "pyrefly": ["pyrefly", "check", "--output-format", "min-text"],
}

PATTERNS = {
    "pyright": [
        (re.compile(r":(\d+):\d+ - information: Type of \".*\" is \"(.*)\"$"), "rev"),
        (re.compile(r":(\d+):\d+ - error: (.*?)(?:\((\w+)\))?$"), "err"),
    ],
    "mypy": [
        (re.compile(r":(\d+): note: Revealed type is \"(.*)\"$"), "rev"),
        (re.compile(r":(\d+): error: (.*?)(?:\s+\[([\w-]+)\])?$"), "err"),
    ],
    "ty": [
        (re.compile(r":(\d+):\d+: info\[revealed-type\] Revealed type: `(.*)`$"), "rev"),
        (re.compile(r":(\d+):\d+: error\[([\w-]+)\] (.*)$"), "tyerr"),
    ],
    "pyrefly": [
        (re.compile(r"INFO .*?:(\d+):[\d-]+: revealed type: (.*) \[reveal-type\]$"), "rev"),
        (re.compile(r"ERROR .*?:(\d+):[\d-]+: (.*) \[([\w-]+)\]$"), "err"),
    ],
}


PATCHED_ARGS = {
    "pyright": ["-p", "pyrightconfig.patched.json"],
    "mypy": [],
    "ty": ["--extra-search-path", "_patched"],
    "pyrefly": ["--search-path", "_patched"],
}


def run(path: Path, patched: bool) -> dict[str, dict[int, list[str]]]:
    results: dict[str, dict[int, list[str]]] = {}
    env = dict(os.environ)
    if patched:
        env["MYPYPATH"] = str(HERE / "_patched")
    suffix = ".patched" if patched else ".stock"
    for name, cmd in CHECKERS.items():
        extra = PATCHED_ARGS[name] if patched else []
        if name == "mypy" and os.environ.get("MATRIX_MYPY_INI"):
            cmd = [c if c != "mypy.ini" else os.environ["MATRIX_MYPY_INI"] for c in cmd]
        proc = subprocess.run([*cmd, *extra, path.name], cwd=HERE, capture_output=True, text=True, env=env)
        out = proc.stdout + proc.stderr
        (RAW / f"{path.stem}.{name}{suffix}.txt").write_text(out)
        per_line: dict[int, list[str]] = {}
        lines: list[str] = []
        for raw_line in out.splitlines():
            # pyright wraps messages; its rule code ends the last continuation line
            if name == "pyright" and lines and raw_line.startswith("  ") and not raw_line.startswith("  /"):
                lines[-1] += " " + raw_line.strip()
            else:
                lines.append(raw_line)
        for line in lines:
            if path.name not in line:
                continue
            for pat, kind in PATTERNS[name]:
                m = pat.search(line)
                if not m:
                    continue
                ln = int(m.group(1))
                if kind == "rev":
                    per_line.setdefault(ln, []).append("=" + m.group(2))
                elif kind == "tyerr":
                    if m.group(2) != "unimported-directive":
                        per_line.setdefault(ln, []).append(f"ERR({m.group(2)})")
                else:
                    code = (m.group(3) or "?") if m.lastindex and m.lastindex >= 3 else "?"
                    if code in ("unimported-directive",):
                        break
                    per_line.setdefault(ln, []).append(f"ERR({code})")
                break
        results[name] = per_line
    return results


def main() -> None:
    RAW.mkdir(exist_ok=True)
    args = sys.argv[1:]
    patched = "--stock" not in args
    for arg in [a for a in args if not a.startswith("--")]:
        path = (HERE / arg).resolve()
        res = run(path, patched)
        print(f"\n### {path.name} ({'patched ibis' if patched else 'stock ibis 12.0.0'})\n")
        print("| case | expect | " + " | ".join(CHECKERS) + " |")
        print("|---|---|" + "---|" * len(CHECKERS))
        for i, src in enumerate(path.read_text().splitlines(), start=1):
            m = re.search(r"# case: ([^|]+?)(?:\s+expect: (err|ok))?\s*$", src)
            if not m:
                continue
            name, expect = m.group(1).strip(), m.group(2) or ""
            cells = []
            for ck in CHECKERS:
                items = res[ck].get(i, [])
                revs = [x[1:] for x in items if x.startswith("=")]
                errs = sorted({x for x in items if not x.startswith("=")})
                cell = ", ".join(revs) if revs else ""
                if errs:
                    cell = (cell + " " if cell else "") + " ".join(errs)
                if not cell:
                    cell = "ok"
                got_err = bool(errs)
                if expect and ((expect == "err") != got_err):
                    cell += " !"
                cells.append(cell.replace("|", "\\|"))
            print(f"| {name} | {expect} | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()
