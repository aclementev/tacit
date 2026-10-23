"""Run all 4 checkers on probe files against a chosen tacit_next package dir.

python chk_src.py SRC_DIR FILE.py   -> one row per probe line that has a `# L..` marker:
   marker | pyright | mypy | ty | pyrefly   (E = error; otherwise the revealed type)
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "conformance"))
import static  # noqa: E402

src, f = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
cfg = Path(__file__).resolve().parent / "conformance" / f"cfg_chk_{src.parent.name}_{src.name}"
res = static.checkers(src, [str(f)], cfg)
lines = f.read_text().splitlines()
print(f"# {f.name} against {src}")
for i, line in enumerate(lines, 1):
    m = re.search(r"#\s*(L\d+\b.*)$", line)
    if not m:
        continue
    cells = []
    for chk in ("pyright", "mypy", "ty", "pyrefly"):
        d = [x for x in res.get(chk, []) if x[1] == i]
        err = any(k == "error" for _, _, k, _ in d)
        rev = next((t for _, _, k, t in d if k == "reveal"), "-")
        cells.append(("E " if err else "") + rev)
    print(f"{m.group(1)[:60]:<60} | " + " | ".join(f"{c[:30]:<30}" for c in cells))
