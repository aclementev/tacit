# ibis: DuckDB backend uses deprecated `fetch_arrow_table()`

**Status:** Ready to contribute
**ibis version:** 12.0.0
**duckdb version:** 1.5.1+
**Severity:** Low — cosmetic (DeprecationWarning), no functional impact

## Problem

duckdb 1.5.x deprecated `DuckDBPyResult.fetch_arrow_table()` in favor of
`to_arrow_table()`. ibis 12.0.0 still uses the old name in its DuckDB backend,
producing a `DeprecationWarning` on every call.

## Reproduction

```python
import ibis
import warnings
warnings.simplefilter("always")

con = ibis.duckdb.connect()
t = con.read_csv("any_file.csv")
t.execute()  # DeprecationWarning: fetch_arrow_table() is deprecated
```

## Fix

Replace `fetch_arrow_table()` with `to_arrow_table()` on cursor/result objects
in `ibis/backends/duckdb/__init__.py`. There are 5 call sites:

```
line 332:  meta = result.fetch_arrow_table()
line 356:  result = cur.fetch_arrow_table()
line 372:  out = cur.fetch_arrow_table()
line 901:  out = self.con.execute(sql).fetch_arrow_table()
line 1718: rows = cur.fetch_arrow_table()
```

The fix is a direct rename — `to_arrow_table()` is the same API with the same
signature and return type.

Note: ibis also calls `to_arrow_table()` on DuckDB **relation** objects
elsewhere in the file — that's a different (non-deprecated) method and is
unrelated.

## Workaround (applied in tacit)

```toml
[tool.pytest.ini_options]
filterwarnings = [
    "ignore:fetch_arrow_table\\(\\) is deprecated:DeprecationWarning:ibis.backends.duckdb",
]
```
