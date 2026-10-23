"""Make E13's generated ibis Table mirror owner-aware for unbound refs (`Orders.amount`).

    uv run --frozen python e14-column-refs/tools/gen_ref_stub.py

Input : tools/base/_ibis_api.pyi  (E13 `gen_table_stub.py --returns getattr` output, unchanged)
Output: src/tacit_thin/_ibis_api.pyi

Mechanical rewrites (a post-pass; folding them into gen_table_stub.py is ~30 lines):
  1. `TableAPI` and `GroupedTable` become generic in the frame schema `S_co` (covariant);
     the getattr result class `Table` is `TableAPI[Any]` (refs of any owner: unchecked);
  2. every PARAMETER position that accepts ibis `Deferred` also accepts
     `Ref[S_co, Any] | RefScalar[S_co, Any]` -- owner-checked, since Ref is contravariant in
     its owner and S_co is covariant, `Ref[S_co, ...]` in a parameter is variance-correct;
  3. params ibis types `_ir.Value` without Deferred (group_by **key_exprs, agg **kwargs) get refs too;
  4. `group_by` returns `GroupedTable[S_co]`; its (untyped in ibis) `agg`/`aggregate` take
     `RefScalar[S_co, Any]` / ibis values / Deferred -- a bare non-reduced ref there is an error;
  5. join methods get a method type parameter `R` for the right frame's schema and the
     key-pair form `(left_key, right_key)` is typed `(Ref[S_co, Any], Ref[R, Any])`.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE / "base" / "_ibis_api.pyi"
OUT = HERE.parent / "src" / "tacit_thin" / "_ibis_api.pyi"
REFS = "Ref[S_co, Any] | RefScalar[S_co, Any]"

stats: Counter[str] = Counter()


def params_of(line: str) -> tuple[str, str, str]:
    """split `def name(params) -> ret: ...` into (head, params, tail) on the outermost parens."""
    i = line.index("(")
    depth = 0
    for j in range(i, len(line)):
        depth += line[j] == "("
        depth -= line[j] == ")"
        if depth == 0:
            return line[: i + 1], line[i + 1 : j], line[j:]
    raise ValueError(line)


def rewrite_tableapi(line: str) -> str:
    if "def " not in line:
        return line
    head, params, tail = params_of(line)
    name = re.search(r"def (\w+)", head)[1]  # type: ignore[index]
    n = len(re.findall(r"\b(?:_ir\.)?Deferred\b", params))
    stats["deferred->+refs"] += n
    if name.endswith("join") and "tuple[" in params:
        # key pair: left element -> left schema, right element -> right schema
        params = params.replace(
            "tuple[str | (_ir.Column | Column[Any]) | _ir.Deferred, str | (_ir.Column | Column[Any]) | _ir.Deferred]",
            "tuple[str | (_ir.Column | Column[Any]) | _ir.Deferred | Ref[S_co, Any], "
            "str | (_ir.Column | Column[Any]) | _ir.Deferred | Ref[R, Any]]",
        )
        params = params.replace("right: TableAPI | _ir.Table", "right: TableAPI[R] | _ir.Table", 1)
        head = head.replace(f"def {name}(", f"def {name}[R](")
        stats["join: R + key pair"] += 1
    params = re.sub(r"(?<![\w.])Deferred\b(?! \| Ref)", f"Deferred | {REFS}", params)
    # pyrefly treats ibis's `*Column` classes (Unknown base via the Jupyter mixin) as accepting
    # ANY argument, which swallows wrong-owner refs; `Value` is not affected and is what ibis binds.
    params, n2 = re.subn(r"\b_ir\.(Boolean)?Column\b", lambda m: f"_ir.{m[1] or ''}Value", params)
    stats["pyrefly: _ir.Column -> _ir.Value"] += n2
    # E13 PARAM_PATCHES used `s.Selector`, which pyright resolves to Unknown (accepts anything)
    stats["s.Selector -> Selector"] += params.count("s.Selector")
    params = params.replace("s.Selector", "Selector")
    # ...and a union STARTING with Selector is Unknown on pyright (its metaclass defines `__or__`,
    # so `Selector | X` is evaluated as a value expression): `t.select(12345)` was accepted.
    stats["pyright: leading `Selector |` reordered"] += params.count("*exprs: Selector | _ir.Value")
    params = params.replace("*exprs: Selector | _ir.Value", "*exprs: _ir.Value | Selector")
    if name == "group_by":
        params = params.replace("**key_exprs: str | _ir.Value", f"**key_exprs: str | _ir.Value | {REFS}")
        stats["group_by kwargs"] += 1
    if name in ("agg", "aggregate"):
        params = params.replace("**kwargs: _ir.Value", f"**kwargs: _ir.Value | {REFS}")
        stats["agg kwargs"] += 1
    tail = tail.replace("-> GroupedTable:", "-> GroupedTable[S_co]:")
    return head + params + tail


AGG = "_ir.Scalar | Scalar[Any] | Deferred | RefScalar[S_co, Any]"
GROUPED = {
    # ibis leaves GroupedTable.agg untyped; a non-reduced column there is a runtime error, so
    # metrics are typed as scalars (ibis or facade), refs reductions, or Deferred.
    "agg": f"    def agg(self, *metrics: {AGG} | Sequence[{AGG}], **kwds: {AGG}) -> Table: ...",
    "aggregate": f"    def aggregate(self, *metrics: {AGG} | Sequence[{AGG}], **kwds: {AGG}) -> Table: ...",
"mutate": f"    def mutate(self, *exprs: _ir.Value | Sequence[_ir.Value] | {REFS}, **kwexprs: _ir.Value | {REFS}) -> Table: ...",
}


def main() -> None:
    src = BASE.read_text().splitlines()
    out: list[str] = []
    section = ""
    for ln in src:
        if m := re.match(r"class (\w+)", ln):
            section = m[1]
            ln = {"class TableAPI:": "class TableAPI(Generic[S_co]):",
                  "class GroupedTable:": "class GroupedTable(Generic[S_co]):",
                  "class Table(TableAPI):": "class Table(TableAPI[Any]):"}.get(ln, ln)
        elif section == "TableAPI":
            ln = rewrite_tableapi(ln)
        elif section == "GroupedTable" and (m := re.match(r"    def (\w+)\(", ln)) and m[1] in GROUPED:
            ln = GROUPED[m[1]]
            stats[f"GroupedTable.{m[1]} typed"] += 1
        elif section == "GroupedTable":
            ln = ln.replace("-> GroupedTable:", "-> GroupedTable[S_co]:")
        out.append(ln)
    text = "\n".join(out) + "\n"
    text = text.replace(
        "from ._column import Column, Scalar",
        "from typing import Generic, TypeVar\nfrom ._column import Column, Ref, RefScalar, Scalar\n\n"
        'S_co = TypeVar("S_co", covariant=True)',
        1,
    )
    text = text.replace("# GENERATED by tools/gen_table_stub.py", "# GENERATED by e14 tools/gen_ref_stub.py over tools/gen_table_stub.py", 1)
    OUT.write_text(text)
    print(f"wrote {OUT}")
    for k, v in sorted(stats.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
