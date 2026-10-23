"""Build a tacit_next package copy (E8 runtime files) whose _column.pyi is the derived facade.

python make_pkg.py OUT_DIR [gen_derived args...]
Patch vs E8: predicates (filter / join on= / tc.check) accept Column[bool | None], because the
derived facade types comparisons on nullable columns as nullable (SQL three-valued logic).
"""
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
E8 = HERE.parents[1] / "e8-prototype" / "src" / "tacit_next"
out = Path(sys.argv[1]) / "tacit_next"
out.mkdir(parents=True, exist_ok=True)
for f in E8.iterdir():
    if f.suffix == ".py" or f.name == "py.typed":
        shutil.copy(f, out / f.name)
for name, old, new in [
    ("_frame.py", "def filter(self, *predicates: Column[bool]) -> Self:", "def filter(self, *predicates: Column[bool | None]) -> Self:"),
    ("_join.py", "on: Callable[[L, R], Column[bool]]", "on: Callable[[L, R], Column[bool | None]]"),
    ("_fields.py", "def check(fn: Callable[[Column[Any]], Column[bool]]", "def check(fn: Callable[[Column[Any]], Column[bool | None]]"),
]:
    p = out / name
    s = p.read_text()
    assert old in s, (name, old)
    p.write_text(s.replace(old, new))
subprocess.run([sys.executable, str(HERE / "gen_derived.py"), sys.argv[1], *sys.argv[2:]], check=True)
