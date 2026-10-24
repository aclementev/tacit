"""Generate `src/tacit_thin/_ibis_api.pyi`: a CLEAN static mirror of ibis's Table API.

    uv run --frozen python e13-thin-frame/tools/gen_table_stub.py [--returns mirror|ibis]

What it does (mechanically, from the installed ibis):

* walks the runtime MRO of `ir.Table` and `GroupedTable`, collecting every public
  member plus a whitelist of dunders, and copies each signature with `inspect`
  (annotations stay the *source strings*: ibis uses `from __future__ import annotations`);
  `typing.get_overloads` recovers `@overload` variants, the AST recovers `@deprecated`;
* OMITS `__getattr__` / `__dir__` (the reason typos are invisible on `ir.Table`) and
  everything private; emits the classes with NO base (clean MRO on every checker);
* resolves every name an annotation uses against the defining module's imports
  (top level and `if TYPE_CHECKING:`), and emits those imports;
* rewrites annotations:
    - `Table` / `ir.Table` in a return -> `Table` (this mirror, `--returns mirror`)
      or `ir.Table` (`--returns ibis`); in a parameter -> `Table | ir.Table`;
      same for `GroupedTable`;
    - in parameters, ibis's concrete column types are widened to also accept tacit's
      facade: `ir.XxxColumn` -> `| Column[...]`, `ir.BooleanValue` -> `| Column[bool | None]`,
      `ir.XxxScalar` -> `| Scalar[...]` (E8 FP #1/#2: the facade is an `ir.Value`, not an
      `ir.Column`, so ibis APIs typed with `ir.Column` reject it);
* the only hand-written input is HAND_FIXES below (reported in the header).
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import inspect
import re
import sys
import textwrap
import typing
from collections import Counter
from pathlib import Path
from types import FunctionType, ModuleType

import ibis
import ibis.expr.types as ir
from ibis.expr.types.groupby import GroupedTable

OUT = Path(__file__).resolve().parents[1] / "src_common" / "tacit_thin" / "_ibis_api.pyi"
FACADE = "tacit"  # E17: --facade tacit (L3: Column[T]) | mirror (L2: _ibis_cols classes) | none (L1)

CLASSES: dict[str, type] = {"Table": ir.Table, "GroupedTable": GroupedTable}
# dunders worth exposing statically (operators / protocols users hit)
DUNDERS = {"__getitem__", "__contains__", "__len__", "__iter__", "__bool__", "__hash__", "__array__",
           "__dataframe__", "__arrow_c_stream__", "__repr__"}
# never copied: these are what makes ir.Table untypable, or construction internals
OMIT = {"__getattr__", "__dir__", "__init__", "__coerce__", "__reduce__", "__init_subclass__"}
# GroupedTable inherits ibis's `Concrete` dataclass machinery; not user API
OMIT_MEMBERS = {"GroupedTable": {"args", "argnames", "copy", "table", "groupings", "orderings", "havings"}}

FACADE_ELEM = {"Boolean": "bool | None", "Integer": "int | None", "Floating": "float | None",
               "String": "str | None", "Timestamp": "_datetime | None", "Date": "_date | None"}

# Hand fixes: (class, member) -> replacement source. Kept tiny on purpose; each is reported.
HAND_FIXES: dict[tuple[str, str], str] = {}
# Upstream annotation bugs patched in the mirror (param-level; each is reported, and each is a
# dev/contributions candidate). (class, member-glob, param) -> extra union members.
PARAM_PATCHES: dict[tuple[str, str, str], str] = {
    # ibis 12: `t.join(s, t.a == s.a)` is rejected by every checker (only a *Sequence* of predicates
    # is annotated), though it is the documented common case.
    ("Table", "*join", "predicates"): "_ir.BooleanValue | Column[bool | None] | Deferred",
    # ibis 12: `t.mutate(one=1)` (literal broadcast) is rejected (E2 Issue 2).
    ("Table", "mutate", "mutations"): "int | float | bool | None",
    # ibis 12: `t.select(s.numeric())` is rejected by every checker (selectors are documented input).
    ("Table", "select", "exprs"): "s.Selector",
    ("Table", "projection", "exprs"): "s.Selector",
}

MIRROR_NAMES = {f"{f}{k}" for f in ["", "Numeric", "Boolean", "Integer", "Floating", "Decimal", "String",
                                       "Timestamp", "Date", "Time"] for k in ("Column", "Scalar")}
stats: Counter[str] = Counter()
hand: list[str] = []
patched: set[str] = set()
unresolved: set[str] = set()


def module_imports(mod: ModuleType) -> dict[str, str]:
    """name -> import statement that binds it, from top level and `if TYPE_CHECKING:` blocks."""
    tree = ast.parse(inspect.getsource(mod))
    out: dict[str, str] = {}

    def visit(body: list[ast.stmt]) -> None:
        for n in body:
            if isinstance(n, ast.If) and "TYPE_CHECKING" in ast.unparse(n.test):
                visit(n.body)
            elif isinstance(n, ast.Import):
                for a in n.names:
                    out[a.asname or a.name.split(".")[0]] = (
                        f"import {a.name} as {a.asname}" if a.asname else f"import {a.name}"
                    )
            elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
                for a in n.names:
                    nm = a.asname or a.name
                    out[nm] = f"from {n.module} import {a.name}" + (f" as {a.asname}" if a.asname else "")

    visit(tree.body)
    # module-level classes/aliases referenced by annotations (e.g. `Value` in relations.py is imported;
    # but some names are defined in the module itself)
    for n in tree.body:
        if isinstance(n, ast.ClassDef | ast.FunctionDef) and n.name not in out:
            out[n.name] = f"from {mod.__name__} import {n.name}"
    return out


def deprecations(cls: type) -> dict[str, str]:
    """member -> deprecation message, from `@deprecated(as_of=..., instead=...)` decorators (AST)."""
    out: dict[str, str] = {}
    for c in cls.__mro__:
        try:
            tree = ast.parse(textwrap.dedent(inspect.getsource(c)))
        except (OSError, TypeError):
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.FunctionDef):
                for d in n.decorator_list:
                    s = ast.unparse(d)
                    if s.startswith(("deprecated(", "util.deprecated(")):
                        as_of = re.search(r"as_of='([^']*)'", s)
                        instead = re.search(r"instead='([^']*)'", s)
                        out.setdefault(n.name, f"deprecated since ibis {as_of[1] if as_of else '?'}: "
                                       f"{instead[1] if instead else ''}")
    return out


class Rewriter(ast.NodeTransformer):
    def __init__(self, position: str, ret_mode: str, imports: dict[str, str], needed: dict[str, str]) -> None:
        self.position = position  # "param" | "return"
        self.ret_mode = ret_mode
        self.imports = imports
        self.needed = needed

    def _self_ref(self, name: str) -> ast.expr | None:
        if name not in CLASSES:
            return None
        stats[f"rewrite:{self.position}:{name}"] += 1
        if self.position == "return":
            src = f"_ir.{name}" if self.ret_mode == "ibis" else name
        else:
            src = f"{'TableAPI' if name == 'Table' else name} | _ir.{name}"
        return ast.parse(src, mode="eval").body

    def _widen(self, node: ast.expr, short: str) -> ast.expr:
        if self.position != "param" or FACADE == "none":
            return node
        if FACADE == "mirror":  # L2: mirror classes subclass the real *Value* classes, not Column/Scalar
            m = re.fullmatch(r"(\w*?)(Column|Scalar)", short)
            if not m or short not in MIRROR_NAMES:
                return node
            stats["rewrite:param:mirror-widening"] += 1
            return ast.parse(f"{ast.unparse(node)} | _cols.{short}", mode="eval").body
        m = re.fullmatch(r"(\w*?)(Column|Value|Scalar)", short)
        if not m or short in ("Value",):
            return node
        prefix, kind = m[1], m[2]
        if kind == "Value" and prefix != "Boolean":
            return node  # the facade IS an ir.Value; only BooleanValue needs widening
        elem = FACADE_ELEM.get(prefix, "Any")
        facade = {"Column": [f"Column[{elem}]"], "Scalar": [f"Scalar[{elem}]"],
                  "Value": [f"Column[{elem}]", f"Scalar[{elem}]"]}[kind]
        stats["rewrite:param:facade-widening"] += 1
        return ast.parse(" | ".join([ast.unparse(node), *facade]), mode="eval").body

    def visit_Attribute(self, node: ast.Attribute) -> ast.expr:
        if isinstance(node.value, ast.Name) and node.value.id == "ir":
            if (r := self._self_ref(node.attr)) is not None:
                return r
            self.needed["_ir"] = "import ibis.expr.types as _ir"
            return self._widen(ast.Attribute(ast.Name("_ir"), node.attr), node.attr)
        root = node
        while isinstance(root, ast.Attribute):
            root = root.value
        if isinstance(root, ast.Name):
            self._need(root.id)
        return node

    def visit_Name(self, node: ast.Name) -> ast.expr:
        if (r := self._self_ref(node.id)) is not None:
            return r
        if node.id in ("ir",):
            self.needed["_ir"] = "import ibis.expr.types as _ir"
            return ast.Name("_ir")
        self._need(node.id)
        if node.id in ("Column", "Scalar"):  # an ibis name that would clash with the facade
            return node
        imp = self.imports.get(node.id, "")
        if imp.startswith("from ibis.expr.types") and node.id != "Value":
            return self._widen(node, node.id)
        return node

    def _need(self, name: str) -> None:
        if name in dir(__builtins__) or name in ("None",) or name in CLASSES:
            return
        if name in self.imports:
            self.needed[name] = self.imports[name]
        elif hasattr(typing, name):
            self.needed[name] = f"from typing import {name}"
        else:
            unresolved.add(name)


def ann(s: object, position: str, ret_mode: str, imports: dict[str, str], needed: dict[str, str]) -> str:
    if s is inspect.Parameter.empty:
        stats[f"unannotated:{position}"] += 1
        return ""
    if not isinstance(s, str):
        s = inspect.formatannotation(s)
    tree = ast.parse(s, mode="eval")
    tree = Rewriter(position, ret_mode, imports, needed).visit(tree)
    return ast.unparse(tree)


def render_sig(fn: FunctionType, ret_mode: str, imports: dict[str, str], needed: dict[str, str], *, drop_self: bool,
               where: tuple[str, str] = ("", "")) -> str:
    sig = inspect.signature(fn, eval_str=False)
    parts: list[str] = []
    seen_kwonly = False
    params = list(sig.parameters.values())
    for i, p in enumerate(params):
        if i == 0 and drop_self:
            parts.append("self")
            continue
        a = ann(p.annotation, "param", ret_mode, imports, needed)
        for (pc, pm, pp), extra in PARAM_PATCHES.items():
            if pc == where[0] and pp == p.name and fnmatch.fnmatch(where[1], pm) and a:
                a = f"{extra} | {a}"
                patched.add(f"{where[0]}.{where[1]}({p.name})")
        a = f": {a}" if a else ""
        default = " = ..." if p.default is not inspect.Parameter.empty else ""
        if p.kind is p.VAR_POSITIONAL:
            parts.append(f"*{p.name}{a}")
            seen_kwonly = True
        elif p.kind is p.VAR_KEYWORD:
            parts.append(f"**{p.name}{a}")
        else:
            if p.kind is p.KEYWORD_ONLY and not seen_kwonly:
                parts.append("*")
                seen_kwonly = True
            parts.append(f"{p.name}{a}{default}")
        if p.kind is p.POSITIONAL_ONLY and (i + 1 == len(params) or params[i + 1].kind is not p.POSITIONAL_ONLY):
            parts.append("/")
    r = ann(sig.return_annotation, "return", ret_mode, imports, needed)
    return f"({', '.join(parts)})" + (f" -> {r}" if r else "")


def gen_class(name: str, cls: type, ret_mode: str, needed: dict[str, str]) -> list[str]:
    emitted = "TableAPI" if name == "Table" and ret_mode != "mirror" else name
    lines = [f"class {emitted}:",
             f'    """Static mirror of `{cls.__module__}.{cls.__qualname__}` minus `__getattr__` (generated)."""', ""]
    deps = deprecations(cls)
    members = sorted(n for n in dir(cls) if (not n.startswith("_") or n in DUNDERS) and n not in OMIT
                     and n not in OMIT_MEMBERS.get(name, set()))
    for m in members:
        if (name, m) in HAND_FIXES:
            lines.append(HAND_FIXES[(name, m)])
            hand.append(f"{name}.{m}")
            continue
        owner = next(c for c in cls.__mro__ if m in c.__dict__)
        raw = owner.__dict__[m]
        mod = sys.modules[owner.__module__]
        imports = module_imports(mod)
        if raw is None:  # e.g. __array_ufunc__ = None
            continue
        if isinstance(raw, property):
            r = ann(inspect.signature(raw.fget, eval_str=False).return_annotation, "return", ret_mode, imports, needed)
            lines += ["    @property", f"    def {m}(self) -> {r or 'Any'}: ..."]
            stats["property"] += 1
            continue
        if isinstance(raw, classmethod | staticmethod):
            stats["skipped:classmethod"] += 1
            continue
        fn = inspect.unwrap(raw) if callable(raw) else None
        if not isinstance(fn, FunctionType):
            hand.append(f"{name}.{m}: non-function member {type(raw).__name__} skipped")
            continue
        if fn.__module__ != owner.__module__:  # e.g. join methods built by a factory: resolve in its module
            imports = module_imports(sys.modules[fn.__module__])
        overloads = typing.get_overloads(fn)
        if m in deps:
            needed["deprecated"] = "from warnings import deprecated"
            lines.append(f"    @deprecated({deps[m]!r})")
        if overloads:
            for ov in overloads:
                lines += ["    @overload", f"    def {m}{render_sig(ov, ret_mode, imports, needed, drop_self=True, where=(name, m))}: ..."]
            needed["overload"] = "from typing import overload"
            stats["overloaded"] += 1
        else:
            lines.append(f"    def {m}{render_sig(fn, ret_mode, imports, needed, drop_self=True, where=(name, m))}: ...")
        stats["method"] += 1
        if m != fn.__name__:
            stats["alias"] += 1
    return lines + [""]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--returns", choices=["mirror", "getattr", "ibis"], default="getattr",
                    help="what ibis methods on a frame return: mirror = clean Table without __getattr__; "
                         "getattr = clean Table WITH a typed __getattr__ (Frame's base TableAPI has none); "
                         "ibis = the real ir.Table")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--facade", choices=["tacit", "mirror", "none"], default="tacit")
    args = ap.parse_args()
    global FACADE
    FACADE = args.facade
    needed: dict[str, str] = {}
    body: list[str] = []
    for name, cls in CLASSES.items():
        body += gen_class(name, cls, args.returns, needed)
    if args.returns == "mirror":
        body += ["# the frame base and the result type are the same clean class", "TableAPI = Table", ""]
    elif args.returns == "getattr":
        body += ["class Table(TableAPI):",
                 '    """What ibis methods on a frame return: clean MRO, but `t.any_name` is an ibis column (as in ibis)."""',
                 "    def __getattr__(self, name: str, /) -> _ir.Column: ...", ""]
    else:
        body += ["# ibis methods on a frame return the real ibis Table", "Table = _ir.Table", ""]
    needed.pop("Column", None)
    needed.pop("Scalar", None)
    header = [
        f"# GENERATED by tools/gen_table_stub.py --returns {args.returns} --facade {FACADE} from ibis {ibis.__version__} -- do not edit.",
        '"""Clean static mirror of ibis Table / GroupedTable (no __getattr__, no base class)."""',
        "",
        "from datetime import date as _date, datetime as _datetime",
        "from typing import Any",
        *sorted(set(needed.values()) - {"from typing import Any", "import ibis.expr.types as _ir",
                                         "import ibis.selectors as s", "from ibis.common.deferred import Deferred"}),
        "import ibis.expr.types as _ir",
        "import ibis.selectors as s  # used by PARAM_PATCHES",
        "from ibis.common.deferred import Deferred  # used by PARAM_PATCHES",
        "from ._column import Column, Scalar",
        *(["from . import _ibis_cols as _cols"] if FACADE == "mirror" else []),
        "",
    ]
    if unresolved:
        header.append("# unresolved names (typed as Any): " + ", ".join(sorted(unresolved)))
        header += [f"{n} = Any" for n in sorted(unresolved)]
    text = "\n".join(header + [""] + body)
    args.out.write_text(text)
    n_lines = text.count("\n") + 1
    print(f"wrote {args.out} ({n_lines} lines, returns={args.returns})")
    for k, v in sorted(stats.items()):
        print(f"  {k}: {v}")
    print(f"  hand fixes: {hand or 'none'}")
    print(f"  upstream-bug patches applied: {len(patched)} params: {sorted(patched)}")
    print(f"  unresolved names: {sorted(unresolved) or 'none'}")


if __name__ == "__main__":
    main()
