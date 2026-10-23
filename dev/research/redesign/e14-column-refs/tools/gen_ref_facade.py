"""Derive the unbound-reference facade (`Ref[O, T]` / `RefScalar[O, T]`) from the Column facade.

    uv run --frozen python e14-column-refs/tools/gen_ref_facade.py

Input : tools/base/_column.pyi   (E13's facade, copied unchanged)
Output: src/tacit_thin/_column.pyi = base facade, with
  * `Column.__get__` split into two overloads:
        class access    `Orders.amount`   -> Ref[Orders, T]   (owner captured from `owner: type[O]`)
        instance access `df.c.amount`     -> Column[T]        (obj must be a bound SchemaBase)
  * `Column.__set__` widened to accept refs (dataclass_transform -> `build(...)` kwargs)
  * two NEW classes, produced by a purely textual rewrite of the Column / Scalar bodies:
        Column[X] -> Ref[O_contra, X]      Scalar[X] -> RefScalar[O_contra, X]
    O_contra is the OWNER schema, contravariant: a parent-schema ref is usable on a child
    frame (Ref[Parent, T] <: Ref[Child, T]). Methods whose result is not an expression
    (value_counts/topk -> Table) are dropped: they cannot work on an unbound ref.
The same rewrite applies unchanged to E11's derived 8.3k-line facade (see --base).
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE / "base" / "_column.pyi"
OUT = HERE.parent / "src" / "tacit_thin" / "_column.pyi"

GET_OLD = "    def __get__(self, obj: object, owner: Any, /) -> Self: ..."
GET_NEW = """    @overload
    def __get__(self, obj: None, owner: type[_O], /) -> Ref[_O, T_co]: ...
    @overload
    def __get__(self, obj: SchemaBase, owner: Any, /) -> Self: ..."""
SET_RE = re.compile(r"(    def __set__\(self, obj: object, value: )(.*?)(, /\) -> None: \.\.\.)")


def split_classes(text: str) -> dict[str, tuple[int, int]]:
    """class name -> (start line, end line) of each top-level class block."""
    lines = text.splitlines()
    starts = [(i, m[1]) for i, ln in enumerate(lines) if (m := re.match(r"class (\w+)\(", ln))]
    out = {}
    for k, (i, name) in enumerate(starts):
        j = i + 1
        while j < len(lines) and (not lines[j] or lines[j].startswith((" ", "\t"))):
            j += 1
        out[name] = (i, j)
    return out


def rewrite_body(body: list[str], cls: str) -> tuple[list[str], int, int]:
    """Column/Scalar body -> Ref/RefScalar body. Returns (lines, kept methods, dropped methods)."""
    out: list[str] = []
    kept = dropped = 0
    i = 0
    in_doc = False
    while i < len(body):
        ln = body[i]
        s = ln.strip()
        if s.startswith('"""'):
            in_doc = not (s.count('"""') == 2) and not in_doc
            i += 1
            continue
        if in_doc:
            if '"""' in s:
                in_doc = False
            i += 1
            continue
        if s == "@overload":
            nxt = body[i + 1]
            if skip(nxt):
                dropped += 1
                i += 2
                continue
            out += [ln, sub(nxt)]
            kept += 1
            i += 2
            continue
        if s.startswith("def "):
            if skip(ln):
                dropped += 1
            else:
                out.append(sub(ln))
                kept += 1
            i += 1
            continue
        if s.startswith("#") or not s:
            out.append(ln)
        i += 1
    return out, kept, dropped


def skip(ln: str) -> bool:
    if re.search(r"def __(get|set)__", ln):
        return True
    ret = ln.split("->")[-1]
    return bool(re.search(r"\b(Table|ir\.\w+)\b", ret))  # not an expression of this facade


def sub(ln: str) -> str:
    ln = re.sub(r"\bColumn\[", "Ref[O_contra, ", ln)
    ln = re.sub(r"\bScalar\[", "RefScalar[O_contra, ", ln)
    return ln


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", type=Path, default=BASE)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    text = a.base.read_text()
    assert GET_OLD in text, "unexpected Column.__get__ in the base facade"
    text = text.replace(GET_OLD, GET_NEW, 1)
    text, n = SET_RE.subn(lambda m: m[1] + m[2] + " | Ref[Any, T_co] | RefScalar[Any, T_co]" + m[3], text, count=1)
    assert n == 1
    text = text.replace('T_co = TypeVar("T_co", covariant=True)',
                        'T_co = TypeVar("T_co", covariant=True)\nO_contra = TypeVar("O_contra", contravariant=True)\n'
                        '_O = TypeVar("_O")', 1)
    blocks = split_classes(text)
    lines = text.splitlines()
    new: list[str] = ["", "", "class SchemaBase:",
                      '    """Marker base of bound column namespaces (`df.c`): instance access yields Column[T]."""', ""]
    report = []
    for src, dst, doc in (("Column", "Ref", "An UNBOUND typed column reference: `Orders.amount` is `Ref[Orders, float]`.\n\n"
                           "    Resolved against the frame it is used on (like ibis `_`). `O` is the owner schema\n"
                           "    (contravariant: parent-schema refs are accepted by child-schema frames)."),
                          ("Scalar", "RefScalar", "An unbound reduction over a ref: `Orders.amount.sum()`.")):
        i, j = blocks[src]
        body, kept, dropped = rewrite_body(lines[i + 1 : j], src)
        new += [f"class {dst}(Generic[O_contra, T_co]):", f'    """{doc}"""', "", *body, ""]
        report.append(f"{dst}: {kept} members kept, {dropped} dropped")
    # module-level helpers stay bound-only; insert the new classes right after Scalar
    _, end = blocks["Scalar"]
    text = "\n".join(lines[:end] + new + lines[end:]) + "\n"
    text = text.replace("# GENERATED by tools/gen_facade.py", "# GENERATED by e14 tools/gen_ref_facade.py from E13's gen_facade.py output", 1)
    a.out.write_text(text)
    print(f"wrote {a.out} ({text.count(chr(10))} lines)")
    for r in report:
        print("  " + r)


if __name__ == "__main__":
    main()
