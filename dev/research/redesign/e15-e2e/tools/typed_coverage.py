"""How typed is a pipeline, really? Classify the type pyright infers for every data expression.

    cd dev/research/redesign && uv run --frozen python e15-e2e/tools/typed_coverage.py e15-e2e/examples/e2e.py ...

pyright strict's reportUnknown* rules only flag Unknown. Plain ibis code is mostly *not* Unknown:
`_.amount` is `Deferred`, `t.amount` is `ir.Column`, `t.mutate(...)` is `Table`. Those are typed,
but carry no column names, value types or nullability. So every expression inside function
bodies (calls, attribute reads, operators, comparisons, subscripts, names) is wrapped in
`reveal_type(...)` in a temporary copy, and pyright's revealed type is classified:

  schema    the type carries tacit's column/schema typing: Column[T], Scalar[T], DataFrame[S], a Schema
  ibis      an ibis type without column typing: Table, GroupedTable, ir.*Column / *Value / *Scalar
  deferred  ibis `Deferred` (`_.x`): resolved only at runtime
  unknown   Unknown / Any (or partially Unknown)
  other     not data: str, int, Path, functions, modules, lists of str, ...

Writes out/typed_coverage.txt (summary + every non-schema data expression).
"""

import ast
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
ROOT = HERE.parent
SKIP_FUNCS = {"reveal_type", "print", "Path", "len", "isinstance"}


class Wrap(ast.NodeTransformer):
    def __init__(self) -> None:
        self.n = 0

    def _wrap(self, node: ast.expr) -> ast.expr:
        self.n += 1
        return ast.Call(func=ast.Name("reveal_type", ast.Load()), args=[node], keywords=[])

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        node.body = [self.visit(s) for s in node.body]  # leave decorators / annotations alone
        return node

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        return node  # schema declarations are not pipeline expressions

    def visit_Lambda(self, node: ast.Lambda) -> ast.expr:
        node.body = self.visit(node.body)
        return node

    def generic_visit(self, node: ast.AST) -> ast.AST:
        super().generic_visit(node)
        if isinstance(node, (ast.Call, ast.Attribute, ast.BinOp, ast.Compare, ast.Subscript, ast.Name, ast.UnaryOp)):
            if isinstance(getattr(node, "ctx", ast.Load()), ast.Load) and not _skip(node):
                return self._wrap(node)
        return node

    def visit_Call(self, node: ast.Call) -> ast.expr:
        # do not wrap the callee itself (x.method / f): only its receiver and arguments
        if isinstance(node.func, ast.Attribute):
            node.func.value = self.visit(node.func.value)
        node.args = [self.visit(a) for a in node.args]
        for k in node.keywords:
            k.value = self.visit(k.value)
        return node if _skip(node) else self._wrap(node)


def _skip(node: ast.AST) -> bool:
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in SKIP_FUNCS:
        return True
    return isinstance(node, ast.Name) and node.id in ("ibis", "tacit", "_", "pa", "Path", "sys") or (
        isinstance(node, ast.Name) and node.id[:1].isupper()
    )


def classify(t: str, schemas: set[str]) -> str:
    if "Unknown" in t or re.search(r"(^|[^\w\[])Any\b", t):
        return "unknown"
    if "Deferred" in t:
        return "deferred"
    if re.search(r"\b(Column|Scalar|DataFrame|Join)\[", t) or t in schemas or t.startswith("tuple[DataFrame["):
        return "schema"
    if any(re.search(rf"\b{n}\b", t) for n in IBIS_NAMES) or t.endswith(("Column", "Value", "Scalar")):
        return "ibis"
    return "other"


IBIS_NAMES = ["Table", "GroupedTable", "Join", "Value", "Expr", "BooleanValue", "BooleanColumn", "IntegerScalar",
              "ArrayColumn", "IntervalColumn", "BaseBackend", "Backend"]


def main(files: list[str]) -> None:
    report: list[str] = []
    for f in files:
        src = Path(f).read_text()
        w = Wrap()
        parsed = ast.parse(src)
        schemas = {n.name for n in ast.walk(parsed) if isinstance(n, ast.ClassDef)}
        tree = w.visit(parsed)
        code = ast.unparse(ast.fix_missing_locations(tree))
        with tempfile.TemporaryDirectory(dir=HERE / "out") as td:
            tmp = Path(td) / Path(f).name
            tmp.write_text(code)
            p = subprocess.run(["uv", "run", "--frozen", "pyright", "-p", str(HERE / "pyrightconfig.json"), "--outputjson", str(tmp)],
                               cwd=ROOT, capture_output=True, text=True)
        diags = json.loads(p.stdout[p.stdout.find("{"):])["generalDiagnostics"]
        revs = []
        for d in diags:
            m = re.match(r'^Type of "(.*)" is "(.*)"$', d["message"], re.S)
            if d["severity"] == "information" and m:
                revs.append((m[1], m[2]))
        errors = [d["message"] for d in diags if d["severity"] == "error"]
        cats = Counter(classify(t, schemas) for _, t in revs)
        data = {k: v for k, v in cats.items() if k != "other"}
        total = sum(data.values())
        report.append(f"== {f}: {w.n} wrapped expressions, {len(revs)} revealed, {len(errors)} errors in instrumented copy {[e[:120] for e in errors]}")
        report.append("   data expressions: " + ", ".join(f"{k} {v} ({v / total:.0%})" for k, v in sorted(data.items(), key=lambda x: -x[1]))
                      + f"   [other/non-data: {cats['other']}]")
        for e, t in revs:
            c = classify(t, schemas)
            if c not in ("schema", "other"):
                e = e.replace("reveal_type(", "").replace("))", ")")
                report.append(f"   {c:8} {e[:64]:64} : {t[:60]}")
    text = "\n".join(report)
    (HERE / "out" / "typed_coverage.txt").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main(sys.argv[1:])
