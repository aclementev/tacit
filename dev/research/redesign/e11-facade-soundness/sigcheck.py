"""Compare the E8 facade's hand-written parameter lists with ibis's (names, kinds, defaults).

python sigcheck.py FACADE.pyi  -> out/sigcheck.txt
A facade param list that drops an ibis parameter (FP when users pass it), renames it, or makes a
keyword-capable parameter positional-only (FP for keyword calls) is a mechanical drift the
derived generator cannot have.
"""
import ast
import inspect
import sys
from pathlib import Path

import ibis.expr.types as ir

FAM = {"bool": "Boolean", "int": "Integer", "float": "Floating", "Decimal": "Decimal", "str": "String",
       "datetime": "Timestamp", "date": "Date", "time": "Time", "_datetime": "Timestamp", "_date": "Date", "_time": "Time"}

tree = ast.parse(Path(sys.argv[1]).read_text())
rows = set()
for cls in tree.body:
    if not isinstance(cls, ast.ClassDef) or cls.name not in ("Column", "Scalar"):
        continue
    for fn in cls.body:
        if not isinstance(fn, ast.FunctionDef) or fn.name.startswith("__"):
            continue
        a = fn.args
        selfann = (a.posonlyargs + a.args)[0].annotation
        fams = []
        if selfann is None:
            fams = ["int", "str"]
        else:
            txt = ast.unparse(selfann)
            fams = [f for f in FAM if f"[{f}" in txt or f" {f}" in txt and not f.startswith("_")][:1] or ["int"]
        for fam in fams:
            ic = getattr(ir, FAM[fam] + cls.name, None)
            if ic is None or not hasattr(ic, fn.name):
                continue
            ip = list(inspect.signature(getattr(ic, fn.name)).parameters.values())[1:]
            fac_pos = [x.arg for x in a.posonlyargs[1:]] if a.posonlyargs else []
            fac_all = [x.arg for x in (a.posonlyargs + a.args)[1:]] + [x.arg for x in a.kwonlyargs]
            ib_names = [p.name for p in ip if p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)]
            missing = [n for n in ib_names if n not in fac_all]
            extra = [n for n in fac_all if n not in ib_names]
            posonly_narrow = [n for n in fac_pos if any(p.name == n and p.kind == p.POSITIONAL_OR_KEYWORD for p in ip)]
            if missing or extra or posonly_narrow:
                rows.add(f"{cls.name}.{fn.name:<14} [{fam}] ibis{inspect.signature(getattr(ic, fn.name))}\n"
                         f"      missing-in-facade={missing} renamed/extra={extra} positional-only-but-ibis-allows-keyword={posonly_narrow}")
out = "\n".join(sorted(rows))
Path(Path(__file__).resolve().parent, "out", "sigcheck.txt").write_text(out + "\n")
print(out)
print(f"\n{len(rows)} facade methods whose parameters drift from ibis")
