"""Derived facade generator: build tacit's Column[T]/Scalar[T] stub FROM ibis.

python gen_derived.py OUT_DIR [--fallback ibis|any|none] [--no-backend]

What is mechanical (read from the installed ibis):
  * which methods/operators exist on which dtype family, for Column and Scalar
    (dir() of ir.IntegerColumn, ir.StringScalar, ...);
  * parameter names, kinds (positional-only / keyword-only / *args), defaults,
    and parameter types (ibis's own annotations, with ibis expression classes
    mapped onto Column[T] / Scalar[T]);
  * the result container (Column / Scalar / Table / other ibis class) and the
    result value family, by CALLING the method on a sample column of each dtype
    and reading the result's dtype -- ibis's own dtype rules, not ours;
  * which operand families each operator accepts, and which casts the backend
    can bind (the probe executes every candidate on an empty duckdb table).

What stays hand-written (HAND_* tables below, ~60 lines):
  * nullability rules (ibis's dtype.nullable is not propagated, so it can't be read);
  * sample arguments for methods whose required parameters can't be synthesised;
  * signatures that need a TypeVar (ifelse) or solve T (fill_null), and the
    descriptor protocol / helper functions (copied from the E8 stub).

Fallback for methods the probe can't type (--fallback):
  ibis : keep the method, self-restricted to the families that have it, typed with
         ibis's own declared return annotation (default; never removes access)
  any  : same, but returning Any
  none : omit (E8 behaviour: attribute error)
"""

from __future__ import annotations

import ast
import inspect
import re
import sys
import warnings
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import ibis
import ibis.expr.types as ir

warnings.filterwarnings("ignore")

FAMS = ["bool", "int", "float", "Decimal", "str", "datetime", "date", "time"]  # narrow-first overload order
IBIS_FAM = {"bool": "Boolean", "int": "Integer", "float": "Floating", "Decimal": "Decimal", "str": "String",
            "datetime": "Timestamp", "date": "Date", "time": "Time"}
DTYPE = {"bool": "boolean", "int": "int64", "float": "float64", "Decimal": "decimal(12, 2)", "str": "string",
         "datetime": "timestamp", "date": "date", "time": "time"}
PYLIT = {"bool": True, "int": 1, "float": 1.5, "Decimal": Decimal("1.5"), "str": "2024-01-01",
         "datetime": datetime(2024, 1, 2, 3), "date": date(2024, 1, 2), "time": time(1, 2)}
# Expression plumbing / deprecated aliases: not part of the typed column surface (reachable via ir.Value).
SKIP = {
    "compile", "execute", "to_pandas", "to_polars", "to_pyarrow", "to_pyarrow_batches", "to_csv", "to_parquet",
    "to_delta", "to_json", "to_torch", "to_list", "to_sql", "visualize", "pipe", "op", "equals", "get_backend",
    "unbind", "has_name", "get_name", "type", "as_table", "as_scalar", "preview", "to_parquet_dir", "to_xlsx",
    "to_pandas_batches", "to_array", "to_frame", "fillna", "case", "identical_to",
    # handled by HAND templates below
    "fill_null", "ifelse", "cast", "try_cast", "name", "over", "asc", "desc",
}

# ---------------------------------------------------------------------------------------------
# HAND 1: nullability. ibis marks almost every result `nullable=True`, so this can't be derived.
#   default (element-wise AND reductions): nullable iff the receiver or an expression argument is nullable.
#   Reductions of a non-null column are non-null for every GROUP BY group (groups are never empty);
#   only a global aggregate over empty input returns NULL -- documented, checked at runtime by parse.
#   HAND_ALWAYS_NULL: may produce NULL from non-null input (n<2 statistics, window edges, failed casts).
HAND_NEVER_NULL = {"isnull", "notnull", "count", "nunique", "approx_nunique", "rank", "dense_rank", "percent_rank",
                   "cume_dist", "ntile", "typeof", "hash", "isnan", "isinf"}
