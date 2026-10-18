"""Prototype mypy plugin: makes `X = Base.pick(...)` / `.drop` / `.rename` / `.extend`
define a real class X for mypy (pyright, ty and pyrefly have no plugin API).

    [mypy]
    plugins = mypy_tacit_plugin.py

Only module-level `Name = SchemaClass.<op>(...)` assignments are handled
(mypy's dynamic-class hook). Field types are copied from the base's TypeInfo.
"""

from __future__ import annotations

from collections.abc import Callable

from mypy.nodes import (
    GDEF,
    MDEF,
    ARG_NAMED,
    ARG_POS,
    Block,
    ClassDef,
    MemberExpr,
    RefExpr,
    StrExpr,
    SymbolTable,
    SymbolTableNode,
    TypeInfo,
    Var,
)
from mypy.plugin import DynamicClassDefContext, Plugin
from mypy.exprtotype import expr_to_unanalyzed_type
from mypy.types import Instance, Type

SCHEMA = "tx.Schema"
OPS = {"pick", "drop", "rename", "extend"}


def _columns(info: TypeInfo) -> dict[str, Type | None]:
    """Instance-level annotated attributes along the MRO (base-most first)."""
    cols: dict[str, Type | None] = {}
    for base in reversed(info.mro):
        if base.fullname in ("builtins.object", SCHEMA):
            continue
        for name, sym in base.names.items():
            node = sym.node
            if isinstance(node, Var) and not node.is_classvar and not name.startswith("_") and node.is_inferred is False:
                cols[name] = node.type
    return cols


def _hook(ctx: DynamicClassDefContext) -> None:
    callee = ctx.call.callee
    assert isinstance(callee, MemberExpr) and isinstance(callee.expr, RefExpr)
    base = callee.expr.node
    if not isinstance(base, TypeInfo) or not base.has_base(SCHEMA):
        return
    schema_sym = ctx.api.lookup_fully_qualified_or_none(SCHEMA)
    if schema_sym is None or not isinstance(schema_sym.node, TypeInfo):
        ctx.api.defer()
        return
    src = _columns(base)
    if any(t is None for t in src.values()):  # base not fully analysed yet
        ctx.api.defer()
        return

    op = callee.name
    pos = [a for a, k in zip(ctx.call.args, ctx.call.arg_kinds) if k == ARG_POS]
    kw = {n: a for a, k, n in zip(ctx.call.args, ctx.call.arg_kinds, ctx.call.arg_names) if k == ARG_NAMED and n}

    def names() -> list[str]:
        out = []
        for a in pos:
            if not isinstance(a, StrExpr):
                ctx.api.fail(f"{op}() column names must be string literals", a)
                continue
            if a.value not in src:
                ctx.api.fail(f'"{base.name}" has no column "{a.value}"', a)
            out.append(a.value)
        return out

    parent = schema_sym.node
    if op == "pick":
        wanted = names()
        cols = {n: src[n] for n in wanted if n in src}
    elif op == "drop":
        dropped = set(names())
        cols = {n: t for n, t in src.items() if n not in dropped}
    elif op == "rename":
        cols = {}
        mapping: dict[str, str] = {}
        for old, new in kw.items():
            if old not in src:
                ctx.api.fail(f'"{base.name}" has no column "{old}"', new)
            if not isinstance(new, StrExpr):
                ctx.api.fail("rename() targets must be string literals", new)
                continue
            mapping[old] = new.value
        cols = {mapping.get(n, n): t for n, t in src.items()}
    else:  # extend: subclass the base so X <: Base nominally
        parent = base
        cols = {}
        for name, expr in kw.items():
            t = ctx.api.anal_type(expr_to_unanalyzed_type(expr, ctx.api.options))
            if t is None:
                ctx.api.defer()
                return
            cols[name] = t

    classdef = ClassDef(ctx.name, Block([]))
    classdef.fullname = ctx.api.qualified_name(ctx.name)
    info = TypeInfo(SymbolTable(), classdef, ctx.api.cur_mod_id)
    classdef.info = info
    info.bases = [Instance(parent, [])]
    info.calculate_metaclass_type()
    info.mro = [info, *parent.mro]
    for name, typ in cols.items():
        var = Var(name, typ)
        var.info = info
        var._fullname = f"{info.fullname}.{name}"
        var.is_inferred = False
        info.names[name] = SymbolTableNode(MDEF, var)
    ctx.api.add_symbol_table_node(ctx.name, SymbolTableNode(GDEF, info))


class TacitPlugin(Plugin):
    def get_dynamic_class_hook(self, fullname: str) -> Callable[[DynamicClassDefContext], None] | None:
        if fullname.rsplit(".", 1)[-1] in OPS:
            return _hook
        return None


def plugin(version: str) -> type[Plugin]:
    return TacitPlugin
