# pandera: `pandera.ibis` missing `__all__`

**Status:** Proposed
**pandera version:** 0.27.0
**Severity:** Low — only affects type checkers, not runtime

## Observed symptoms

pyright reports `reportPrivateImportUsage` for imports from `pandera.ibis`:

```
"Check" is not exported from module "pandera.ibis"
"Column" is not exported from module "pandera.ibis"
"DataFrameSchema" is not exported from module "pandera.ibis"
```

These are the public API of `pandera.ibis`. The imports work at runtime.

## Minimal reproduction

```python
# pyright_test.py
import pandera.ibis as pa

check = pa.Check.ge(0)         # reportPrivateImportUsage
col = pa.Column("int64")       # reportPrivateImportUsage
schema = pa.DataFrameSchema({}) # reportPrivateImportUsage
```

Run: `pyright pyright_test.py`

## Root cause

`pandera.ibis.__init__` does not define `__all__`. Without it, pyright
treats all names in the module as private (not intended for re-export).

The top-level `pandera` module does define `__all__` and exports `Check`
correctly. But `Column` and `DataFrameSchema` from `pandera.ibis` are
ibis-specific implementations (different classes from their pandas
counterparts), so they can only be imported from `pandera.ibis`.

| Class             | Origin                              | ibis-specific? |
|-------------------|-------------------------------------|----------------|
| `Check`           | `pandera.api.checks.Check`          | No — shared    |
| `Column`          | `pandera.api.ibis.components.Column` | Yes            |
| `DataFrameSchema` | `pandera.api.ibis.container.DataFrameSchema` | Yes   |

## Proposed fix

Add `__all__` to `pandera/ibis/__init__.py`:

```python
__all__ = [
    "Check",
    "Column",
    "DataFrameSchema",
    "DataFrameModel",
    "Field",
    # ... other public names
]
```

The exact list should match everything currently importable from
`pandera.ibis` that is part of the public API.

## Workaround

Suppress in pyright config:

```toml
[tool.pyright]
reportPrivateImportUsage = false
```

Alternatively, `Check` can be imported from `pandera` directly (which has
`__all__`), reducing the suppression to only the ibis-specific classes
(`Column`, `DataFrameSchema`) which are internal to library code.

## Impact

Fixes `reportPrivateImportUsage` for all pyright/mypy users of the
`pandera.ibis` backend. No runtime behavior change.
