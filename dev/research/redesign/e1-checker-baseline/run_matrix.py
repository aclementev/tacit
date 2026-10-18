#!/usr/bin/env python3
"""Run every checker variant over a set of files; write raw output to out/ and
print per-file (line -> message) summaries. Usage: run_matrix.py <glob-dir> [variant ...]"""
import json, re, subprocess, sys, pathlib

HERE = pathlib.Path(__file__).parent
VARIANTS = {
    "pyright":        ["uv", "run", "pyright", "-p", "pyrightconfig.json"],
    "pyright-repo":   ["uv", "run", "pyright", "-p", "pyrightconfig_repo.json"],
    "mypy":           ["uv", "run", "mypy", "--config-file", "mypy.ini", "--no-pretty", "--show-column-numbers", "--show-error-codes"],
    "mypy-ignoremissing": ["uv", "run", "mypy", "--config-file", "mypy_ignoremissing.ini", "--no-pretty", "--show-column-numbers", "--show-error-codes"],
    "mypy-strict":    ["uv", "run", "mypy", "--config-file", "mypy_strict.ini", "--no-pretty", "--show-column-numbers", "--show-error-codes"],
    "mypy-follow":    ["uv", "run", "mypy", "--config-file", "mypy_follow.ini", "--no-pretty", "--show-column-numbers", "--show-error-codes"],
    "mypy-follow-strict": ["uv", "run", "mypy", "--config-file", "mypy_follow_strict.ini", "--no-pretty", "--show-column-numbers", "--show-error-codes"],
    "mypy-tacit-typed": ["uv", "run", "mypy", "--config-file", "mypy_tacittyped.ini", "--no-pretty", "--show-column-numbers", "--show-error-codes"],
    "ty":             ["uv", "run", "ty", "check", "--config-file", "ty.toml", "--output-format", "concise", "--color", "never"],
    "pyrefly":        ["uv", "run", "pyrefly", "check", "--config", "pyrefly.toml", "--output-format", "min-text"],
}

def run(variant, paths):
    cmd = VARIANTS[variant] + paths
    if variant.startswith("pyright"):
        cmd = cmd[:]  # json
        cmd.insert(4 if False else len(VARIANTS[variant]), "--outputjson")
    p = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True)
    return p.stdout + p.stderr, p.stdout

def parse(variant, stdout):
    """-> list of (file, line, msg)"""
    res = []
    if variant.startswith("pyright"):
        try:
            d = json.loads(stdout)
        except Exception:
            return res
        for g in d.get("generalDiagnostics", []):
            if g["severity"] != "error":
                continue
            f = pathlib.Path(g["file"]).relative_to(HERE.resolve())
            res.append((str(f), g["range"]["start"]["line"] + 1,
                        g["message"].replace("\n", " | ") + f" ({g.get('rule','')})"))
    elif variant.startswith("mypy"):
        for l in stdout.splitlines():
            m = re.match(r"^(\S+?\.py):(\d+):\d+: error: (.*)$", l)
            if m: res.append((m[1], int(m[2]), m[3]))
    elif variant == "ty":
        for l in stdout.splitlines():
            m = re.match(r"^(\S+?\.py):(\d+):\d+: (?:error|warning)\[(.*?)\] (.*)$", l)
            if m: res.append((m[1], int(m[2]), f"{m[4]} ({m[3]})"))
    elif variant == "pyrefly":
        for l in stdout.splitlines():
            m = re.match(r"^ERROR (\S+?\.py):(\d+):[\d\-:]+: (.*)$", l)
            if m: res.append((m[1], int(m[2]), m[3]))
    return res

if __name__ == "__main__":
    target = sys.argv[1]
    variants = sys.argv[2:] or list(VARIANTS)
    out = HERE / "out"; out.mkdir(exist_ok=True)
    for v in variants:
        raw, so = run(v, [target])
        (out / f"{target.strip('/').replace('/','_')}.{v}.txt").write_text(raw)
        diags = parse(v, so)
        print(f"##### {v}  {target}: {len(diags)} errors")
        for f, l, m in sorted(diags):
            print(f"  {f}:{l}: {m[:230]}")