HAND_ALWAYS_NULL = {"try_cast", "nullif", "lag", "lead", "nth", "std", "var", "cov", "corr", "kurtosis", "arbitrary",
                    "first", "last"}
# HAND 2: probe arguments where synthesis from the annotation would not produce a valid call.
HAND_ARGS: dict[str, tuple[str, ...]] = {
    "truncate": ('"D"',), "re_extract": ('"(a)"', "1"), "re_replace": ('"a"', '"b"'), "replace": ('"a"', '"b"'),
    "strftime": ('"%Y"',), "as_timestamp": ('"%Y"',), "as_date": ('"%Y"',), "as_time": ('"%H"',),
    "delta": ("x", ), "bucket": ("[1, 2]",), "quantile": ("0.5",), "approx_quantile": ("0.5",),
    "translate": ('"a"', '"b"'), "clip": ("lower=1",), "find_in_set": ('["a"]',), "levenshtein": ('"a"',), "lpad": ("3",),
    "rpad": ("3",), "repeat": ("2",), "convert_base": ("10", "2"), "atan2": ("x",), "corr": ("x",),
    "cov": ("x",), "join": ('["a"]',), "as_interval": ('"s"',),
}
HAND_KWARGS: dict[str, str] = {"delta": 'unit="day"'}

# ---------------------------------------------------------------------------------------------
# Annotation mapping: ibis expression classes -> facade types (mechanical).
VALUE_FAM = {"BooleanValue": "bool", "IntegerValue": "int", "NumericValue": "float", "FloatingValue": "float",
             "DecimalValue": "Decimal", "StringValue": "str", "TimestampValue": "datetime", "DateValue": "date",
             "TimeValue": "time", "BooleanColumn": "bool", "IntegerColumn": "int", "StringColumn": "str"}
DT_FAM = {"Timestamp": "datetime", "String": "str", "Date": "date", "Time": "time", "Boolean": "bool",
          "Int64": "int", "Integer": "int", "Float64": "float", "Floating": "float", "Decimal": "Decimal"}
KEEP = {"str", "int", "float", "bool", "bytes", "None", "Any", "Sequence", "Iterable", "Mapping", "Callable",
        "Literal", "Decimal"}


class AnnMapper(ast.NodeTransformer):
    def __init__(self, fam: str, nul: str) -> None:
        self.fam, self.nul = fam, nul

    def fac(self, f: str, col_only: bool = False) -> ast.expr:
        lit = "" if col_only else f"{f} | "
        src = f"{lit}Column[{f}{self.nul}]" + ("" if col_only else f" | Scalar[{f}{self.nul}]")
        return ast.parse(src, mode="eval").body

    def visit_Name(self, n: ast.Name) -> ast.AST:
        return self.named(n.id, n)

    def visit_Attribute(self, n: ast.Attribute) -> ast.AST:
        full = ast.unparse(n)
        if full in ("datetime.datetime", "datetime.date", "datetime.time"):
            return ast.Name(full.split(".")[1])
        return self.named(n.attr, n)

    def named(self, name: str, node: ast.AST) -> ast.AST:
        if name in ("Value", "Scalar", "Deferred_self"):
            return self.fac(self.fam)
        if name == "Column":
            return self.fac(self.fam, col_only=True)
        if name in VALUE_FAM:
            return self.fac(VALUE_FAM[name])
        if name == "Number":
            return ast.parse("float | Decimal", mode="eval").body
        if name in KEEP or name in ("datetime", "date", "time", "timedelta"):
            return ast.Name(name)
        if name == "Deferred":
            return ast.Name("_Drop")
        if hasattr(ir, name):
            return ast.parse(f"ir.{name}", mode="eval").body
        return ast.Name("Any")

    def visit_Subscript(self, n: ast.Subscript) -> ast.AST:
        base = ast.unparse(n.value)
        if base in ("Value", "ir.Value"):  # Value[dt.Timestamp]
            inner = ast.unparse(n.slice).split(".")[-1]
            return self.fac(DT_FAM.get(inner, self.fam))
        if base == "Literal":
            return n
        return self.generic_visit(n)


