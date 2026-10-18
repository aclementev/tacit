# ibis: `relations.py` re-imports `Table` under TYPE_CHECKING, so mypy types `ir.Table` as `Any`

**Status:** Proposed (not filed yet)
**ibis version:** 12.0.0 and `main` as of 2026-10-19
**Checkers affected:** mypy 2.4.0 (with `follow_untyped_imports = True`, which ibis needs because it ships no `py.typed`)
**Severity:** High. Every Table method returns `Any` in mypy, and any subclass of `Table` (such as tacit's
`DataFrame[S]`) has an `Any` base, so mypy accepts `DataFrame[Iris]` as `int` and invariance is meaningless.

## Root cause

`ibis/expr/types/relations.py` has

```python
if TYPE_CHECKING:
    from ibis.expr.types import Table
...
class Table(Expr, FixedTextJupyterMixin): ...
```

mypy reports `no-redef` for the class definition and falls back to `Any` for the name.

## Minimal reproduction

`dev/research/redesign/e2-typed-columns/upstream_repro_mypy_table_any/` (`selfimp/rel.py`, `use.py`):
`reveal_type(t)` is `Any` in mypy.

## Proposed fix

Delete the self-import. The class is defined in the same module, and `from __future__ import annotations`
already makes forward references work. Patch: `dev/research/redesign/e3-schema-algebra/ibis-typing.patch`.

## Related

- ibis ships no `py.typed`. Re-adding it was declined upstream (ibis#6844). mypy users must set
  `follow_untyped_imports = true` for ibis. Tacit should document this, and must itself ship `py.typed`.
