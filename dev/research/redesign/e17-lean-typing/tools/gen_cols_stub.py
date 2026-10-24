"""L2: generate `overlays/l2/tacit_thin/_ibis_cols.pyi`, a CLEAN mirror of ibis's column/scalar classes.

    uv run --frozen python e17-lean-typing/tools/gen_cols_stub.py

Same technique as E13's `gen_table_stub.py`: inspect + copy ibis's own annotation strings.
NO execution probing and NO nullability. What is mechanical:

* the classes: `Value/Column/Scalar`, `Numeric*`, and `<F>Value/<F>Column/<F>Scalar` for the eight
  value families tacit declares (bool, int, float, Decimal, str, datetime, date, time);
* the MRO is cleaned: ibis's `Column` has the conditional Jupyter mixin as a base (an Unknown
  base on ty/pyrefly, E2), so mirror columns subclass the real ibis *Value* class of their family
  instead (`FloatingColumn(..., ir.FloatingValue)`), which is clean on every checker and keeps
  mirror values assignable to ibis APIs typed with Value classes; scalars subclass the real scalar;
* every public member + operator dunder (except Expr's, inherited from the real class) is copied
  with `inspect.signature`; in RETURNS ibis class names become the mirror classes, in PARAMETERS
  they stay the real ibis classes (`| mirror` for Column/Scalar classes, which mirrors don't subclass);
* one rewrite rule: on a Column receiver a returned `<F>Value` is `<F>Column` (unary methods and
  `column OP x` are columns at runtime; ibis annotates the Value supertype, E4);
* each family class carries a phantom marker `_Fam[T]` (T = the Python type tacit declares), so the
  `Column[T]` descriptor's `__set__` can check the family of `build(...)` arguments without
  overloads (pyright/mypy ignore an overloaded `__set__`). Numeric families do not inherit the
  mirror `Numeric*` classes (one marker per class), whose members are copied in instead.

What is hand-written: PATCHES below, the short list of upstream annotation bugs (each reported).
"""

from __future__ import annotations

import ast
import inspect
import sys
import textwrap
import typing
from collections import Counter
from pathlib import Path
from types import FunctionType, ModuleType

import ibis
import ibis.expr.types as ir

OUT = Path(__file__).resolve().parents[1] / "overlays" / "l2" / "tacit_thin" / "_ibis_cols.pyi"

FAMS = {"Boolean": "bool", "Integer": "int", "Floating": "float", "Decimal": "Decimal", "String": "str",
        "Timestamp": "_datetime", "Date": "_date", "Time": "_time"}
NUMERIC_FAMS = {"Boolean", "Integer", "Floating", "Decimal"}  # ibis: BooleanValue subclasses NumericValue
KINDS = ("Value", "Column", "Scalar")
NAMES = ["Value", "Column", "Scalar"] + [f"{f}{k}" for f in ["Numeric", *FAMS] for k in KINDS]
MIRRORED: dict[str, type] = {n: getattr(ir, n) for n in NAMES}
SKIP_OWNERS = {"Expr", "Immutable", "Coercible", "Abstract", "FixedTextJupyterMixin", "JupyterMixin", "object"}
DUNDERS = {"__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__", "__add__", "__radd__", "__sub__", "__rsub__",
           "__mul__", "__rmul__", "__truediv__", "__rtruediv__", "__floordiv__", "__rfloordiv__", "__mod__",
           "__rmod__", "__pow__", "__rpow__", "__neg__", "__invert__", "__and__", "__rand__", "__or__", "__ror__",
           "__xor__", "__rxor__", "__lshift__", "__rlshift__", "__rshift__", "__rrshift__", "__getitem__",
           "__contains__", "__div__", "__rdiv__", "__hash__"}
OMIT = {"__init__", "__coerce__", "__getattr__", "__dir__", "__array__", "__deferred_repr__", "__pyarrow_result__",
        "__pandas_result__", "__polars_result__", "__rich_console__", "__interactive_rich_console__"}

# ---------------------------------------------------------------------------------------------
# PATCHES: the hand-written list of upstream annotation bugs, in ibis-source spelling (bare ibis
# class names; they go through the same rewriter, so `BooleanValue` returns become `BooleanColumn`
# on column receivers). Keyed by family ("Numeric" = the mirror Numeric* classes) and member.