def _flatten(node: ast.expr) -> list[str]:
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _flatten(node.left) + _flatten(node.right)
    return [ast.unparse(node)]


def map_ann(ann: object, fam: str, nul: str, mapper: type[ast.NodeTransformer] | None = None) -> str | None:
    if ann is inspect.Parameter.empty:
        return None
    if not isinstance(ann, str):
        ann = getattr(ann, "__name__", "Any")
    try:
        tree = ast.parse(ann, mode="eval")
    except SyntaxError:
        return "Any"
    m = (mapper or AnnMapper)(fam, nul)
    body = m.visit(tree).body
    parts = [p for p in dict.fromkeys(_flatten(body)) if p != "_Drop"]
    out = " | ".join(parts) or "Any"
    return out.replace("_Drop", "Any")


class IbisRetMapper(AnnMapper):
    """Fallback return types: keep ibis's own classes (ir.X), never the facade."""

    def named(self, name: str, node: ast.AST) -> ast.AST:
        if name == "Self":
            return ast.parse(f"ir.{IBIS_FAM[self.fam]}{self.nul}", mode="eval").body
        if name in KEEP or name in ("datetime", "date", "time", "timedelta"):
            return ast.Name(name)
        if hasattr(ir, name):
            return ast.parse(f"ir.{name}", mode="eval").body
        return ast.Name("Any")

    def visit_Subscript(self, n: ast.Subscript) -> ast.AST:
        return ast.parse("ir.Value", mode="eval").body if ast.unparse(n.value).endswith("Value") else self.generic_visit(n)


def sig_params(fn, fam: str, nul: str, drop_first: bool = True, variant: str | None = None) -> str:
    """Render ibis's parameter list with mapped annotations (names, kinds, defaults preserved)."""
    sig = inspect.signature(fn)
    out, saw_kwonly, saw_posonly = [], False, False
    params = list(sig.parameters.values())[1 if drop_first else 0:]
    if variant:
        how, pname = variant.split(":")
        if how == "drop":
            params = [p for p in params if p.name != pname]
        else:
            params = [p.replace(default=p.empty) if p.name == pname else p for p in params]
    for p in params:
        a = map_ann(p.annotation, fam, nul)
        ann = f": {a}" if a else ""
        if p.kind == p.POSITIONAL_ONLY:
            saw_posonly = True
        elif saw_posonly:
            out.append("/")
            saw_posonly = False
        if p.kind == p.KEYWORD_ONLY and not saw_kwonly:
            out.append("*")
            saw_kwonly = True
        if p.kind == p.VAR_POSITIONAL:
            out.append(f"*{p.name}{ann}")
            saw_kwonly = True
        elif p.kind == p.VAR_KEYWORD:
            out.append(f"**{p.name}{ann}")
        else:
            out.append(f"{p.name}{ann}{' = ...' if p.default is not p.empty else ''}")
    if saw_posonly:
        out.append("/")
    return "".join(", " + s for s in out)


LITSRC = {"bool": "True", "int": "1", "float": "1.5", "Decimal": 'Decimal("1.5")', "str": '"2024-01-01"',
          "datetime": "datetime(2024, 1, 2, 3)", "date": "date(2024, 1, 2)", "time": "time(1, 2)"}

# ---------------------------------------------------------------------------------------------
# Probing ibis (and the duckdb binder) for result kinds and families.
def family_of(d) -> str | None:
    for test, name in [("is_boolean", "bool"), ("is_integer", "int"), ("is_floating", "float"),
                       ("is_decimal", "Decimal"), ("is_string", "str"), ("is_timestamp", "datetime"),
                       ("is_date", "date"), ("is_time", "time")]:
        if getattr(d, test)():
            return name
    return None


