"""Semantic diff of ibis behaviour between versions on the conformance cases (what a facade must track).

python runtime_diff.py out/runtime_A.json out/runtime_B.json
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "conformance"))
from cases import all_cases  # noqa: E402

a, b = (json.load(open(p)) for p in sys.argv[1:3])
cs = {c.id: c for c in all_cases()}


def sig(r):
    if "error" in r:
        return "ERR"
    x = r.get("exec_error", "")
    if x and re.search(r"Binder Error|Unimplemented type for cast|Unsupported cast|Cannot compare|Cannot mix|Parser Error", x):
        return "BACKEND_ERR"
    return f"{r.get('kind')}[{r.get('fam')}]"


groups = defaultdict(list)
for cid, ra in a["cases"].items():
    rb = b["cases"][cid]
    sa, sb = sig(ra), sig(rb)
    if sa != sb:
        c = cs[cid]
        groups[(c.template, sa, sb)].append(f"{c.container[0]}:{c.fam}{'?' if c.nullable else ''}")
print(f"ibis {a['ibis']} -> {b['ibis']}: {sum(len(v) for v in groups.values())} cases changed in {len(groups)} groups")
for (tpl, sa, sb), who in sorted(groups.items()):
    print(f"  {tpl:<26} {sa:>16} -> {sb:<16} [{' '.join(who)}]")
