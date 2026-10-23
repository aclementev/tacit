"""Wall time of each checker on a file, per facade (stub size cost). python time_checkers.py FILE SRC..."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "conformance"))
import static  # noqa: E402

f = str(Path(sys.argv[1]).resolve())
for src in sys.argv[2:]:
    s = Path(src).resolve()
    row = []
    for chk in ("pyright", "mypy", "ty", "pyrefly"):
        cfg = Path(__file__).resolve().parent / "conformance" / f"cfg_time_{s.parent.name}_{s.name}"
        if chk == "mypy":  # cold cache each time
            import shutil
            shutil.rmtree(cfg / ".mypy_cache", ignore_errors=True)
        t0 = time.time()
        r = static.checkers(s, [f], cfg, {chk})
        errs = sum(1 for d in r.get(chk, []) if d[2] == "error")
        row.append(f"{chk} {time.time() - t0:5.1f}s ({errs} err)")
    print(f"{s.parent.name}/{s.name}: " + "; ".join(row))