DATA_ERR = re.compile(r"Could not convert string|invalid timestamp field|out of range|Could not parse", re.I)


class Prober:
    def __init__(self, backend: bool) -> None:
        import pyarrow as pa

        sch = ibis.schema({f"c_{f}": "!" + DTYPE[f] for f in FAMS} | {"g": "!string"})
        # one row of typical values: type errors that duckdb raises only when a value flows
        # (e.g. CAST(BIGINT AS DATE)) surface; value-dependent errors are filtered by DATA_ERR
        row = {f"c_{f}": [PYLIT[f]] for f in FAMS} | {"g": ["a"]}
        self.t = ibis.memtable(pa.table({k: pa.array(row[k], type=v.to_pyarrow()) for k, v in sch.items()}), schema=sch)
        self.con = ibis.duckdb.connect() if backend else None

    def recv(self, fam: str, container: str):
        c = self.t[f"c_{fam}"]
        return c if container == "Column" else c.max()

    def check(self, e) -> tuple[str, str | None] | None:
        """-> (kind, fam-or-ibis-class) if ibis builds it and the backend binds it, else None."""
        if isinstance(e, ir.Table):
            kind, res = "Table", None
        elif isinstance(e, ir.Value):
            kind = "Column" if isinstance(e, ir.Column) else "Scalar"
            res = family_of(e.type()) or f"ir.{type(e).__name__}"
        else:
            return None
        if self.con is not None:
            try:
                if kind == "Table":
                    self.con.execute(e.limit(0))
                elif kind == "Column":
                    self.con.execute(self.t.select(r=e))
                elif e.op().relations:
                    self.con.execute(self.t.aggregate(r=e))
                else:
                    self.con.execute(e)
            except Exception as ex:  # noqa: BLE001
                if not DATA_ERR.search(str(ex)):
                    return None
        return kind, res

    def call(self, fam: str, container: str, src: str):
        x = self.recv(fam, container)
        ns = {"x": x, "Decimal": Decimal, "datetime": datetime, "date": date, "time": time, "ibis": ibis}
        try:
            return self.check(eval(src, ns))
        except Exception:  # noqa: BLE001
            return None


def synth_args(name: str, fn, fam: str) -> list[str]:
    """Candidate argument lists (tried in order): HAND_ARGS, then synthesised from annotations."""
    if name in HAND_ARGS:
        a = ", ".join(HAND_ARGS[name])
        return [a + (", " + HAND_KWARGS[name] if name in HAND_KWARGS else "")]
    per_param: list[list[str]] = []
    for p in list(inspect.signature(fn).parameters.values())[1:]:
        if p.default is not p.empty or p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        a = str(p.annotation)
        cands: list[str] = []
        m = re.search(r"Literal\[\s*'([^']+)'", a)
        if m:
            cands.append(f'"{m.group(1)}"')
        if "Value" in a or a in ("Scalar", "Column") or "Iterable" in a:
            cands.append("x")
        if "Interval" in a or "timedelta" in a:
            cands.append("ibis.interval(days=1)")
        if "Iterable" in a or "Sequence" in a:
            cands.append(f"[{LITSRC[fam]}]")
        if a.startswith(("str", "'str")) or "StringValue" in a:
            cands.append('"a"')
        if "int" in a or "IntegerValue" in a:
            cands.append("1")
        if "float" in a or "Numeric" in a:
            cands.append("0.5")
        if "bool" in a:
            cands.append("True")
        if not cands:
            return []
        per_param.append([f"{p.name}={v}" if p.kind == p.KEYWORD_ONLY else v for v in cands])
    if not per_param:
        return [""]
    # same candidate index for every parameter, then the first candidate everywhere else
    n = max(len(c) for c in per_param)
    return [", ".join(c[min(i, len(c) - 1)] for c in per_param) for i in range(n)]


