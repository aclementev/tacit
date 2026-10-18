# ibis: conditionally-defined `FixedTextJupyterMixin` gives every Table/Column an Unknown base (ty, pyrefly)

**Status:** Proposed (not filed yet)
**ibis version:** 12.0.0 and `main` as of 2026-10-19
**Checkers affected:** ty 0.0.89, pyrefly 1.4.0, and pyright (`reportGeneralTypeIssues` inside ibis)
**Severity:** High. Under ty and pyrefly, an `ir.Table` is assignable to any `Table` subclass, so tacit's
"forgot to cast" guarantee silently disappears, and `x.upper()` on a float column goes unflagged.

## Root cause

`ibis/expr/types/rich.py` defines `FixedTextJupyterMixin` in both branches of a `try/except ImportError`
around `from rich.jupyter import JupyterMixin`. Type checkers see two class definitions with the same name.
ty and pyrefly then treat the base as a union, which they model as an Unknown base. Every class deriving from it
(`Expr` → `Table`, `Column`, …) inherits an Unknown base: attribute lookups that should fail resolve to
`Unknown`, and assignability checks against subclasses pass.

## Minimal reproduction

See `dev/research/redesign/e2-typed-columns/upstream_repro_conditional_base/` (`repro.py`, `output.txt`).
The repro is checked under all four checkers. Shape:

```python
try:
    from json import JSONDecoder as Base
except ImportError:
    class Mixin: ...
else:
    class Mixin(Base): ...

class Col(Mixin):
    def mean(self) -> float: ...

def f(c: Col) -> None:
    c.upperr()   # ty/pyrefly: Unknown, no error
```

## Proposed fix (one definition visible to type checkers)

```python
if TYPE_CHECKING:
    from rich.jupyter import JupyterMixin
else:
    try:
        from rich.jupyter import JupyterMixin
    except ImportError:
        JupyterMixin = object

class FixedTextJupyterMixin(JupyterMixin):
    ...
```

Full patch: `dev/research/redesign/e3-schema-algebra/ibis-typing.patch`. With this patch plus the companion
mypy fix (`../ibis-table-self-import-mypy-any`), E3 measured correct behavior in pyright, mypy, ty and pyrefly
(`raw/MATRIX.patched.md` vs `raw/MATRIX.stock.md`).