_NUM = "int | float | Decimal"
CMP = {  # comparison / bound / fill operand, as in ibis PR #11966 (InferrableTo<F> | <F>Value | Deferred)
    **{f: f"{_NUM} | NumericValue" for f in ("Numeric", "Integer", "Floating", "Decimal")},
    "Boolean": "bool | BooleanValue", "String": "str | StringValue",
    "Timestamp": "_datetime | str | TimestampValue", "Date": "_date | str | DateValue",
    "Time": "_time | str | TimeValue",
}
_LIT = "bool | int | float | Decimal | str | _date | _datetime"
P_SIG: dict[tuple[str, str], list[str]] = {}  # (family, member) -> signature(s); several = overloads
P_RET: dict[tuple[str, str], str] = {}  # (family, member) -> return annotation only (params from ibis)
for f, cmp in CMP.items():
    for op in ("__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__"):  # 1. literals in comparisons (E3)
        P_SIG[f, op] = [f"(self, other: {cmp} | Deferred) -> BooleanValue"]
    for m in ("isin", "notin"):  # 2. isin(["a", "b"]) (E4)
        P_SIG[f, m] = [f"(self, values: Iterable[{cmp}] | ArrayValue | Column, /) -> BooleanValue"]
    P_SIG[f, "between"] = [f"(self, lower: {cmp}, upper: {cmp}) -> BooleanValue"]  # 3. literal bounds
    for m in ("fill_null", "fillna"):  # 4. fill_null(0): ibis types the fill as `Scalar`
        P_SIG[f, m] = [f"(self, fill_value: {cmp}, /) -> Self"]
    for m in ("min", "max", "first", "last", "arbitrary", "mode", "argmin", "argmax"):  # 5. same-family reductions
        P_RET[f, m] = f"{f}Scalar"
    for m in ("cummin", "cummax", "lag", "lead", "nth"):  # ... and window functions (ibis: bare `Column`)
        P_RET[f, m] = "Self"
P_SIG["Boolean", "ifelse"] = [  # 6. ifelse("y", "n"): ibis wants ir.Value branches and returns untyped Value
    "(self, true_expr: str | StringValue, false_expr: str | StringValue, /) -> StringValue",
    "(self, true_expr: int | IntegerValue, false_expr: int | IntegerValue, /) -> IntegerValue",
    "(self, true_expr: float | NumericValue, false_expr: float | NumericValue, /) -> FloatingValue",
    f"(self, true_expr: Value | {_LIT}, false_expr: Value | {_LIT}, /) -> Value",
]
for f, s in (("Integer", "IntegerScalar"), ("Boolean", "IntegerScalar"), ("Floating", "FloatingScalar"),
             ("Decimal", "DecimalScalar")):  # 7. sum/mean/cumsum/std/var keep a family (ibis: NumericScalar)
    P_RET[f, "sum"] = s
    P_RET[f, "cumsum"] = s.replace("Scalar", "Column")
for f in ("Integer", "Boolean", "Floating"):
    for m in ("mean", "std", "var"):
        P_RET[f, m] = "FloatingScalar"
_ARITH = ("__add__", "__radd__", "__sub__", "__rsub__", "__mul__", "__rmul__", "__mod__", "__rmod__",
          "add", "radd", "sub", "rsub", "mul", "rmul", "mod", "rmod")
for m in _ARITH:  # 8. int OP int stays int (ibis: NumericValue); Decimal OP int/Decimal stays Decimal
    P_SIG["Integer", m] = ["(self, other: int | IntegerValue) -> IntegerValue",
                           "(self, other: float | FloatingValue) -> FloatingValue",
                           "(self, other: Decimal | DecimalValue) -> DecimalValue",
                           f"(self, other: {_NUM} | NumericValue | Deferred) -> NumericValue"]
    P_SIG["Decimal", m] = ["(self, other: int | Decimal | IntegerValue | DecimalValue) -> DecimalValue",
                           f"(self, other: {_NUM} | NumericValue | Deferred) -> NumericValue"]