# ---------------------------------------------------------------------------------------------
def ret_type(container: str, res: tuple[str, str | None], nullable: str) -> str:
    kind, fam = res
    if kind == "Table":
        return "Table"
    if fam is None or fam.startswith("ir."):
        return fam or "Any"
    return f"{kind}[{fam}{nullable}]"


def null_rule(name: str, recv_container: str, res_kind: str) -> str:
    if name in HAND_NEVER_NULL:
        return "never"
    if name in HAND_ALWAYS_NULL:
        return "always"
    return "propagate"


def _optional_positional(fn) -> str | None:
    for p in list(inspect.signature(fn).parameters.values())[1:]:
        if p.default is not p.empty and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD):
            return p.name
    return None


def _sample_for(p: inspect.Parameter) -> str | None:
    a = str(p.annotation)
    if "int" in a or "Integer" in a:
        return "1"
    if "float" in a or "Numeric" in a:
        return "0.5"
    if "str" in a:
        return '"a"'
    return None


def gen_methods(pr: Prober, container: str, fallback: str, stats: dict) -> list[str]:
    """Per family: probe the call; on success emit typed overloads (result from ibis, nullability from HAND).

    If a method's result family changes when its first optional positional parameter is
    supplied (round(), round(1)), emit two overloads: without it / with it required.
    Fallback (ibis-annotated return) only for methods that could not be probed for ANY family
    of this container -- a method that probes fine for int but fails for bool is invalid for bool.
    """
    found: dict[str, dict[str, object]] = defaultdict(dict)  # name -> fam -> list[(params, res)] | "fail" | "noargs"
    fns: dict[tuple[str, str], object] = {}
    for fam in FAMS:
        cls = getattr(ir, IBIS_FAM[fam] + container)
        for name in sorted(dir(cls)):
            if name.startswith("_") or name in SKIP:
                continue
            fn = getattr(cls, name)
            if not callable(fn) or isinstance(inspect.getattr_static(cls, name), property):
                continue
            try:
                sig = inspect.signature(fn)
            except (TypeError, ValueError):
                continue
            fns[(name, fam)] = fn
            cands = synth_args(name, fn, fam)
            if not cands:
                found[name][fam] = "noargs"
                continue
            res, args = None, ""
            for args in cands:
                res = pr.call(fam, container, f"x.{name}({args})")
                if res is not None:
                    break
            if res is None:
                found[name][fam] = "fail"
                continue
            variants = [(None, res)]
            opt = _optional_positional(fn)
            if opt is not None and name not in HAND_ARGS:
                v = _sample_for(sig.parameters[opt])
                res2 = pr.call(fam, container, f"x.{name}({', '.join(a for a in (args, v) if a)})") if v else None
                if res2 is not None and res2 != res:
                    variants = [("drop:" + opt, res), ("require:" + opt, res2)]
            found[name][fam] = variants
    by_name: dict[str, list[str]] = defaultdict(list)
    for name, per in found.items():
        any_ok = any(isinstance(v, list) for v in per.values())
        for fam in FAMS:
            v = per.get(fam)
            if v is None:
                continue
            fn = fns[(name, fam)]
            if isinstance(v, list):
                stats["derived"].add(name)
                for variant, res in v:
                    rule = null_rule(name, container, res[0])
                    for nul_self in ("", " | None"):
                        nul_ret = {"never": "", "always": " | None", "propagate": nul_self}[rule]
                        params = sig_params(fn, fam, nul_self, variant=variant)
                        by_name[name].append(
                            f"    def {name}(self: {container}[{fam}{nul_self}]{params}) -> {ret_type(container, res, nul_ret)}: ...")
            elif any_ok or fallback == "none" or v == "fail" and False:
                stats["omitted"].add(f"{name}:{fam}")
            else:
                stats["fallback"].add(name)
                ann = inspect.signature(fn).return_annotation
                r = "Any" if fallback == "any" or ann is inspect.Signature.empty else map_ann(ann, fam, container, IbisRetMapper)
                for nul_self in ("", " | None"):
                    by_name[name].append(
                        f"    def {name}(self: {container}[{fam}{nul_self}]{sig_params(fn, fam, nul_self)}) -> {r}: ...")
    out = []
    for name, ovs in by_name.items():
        if len(ovs) == 1:
            out += [ovs[0] + IGN]
            continue
        for o in ovs:
            out += ["    @overload", o + IGN]
    return out


