"""Parse a generated _column.pyi: which method names apply to which value family.

A facade method applies to family F if one of its overloads has no `self`
annotation, or a `self: Column[X]` whose X accepts F (bool<:int<:float,
datetime<:date, `| None` is the nullable variant).
"""

from __future__ import annotations

import ast
from pathlib import Path

FAMS = ["bool", "int", "float", "Decimal", "str", "datetime", "date", "time"]
ALIAS = {"_date": "date", "_datetime": "datetime", "_time": "time"}
SUPER = {  # what a declared element type accepts (PEP 484 promotions + subclassing)
    "bool": {"bool"}, "int": {"int", "bool"}, "float": {"float", "int", "bool"},
    "Decimal": {"Decimal"}, "str": {"str"}, "datetime": {"datetime"}, "date": {"date", "datetime"},
    "time": {"time"}, "V": set(FAMS), "Any": set(FAMS), "object": set(FAMS),
}


def _elems(node: ast.expr) -> set[str]:
    if isinstance(node, ast.BinOp):
        return _elems(node.left) | _elems(node.right)
    if isinstance(node, ast.Name):
        return {ALIAS.get(node.id, node.id)}
    if isinstance(node, ast.Constant) and node.value is None:
        return {"None"}
    return {"?"}


def accepts(self_ann: ast.expr | None) -> set[tuple[str, bool]]:
    """(family, nullable) pairs a self annotation accepts."""
    if self_ann is None:
        return {(f, n) for f in FAMS for n in (False, True)}
    assert isinstance(self_ann, ast.Subscript), ast.dump(self_ann)
    el = _elems(self_ann.slice)
    nullable_ok = "None" in el or bool(el & {"V", "Any"})
    fams = set().union(*(SUPER.get(e, set()) for e in el if e != "None"))
    return {(f, n) for f in fams for n in (False, True) if (not n or nullable_ok)}


def parse(path: Path) -> dict[str, dict[str, set[tuple[str, bool]]]]:
    """{class: {method: {(family, nullable)}}}"""
    tree = ast.parse(path.read_text())
    out: dict[str, dict[str, set[tuple[str, bool]]]] = {}
    for cls in tree.body:
        if not isinstance(cls, ast.ClassDef):
            continue
        meths: dict[str, set[tuple[str, bool]]] = {}
        for fn in cls.body:
            if isinstance(fn, ast.FunctionDef):
                a = fn.args.posonlyargs + fn.args.args
                self_ann = a[0].annotation if a else None
                meths.setdefault(fn.name, set()).update(accepts(self_ann))
        out[cls.name] = meths
    return out


if __name__ == "__main__":
    import sys
    p = parse(Path(sys.argv[1]))
    for c, m in p.items():
        print(c, len(m), sorted(m))