for f in ("Integer", "Decimal"):
    for m in ("__truediv__", "__rtruediv__", "div", "rdiv", "__div__", "__rdiv__"):
        P_SIG[f, m] = [f"(self, other: {_NUM} | NumericValue | Deferred) -> FloatingValue"]

PATCH_HEADER = ["from collections.abc import Iterable", "from decimal import Decimal",
                "from datetime import date as _date, datetime as _datetime, time as _time",
                "from ibis.common.deferred import Deferred", "from typing import Self, overload"]

# module-level aliases ibis defines under TYPE_CHECKING (assignments, not imports)
ALIASES = {"Number": "int | float | Decimal"}


class _Alias(ast.NodeTransformer):
    def visit_Name(self, node: ast.Name) -> ast.expr:
        return ast.parse(ALIASES[node.id], mode="eval").body if node.id in ALIASES else node


stats: Counter[str] = Counter()
used_patches: set[str] = set()
unresolved: set[str] = set()


def family(name: str) -> tuple[str, str]:
    for k in KINDS:
        if name.endswith(k):
            return name[: -len(k)], k
    raise ValueError(name)


def module_imports(mod: ModuleType) -> dict[str, str]:
    tree = ast.parse(inspect.getsource(mod))
    out: dict[str, str] = {}

    def visit(body: list[ast.stmt]) -> None:
        for n in body:
            if isinstance(n, ast.If) and "TYPE_CHECKING" in ast.unparse(n.test):
                visit(n.body)
            elif isinstance(n, ast.Import):
                for a in n.names:
                    out[a.asname or a.name.split(".")[0]] = (
                        f"import {a.name} as {a.asname}" if a.asname else f"import {a.name}")
            elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
                for a in n.names:
                    out[a.asname or a.name] = f"from {n.module} import {a.name}" + (f" as {a.asname}" if a.asname else "")

    visit(tree.body)
    for n in tree.body:
        if isinstance(n, ast.ClassDef | ast.FunctionDef) and n.name not in out:
            out[n.name] = f"from {mod.__name__} import {n.name}"
    return out


class Rewriter(ast.NodeTransformer):
    def __init__(self, position: str, receiver: str, imports: dict[str, str], needed: dict[str, str]) -> None:
        self.position, self.receiver, self.imports, self.needed = position, receiver, imports, needed

    def _cls(self, name: str) -> ast.expr | None:
        if name not in MIRRORED and not hasattr(ir, name):
            return None
        if name not in MIRRORED:  # an ibis class we do not mirror (ArrayValue, Table, IntervalValue, ...)
            return ast.parse(f"_ir.{name}", mode="eval").body
        if self.position == "return":
            fam, kind = family(name)
            if kind == "Value" and family(self.receiver)[1] == "Column" and f"{fam}Column" in MIRRORED:
                stats["rule:value->column"] += 1
                name = f"{fam}Column"
            return ast.Name(name)
        fam, kind = family(name)
        src = f"_ir.{name}" if kind == "Value" else f"_ir.{name} | {name}"
        return ast.parse(src, mode="eval").body

    def visit_Attribute(self, node: ast.Attribute) -> ast.expr:
        if isinstance(node.value, ast.Name) and node.value.id == "ir":
            return self._cls(node.attr) or ast.parse(f"_ir.{node.attr}", mode="eval").body
        root = node
        while isinstance(root, ast.Attribute):
            root = root.value
        if isinstance(root, ast.Name):
            self._need(root.id)
        return node

    def visit_Name(self, node: ast.Name) -> ast.expr:
        imp = self.imports.get(node.id, "")
        if node.id in MIRRORED or (imp.startswith("from ibis.expr.types") and hasattr(ir, node.id)):
            if (r := self._cls(node.id)) is not None:
                return r
        self._need(node.id)
        return node

    def _need(self, name: str) -> None:
        if name in dir(__builtins__) or name in ("None", "Self", "Deferred", "Iterable", "Decimal", "_date",
                                                  "_datetime", "_time"):
            return
        if name in self.imports:
            self.needed[name] = self.imports[name]
        elif hasattr(typing, name):
            self.needed[name] = f"from typing import {name}"
        else:
            unresolved.add(name)