BINOPS = ["add", "sub", "mul", "truediv", "floordiv", "mod", "pow", "and", "or", "xor", "lshift", "rshift"]
CMPOPS = ["lt", "le", "gt", "ge", "eq", "ne"]
SYM = {"add": "+", "sub": "-", "mul": "*", "truediv": "/", "floordiv": "//", "mod": "%", "pow": "**", "and": "&",
       "or": "|", "xor": "^", "lshift": "<<", "rshift": ">>", "lt": "<", "le": "<=", "gt": ">", "ge": ">=",
       "eq": "==", "ne": "!="}

def gen_operators(pr: Prober, container: str, stats: dict) -> list[str]:
    """Probe every (operator, self family, operand) combination; emit the ones ibis builds and duckdb binds.

    Operands: a literal / Column / Scalar of each facade family, plus intervals (timedelta literal or an
    ibis interval expression, typed with ibis's own ir.IntervalValue). Result family comes from ibis.
    Nullability: propagate (non-null self + non-null operand -> non-null; otherwise `| None`).
    """
    out: list[str] = []
    ns = {"Decimal": Decimal, "datetime": datetime, "date": date, "time": time, "timedelta": timedelta, "ibis": ibis}
    operands = [(g, LITSRC[g], g, (lambda g=g: pr.t[f"c_{g}"]), (lambda g=g: pr.t[f"c_{g}"].max())) for g in FAMS]
    operands.append(("timedelta", "timedelta(days=1)", "timedelta | ir.IntervalValue", None, None))

    def probe(src: str, x, y=None):
        try:
            return pr.check(eval(src, ns | {"x": x, "y": y}))
        except Exception:  # noqa: BLE001
            return None

    for op in BINOPS + CMPOPS:
        sym = SYM[op]
        for name, reflected in ((f"__{op}__", False), (f"__r{op}__", True)):
            if op in CMPOPS and reflected:
                continue
            ovs: list[str] = []
            for fam in FAMS:
                x = pr.recv(fam, container)
                for g, lsrc, ltype, colf, scf in operands:
                    lit_res = probe(f"{lsrc} {sym} x" if reflected else f"x {sym} {lsrc}", x)
                    if reflected:
                        if lit_res:
                            for nul in ("", " | None"):
                                ovs.append(f"    def {name}(self: {container}[{fam}{nul}], other: {ltype}, /) -> "
                                           f"{ret_type(container, lit_res, nul)}: ...")
                        continue
                    col_res = probe(f"x {sym} y", x, colf()) if colf else None
                    sc_res = probe(f"x {sym} y", x, scf()) if scf else None
                    for nul in ("", " | None"):
                        lits = ltype if lit_res else ""
                        if container == "Column":
                            parts = [p for p in (lits, f"Column[{g}{nul}]" if col_res else "",
                                                 f"Scalar[{g}{nul}]" if sc_res else "") if p]
                            r = col_res or sc_res or lit_res
                            if parts and r:
                                ovs.append(f"    def {name}(self: Column[{fam}{nul}], other: {' | '.join(parts)}, /) -> "
                                           f"{ret_type('Column', ('Column', r[1]), nul)}: ...")
                        else:
                            parts = [p for p in (lits, f"Scalar[{g}{nul}]" if sc_res else "") if p]
                            r = sc_res or lit_res
                            if parts and r:
                                ovs.append(f"    def {name}(self: Scalar[{fam}{nul}], other: {' | '.join(parts)}, /) -> "
                                           f"{ret_type('Scalar', ('Scalar', r[1]), nul)}: ...")
                            if col_res:
                                ovs.append(f"    def {name}(self: Scalar[{fam}{nul}], other: Column[{g}{nul}], /) -> "
                                           f"{ret_type('Column', ('Column', col_res[1]), nul)}: ...")
            if ovs:
                stats["operators"].add(name)
                for o in ovs:
                    out += ["    @overload", o + IGN] if len(ovs) > 1 else [o + IGN]
    for name, sym in (("__invert__", "~"), ("__neg__", "-")):
        ovs = []
        for fam in FAMS:
            r = pr.call(fam, container, f"{sym}x")
            if r:
                for nul in ("", " | None"):
                    ovs.append(f"    def {name}(self: {container}[{fam}{nul}]) -> {ret_type(container, r, nul)}: ...")
        if ovs:
            stats["operators"].add(name)
            for o in ovs:
                out += ["    @overload", o + IGN]
    return out


