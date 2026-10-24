"""Lines of code per section: imports/constants, contracts (classes), steps (functions), runner.

    uv run --frozen python e15-e2e/tools/loc.py e15-e2e/examples/e2e.py e15-e2e/examples/e2e_plain.py

Counts physical lines that hold code: blank lines, comments and docstrings are excluded.
"""

import ast
import io
import sys
import tokenize
from pathlib import Path


def code_lines(src: str) -> set[int]:
    lines: set[int] = set()
    doc: set[int] = set()
    for node in ast.walk(ast.parse(src)):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant):
            if isinstance(body[0].value.value, str):
                doc.update(range(body[0].lineno, body[0].end_lineno + 1))
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type not in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER):
            lines.update(range(tok.start[0], tok.end[0] + 1))
    return lines - doc


def main() -> None:
    print(f"{'file':14} {'imports':>8} {'contracts':>10} {'classes':>8} {'steps':>6} {'runner':>7} {'total':>6}")
    for f in sys.argv[1:]:
        src = Path(f).read_text()
        lines = code_lines(src)
        sec = {"imports": 0, "contracts": 0, "steps": 0, "runner": 0}
        n_classes = 0
        for node in ast.parse(src).body:
            span = {ln for ln in lines if node.lineno - len(getattr(node, "decorator_list", [])) <= ln <= node.end_lineno}
            if isinstance(node, ast.ClassDef):
                sec["contracts"] += len(span)
                n_classes += 1
            elif isinstance(node, ast.FunctionDef) and node.name not in ("run", "read"):
                sec["steps"] += len(span)
            elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.If):
                sec["runner"] += len(span)
            else:
                sec["imports"] += len(span)
        print(f"{Path(f).name:14} {sec['imports']:>8} {sec['contracts']:>10} {n_classes:>8} {sec['steps']:>6} {sec['runner']:>7} {len(lines):>6}")


if __name__ == "__main__":
    main()