def ann(s: object, position: str, receiver: str, imports: dict[str, str], needed: dict[str, str]) -> str:
    if s is inspect.Parameter.empty:
        return ""
    if not isinstance(s, str):
        s = inspect.formatannotation(s)
    s = s.replace("ibis.Deferred", "Deferred")
    s = ALIASES.get(s, s) if s in ALIASES else ast.unparse(_Alias().visit(ast.parse(s, mode="eval")))
    return ast.unparse(Rewriter(position, receiver, imports, needed).visit(ast.parse(s, mode="eval")))


def render(fn: FunctionType, receiver: str, imports: dict[str, str], needed: dict[str, str], ret: str | None = None) -> str:
    sig = inspect.signature(fn, eval_str=False)
    parts: list[str] = []
    seen_kw = False
    params = list(sig.parameters.values())
    for i, p in enumerate(params):
        if i == 0:
            parts.append("self")
            continue
        a = ann(p.annotation, "param", receiver, imports, needed)
        a = f": {a}" if a else ""
        d = " = ..." if p.default is not inspect.Parameter.empty else ""
        if p.kind is p.VAR_POSITIONAL:
            parts.append(f"*{p.name}{a}")
            seen_kw = True
        elif p.kind is p.VAR_KEYWORD:
            parts.append(f"**{p.name}{a}")
        else:
            if p.kind is p.KEYWORD_ONLY and not seen_kw:
                parts.append("*")
                seen_kw = True
            parts.append(f"{p.name}{a}{d}")
        if p.kind is p.POSITIONAL_ONLY and (i + 1 == len(params) or params[i + 1].kind is not p.POSITIONAL_ONLY):
            parts.append("/")
    r = ann(ret if ret is not None else sig.return_annotation, "return", receiver, imports, needed)
    return f"({', '.join(parts)})" + (f" -> {r}" if r else "")


def patch_render(src: str, receiver: str, needed: dict[str, str]) -> str:
    """A patch signature in ibis spelling -> rewritten like a copied one."""
    tree = ast.parse(f"def f{src}: ...").body[0]
    assert isinstance(tree, ast.FunctionDef)
    imports = {n: f"from ibis.expr.types import {n}" for n in dir(ir) if n[0].isupper()}
    for a in [*tree.args.posonlyargs, *tree.args.args, *tree.args.kwonlyargs]:
        if a.annotation is not None:
            a.annotation = Rewriter("param", receiver, imports, needed).visit(a.annotation)
    if tree.returns is not None:
        tree.returns = Rewriter("return", receiver, imports, needed).visit(tree.returns)
    return f"({ast.unparse(tree.args)})" + (f" -> {ast.unparse(tree.returns)}" if tree.returns is not None else "")


def members(cls: type) -> list[str]:
    out = []
    for n in sorted(dir(cls)):
        if n in OMIT or (n.startswith("_") and n not in DUNDERS):
            continue
        owner = next(c for c in cls.__mro__ if n in c.__dict__)
        if owner.__name__ in SKIP_OWNERS or not owner.__module__.startswith("ibis.expr.types"):
            continue
        out.append(n)
    return out


def rendered_members(name: str, needed: dict[str, str]) -> dict[str, list[str]]:
    """member -> emitted lines (receiver-aware), for mirror class `name` (flattened over its real MRO)."""
    cls = MIRRORED[name]
    fam, _ = family(name)
    out: dict[str, list[str]] = {}
    for m in members(cls):
        owner = next(c for c in cls.__mro__ if m in c.__dict__)
        raw = owner.__dict__[m]
        if raw is None or isinstance(raw, classmethod | staticmethod):
            continue
        if isinstance(raw, property):
            r = ann(inspect.signature(raw.fget, eval_str=False).return_annotation, "return", name,
                    module_imports(sys.modules[owner.__module__]), needed)
            out[m] = ["    @property", f"    def {m}(self) -> {r or 'Any'}: ..."]
            continue
        fn = inspect.unwrap(raw) if callable(raw) else None
        if not isinstance(fn, FunctionType):
            stats["skipped:non-function"] += 1
            continue
        imports = module_imports(sys.modules[fn.__module__])
        if (fam, m) in P_SIG:
            sigs = P_SIG[fam, m]
            used_patches.add(f"{fam}.{m}")
            if len(sigs) == 1:
                out[m] = [f"    def {m}{patch_render(sigs[0], name, needed)}: ..."]
            else:
                out[m] = [x for s in sigs for x in ("    @overload", f"    def {m}{patch_render(s, name, needed)}: ...")]
            continue
        ret = P_RET.get((fam, m))
        if ret is not None:
            used_patches.add(f"{fam}.{m} (return)")
        ovs = typing.get_overloads(fn)
        if ovs:
            out[m] = [x for ov in ovs for x in ("    @overload", f"    def {m}{render(ov, name, imports, needed, ret)}: ...")]
        else:
            out[m] = [f"    def {m}{render(fn, name, imports, needed, ret)}: ..."]
    return out


