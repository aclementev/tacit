#!/usr/bin/env python3
"""Compare each checker's errors on tc_raw/ against the expected-error lines
(lines carrying '# pyright: ignore[...]' in tc/). Prints caught / missed / spurious."""
import re, pathlib, collections
from run_matrix import run, parse, VARIANTS, HERE

expected = collections.defaultdict(set)
for f in sorted((HERE/"tc").glob("*.py")):
    for i, l in enumerate(f.read_text().splitlines(), 1):
        if "# pyright: ignore" in l:
            expected[f"tc_raw/{f.name}"].add(i)
total = sum(len(v) for v in expected.values())
print(f"expected errors: {total}")
for v in ["pyright", "pyright-repo", "mypy", "mypy-ignoremissing", "mypy-tacit-typed", "mypy-follow", "mypy-strict", "ty", "pyrefly"]:
    _, so = run(v, ["tc_raw"])
    diags = parse(v, so)
    got = collections.defaultdict(list)
    for f, l, m in diags: got[f].append((l, m))
    caught = missed = 0; spurious = []
    for f, lines in expected.items():
        gl = {l for l, _ in got.get(f, [])}
        caught += len(lines & gl); missed += len(lines - gl)
    for f, ms in got.items():
        for l, m in ms:
            if l not in expected.get(f, set()):
                spurious.append((f, l, m))
    imp = [s for s in spurious if "import-untyped" in s[2]]
    other = [s for s in spurious if "import-untyped" not in s[2]]
    kinds = collections.Counter(re.sub(r'".*?"', '"."', s[2])[:70] for s in other)
    print(f"{v:20s} caught {caught}/{total}  missed {missed}  spurious: {len(other)} (+{len(imp)} import-untyped)")
    for k, c in kinds.most_common(4): print(f"      {c}x {k}")
