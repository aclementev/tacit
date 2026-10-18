"""Merge checker outputs into one per-line table: out/<name>.summary.txt.

Usage: python summarize.py probes/foo.py
R:<type> = revealed type, E:<code> = error.
"""

import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent


def short(t: str) -> str:
    t = re.sub(r"\bibis\.expr\.types\.\w+\.", "", t)
    t = re.sub(r"\b(probes\.)?\w+\.(?=[A-Z])", "", t)  # module prefixes
    return t.replace("builtins.", "")


def parse(checker: str, text: str, fname: str) -> dict[int, list[str]]:
    res: dict[int, list[str]] = defaultdict(list)
    for line in text.splitlines():
        if fname not in line:
            continue
        if checker == "pyright":
            m = re.search(r":(\d+):\d+ - (\w+): (.*)", line)
            if not m:
                continue
            ln, kind, msg = int(m[1]), m[2], m[3]
            if kind == "information" and (r := re.search(r'is "(.*)"$', msg)):
                res[ln].append("R:" + short(r[1]))
            elif kind == "error":
                code = re.search(r"\((\w+)\)$", msg)
                res[ln].append("E:" + (code[1] if code else msg[:40]))
        elif checker == "mypy":
            m = re.search(r":(\d+): (\w+): (.*)", line)
            if not m:
                continue
            ln, kind, msg = int(m[1]), m[2], m[3]
            if kind == "note" and (r := re.search(r'Revealed type is "(.*)"', msg)):
                res[ln].append("R:" + short(r[1]))
            elif kind == "error":
                code = re.search(r"\[([\w-]+)\]$", msg)
                res[ln].append("E:" + (code[1] if code else msg[:40]))
        elif checker == "ty":
            m = re.search(r":(\d+):\d+: (\w+)\[([\w-]+)\] (.*)", line)
            if not m:
                continue
            ln, kind, code, msg = int(m[1]), m[2], m[3], m[4]
            if code == "revealed-type":
                res[ln].append("R:" + short(msg.split("`", 1)[1].rstrip("`")))
            elif kind == "error":
                res[ln].append("E:" + code)
        elif checker == "pyrefly":
            m = re.search(r":(\d+):[\d:-]+: (.*) \[([\w-]+)\]$", line)
            if not m:
                continue
            ln, msg, code = int(m[1]), m[2], m[3]
            if code == "reveal-type":
                res[ln].append("R:" + short(msg.removeprefix("revealed type: ")))
            elif line.lstrip().startswith("ERROR") or "ERROR" in line[:8]:
                res[ln].append("E:" + code)
    return res


def main(path: str) -> None:
    src = (HERE / path).read_text().splitlines()
    name = Path(path).stem
    fname = Path(path).name
    tables = {
        c: parse(c, (HERE / "out" / f"{name}.{c}.txt").read_text(), fname)
        for c in ("pyright", "mypy", "ty", "pyrefly")
    }
    lines = sorted(set().union(*tables.values()))
    out = []
    for ln in lines:
        out.append(f"{ln:>4}| {src[ln - 1].strip()}")
        for c, tab in tables.items():
            out.append(f"      {c:<8} {' ; '.join(tab.get(ln, ['-']))}")
    text = "\n".join(out)
    (HERE / "out" / f"{name}.summary.txt").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    for p in sys.argv[1:]:
        main(p)