CAST_LITS = {  # dtype strings users write; their family is read from ibis.dtype() (mechanical)
    s: None for s in ["int8", "int16", "int32", "int64", "uint8", "uint16", "uint32", "uint64", "float32",
                      "float64", "double", "string", "str", "boolean", "bool", "date", "timestamp", "time",
                      "decimal"]
}


def gen_casts(pr: Prober, container: str) -> list[str]:
    by_target: dict[str, list[str]] = defaultdict(list)
    for s in CAST_LITS:
        by_target[family_of(ibis.dtype(s))].append(f'"{s}"')
    pytype = {"bool": "bool", "int": "int", "float": "float", "Decimal": "Decimal", "str": "str",
              "datetime": "datetime", "date": "date", "time": "time"}
    out = []
    for name in ("cast", "try_cast"):
        if container == "Scalar" and not hasattr(ir.Scalar, name):
            continue
        for fam in FAMS:
            for g in FAMS:
                if pr.call(fam, container, f'x.{name}("{DTYPE[g]}")') is None:
                    continue
                lits = by_target.get(g, [])
                tgt = f"type[{pytype[g]}]" + (f" | Literal[{', '.join(lits)}]" if lits else "")
                for nul in ("", " | None"):
                    rn = " | None" if name == "try_cast" else nul
                    out += ["    @overload", f"    def {name}(self: {container}[{fam}{nul}], target_type: {tgt}, /) -> {container}[{g}{rn}]: ...{IGN}"]
        out += ["    @overload", f"    def {name}(self, target_type: str | dt.DataType, /) -> {container}[Any]: ...{IGN}"]
    return out


IGN = "  # type: ignore"
E8 = Path(__file__).resolve().parents[2] / "e8-prototype"


def hand_parts() -> tuple[str, str, str, str]:
    """HAND 3: the E8 header, descriptor protocol, TypeVar-solving methods and helper functions, reused verbatim."""
    sys.path.insert(0, str(E8 / "tools"))
    import gen_facade as g  # the E8 generator: we reuse its hand-written text blocks only

    head = g.HEADER.replace("tools/gen_facade.py", "e11 derived/gen_derived.py")
    col_hand = f'''
class Column(ir.Value, Generic[T_co]):
    """A typed column (DERIVED facade: generated from ibis {ibis.__version__} + small hand tables)."""
    def __get__(self, obj: object, owner: Any, /) -> Self: ...
    def __set__(self, obj: object, value: Column[T_co] | Scalar[T_co] | T_co, /) -> None: ...{IGN}
    def name(self, name: str, /) -> Self: ...{IGN}
    def asc(self, *, nulls_first: bool = False) -> Self: ...{IGN}
    def desc(self, *, nulls_first: bool = False) -> Self: ...{IGN}
    def over(self, window: Any = None, *, group_by: Any = None, order_by: Any = None, rows: Any = None, range: Any = None) -> Self: ...{IGN}
    def ifelse(self: Column[bool | None], true_expr: V | Column[V] | Scalar[V], false_expr: V | Column[V] | Scalar[V], /) -> Column[V]: ...{IGN}
'''
    sc_hand = f'''
class Scalar(ir.Value, Generic[T_co]):
    """A typed scalar (DERIVED facade)."""
    def name(self, name: str, /) -> Self: ...{IGN}
    def over(self, window: Any = None, *, group_by: Any = None, order_by: Any = None, rows: Any = None, range: Any = None) -> Column[T_co]: ...{IGN}
    def ifelse(self: Scalar[bool | None], true_expr: V | Scalar[V], false_expr: V | Scalar[V], /) -> Scalar[V]: ...{IGN}
'''
    return head, col_hand, sc_hand, g.FUNCS