def mirror_bases(name: str) -> list[str]:
    cls = MIRRORED[name]
    fam, kind = family(name)
    bases = [b.__name__ for b in cls.__bases__ if b.__name__ in MIRRORED
             and not (b.__name__.startswith("Numeric") and fam != "Numeric")]
    if name == "Value":
        return []
    if kind != "Value" and f"{fam}Value" not in bases:
        bases.append(f"{fam}Value")
    if kind != "Value" and name != kind and not any(family(b)[1] == kind for b in bases):
        bases.insert(0, kind)  # e.g. IntegerColumn: Column (generic) instead of NumericColumn
    if kind == "Value" and not bases:
        bases = ["Value"]  # numeric families (not under the mirror NumericValue), temporal (mixin bases)
    return bases


def real_base(name: str) -> str:
    fam, kind = family(name)
    return f"_ir.{fam}Value" if kind == "Column" else f"_ir.{name}"


def main() -> None:
    needed: dict[str, str] = {}
    rendered = {n: rendered_members(n, needed) for n in NAMES}
    bases = {n: mirror_bases(n) for n in NAMES}
    # compute mirror MROs with dummy classes, then emit only members that differ from what is inherited
    dummies: dict[str, type] = {}
    for n in NAMES:
        dummies[n] = type(n, tuple(dummies[b] for b in bases[n]), {})
    body: list[str] = []
    total_members = 0
    for n in NAMES:
        fam, kind = family(n)
        mro = [c.__name__ for c in dummies[n].__mro__[1:-1]]
        emitted: list[str] = []
        for m, lines in rendered[n].items():
            inherited = next((rendered[b][m] for b in mro if m in rendered[b]), None)
            if inherited != lines:
                emitted += lines
                total_members += 1
        marker = []
        if fam in FAMS:
            marker = [f"_Fam[{FAMS[fam]}]"]
        elif fam == "Numeric":
            marker = ["_Fam[float]"]  # an unknown numeric result is accepted into float columns
        bs = ", ".join([*bases[n], real_base(n), *marker])
        body += [f"class {n}({bs}):", *(emitted or ["    ..."]), ""]
        stats[f"class:{kind}"] += 1
    header = [
        f"# GENERATED by tools/gen_cols_stub.py from ibis {ibis.__version__} -- do not edit.",
        '"""L2: clean static mirror of ibis column/scalar classes (+ PATCHES for upstream annotation bugs)."""',
        "",
        "from typing import Any, Generic, TypeVar",
        *PATCH_HEADER,
        *sorted(set(needed.values()) - {"from typing import Any", "from typing import overload",
                                        "from typing import Self"}),
        "import ibis.expr.types as _ir",
        "",
        '_T_co = TypeVar("_T_co", covariant=True)',
        "",
        "class _Fam(Generic[_T_co]):",
        '    """Phantom marker: the value family as the Python type tacit declares (`Column[float]`)."""',
        "",
    ]
    if unresolved:
        header += ["# unresolved names (typed as Any): " + ", ".join(sorted(unresolved))]
        header += [f"{u} = Any" for u in sorted(unresolved)]
    text = "\n".join(header + [""] + body)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text)
    print(f"wrote {OUT} ({text.count(chr(10)) + 1} lines, {len(NAMES)} classes, {total_members} member definitions)")
    for k, v in sorted(stats.items()):
        print(f"  {k}: {v}")
    print(f"  patch sites used: {len(used_patches)}")
    print(f"  unresolved names: {sorted(unresolved) or 'none'}")


if __name__ == "__main__":
    main()
