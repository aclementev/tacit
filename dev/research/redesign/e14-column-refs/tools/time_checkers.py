"""Time the four checkers on FILES with a given package root (src or out/derived_src)."""

import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parent
src = (HERE / sys.argv[1]).resolve()
files = [str((HERE / f).resolve()) for f in sys.argv[2:]]
extra = sorted({str(Path(f).parent) for f in files})
with tempfile.TemporaryDirectory() as d:
    pc = Path(d) / "pyrightconfig.json"
    pc.write_text(f'{{"pythonVersion": "3.13", "venvPath": "{ROOT}", "venv": ".venv", "extraPaths": ["{src}"], '
                  '"typeCheckingMode": "standard", "reportMissingModuleSource": false}')
    mi = Path(d) / "mypy.ini"
    mi.write_text((HERE / "mypy.ini").read_text().replace("$MYPY_CONFIG_FILE_DIR/src", str(src))
                  .replace("$MYPY_CONFIG_FILE_DIR/.mypy_cache", str(Path(d) / "cache")))
    cmds = {
        "pyright": ["pyright", "-p", str(pc), *files],
        "mypy": ["mypy", "--config-file", str(mi), *files],
        "ty": ["ty", "check", "--python", ".venv", "--extra-search-path", str(src),
               *[a for e in extra for a in ("--extra-search-path", e)], *files],
        "pyrefly": ["pyrefly", "check", "--python-interpreter-path", ".venv/bin/python", "--search-path", str(src),
                    *[a for e in extra for a in ("--search-path", e)], *files],
    }
    for n, c in cmds.items():
        t = time.time()
        p = subprocess.run(["uv", "run", "--frozen", *c], cwd=ROOT, capture_output=True, text=True)
        out = (p.stdout + p.stderr).strip().splitlines()
        print(f"{sys.argv[1]:18} {n:8} {time.time() - t:6.1f}s  {out[-1][:80] if out else ''}")