def fill_null(container: str) -> list[str]:
    out = []
    for f in FAMS:
        lit = "int | Decimal" if f == "Decimal" else f
        other = f"{lit} | Column[{f}] | Scalar[{f}]" if container == "Column" else f"{lit} | Scalar[{f}]"
        out += ["    @overload", f"    def fill_null(self: {container}[{f} | None], fill_value: {other}, /) -> {container}[{f}]: ...{IGN}"]
    for f in FAMS:
        other = f"Column[{f} | None] | Scalar[{f} | None]" if container == "Column" else f"Scalar[{f} | None]"
        out += ["    @overload", f"    def fill_null(self: {container}[{f} | None], fill_value: {other}, /) -> {container}[{f} | None]: ...{IGN}"]
    return out


def main(out_dir: str, fallback: str = "ibis", backend: bool = True) -> dict:
    pr = Prober(backend)
    stats: dict = defaultdict(set)
    head, col_hand, sc_hand, funcs = hand_parts()
    lines = [head, col_hand]
    lines += fill_null("Column") + gen_casts(pr, "Column") + gen_methods(pr, "Column", fallback, stats)
    lines += gen_operators(pr, "Column", stats)
    lines.append(sc_hand)
    lines += fill_null("Scalar") + gen_casts(pr, "Scalar") + gen_methods(pr, "Scalar", fallback, stats)
    lines += gen_operators(pr, "Scalar", stats)
    lines.append(funcs)
    text = "\n".join(lines) + "\n"
    text = text.replace("from typing import Any,", "from typing import Any, Callable,")
    head_, sep, body = text.partition("import ibis.expr.datatypes as dt")
    body = re.sub(r"(?<![\w.\"])datetime\b(?![\"(])", "_datetime", body)
    body = re.sub(r"(?<![\w.\"])date(?=[\] |,)])", "_date", body)
    body = re.sub(r"(?<![\w.\"])time(?=[\] |,)])", "_time", body)
    body = body.replace("import ibis.expr.types as ir", "import ibis\nimport ibis.expr.types as ir")
    head_ = head_.replace("from collections.abc import Iterable, Sequence", "from collections.abc import Iterable, Mapping, Sequence")
    head_ = head_.replace("from datetime import date as _date,", "from datetime import timedelta\nfrom datetime import date as _date,")
    out = Path(out_dir) / "tacit_next" / "_column.pyi"
    out.write_text(head_ + sep + body)
    n = text.count("\n")
    summary = {k: sorted(v) for k, v in stats.items()}
    print(f"wrote {out}: {n} lines; derived {len(stats['derived'])} methods, fallback {len(stats['fallback'])}, "
          f"omitted {len(stats['omitted'])}, operators {len(stats['operators'])}")
    return summary


if __name__ == "__main__":
    a = sys.argv[1:]
    fb = a[a.index("--fallback") + 1] if "--fallback" in a else "ibis"
    s = main(a[0], fb, "--no-backend" not in a)
    import json
    Path(a[0], "stats.json").write_text(json.dumps(s, indent=1))
