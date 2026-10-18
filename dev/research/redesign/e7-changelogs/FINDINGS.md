# E7 — Upstream changelog review (2026-10-19)

> Reported by the E7 subagent as text (subagents may not write report files) and saved here by the main session.
> Probe scripts are in this folder (`*_probe.py`).
> Versions checked: ibis 12.0.0, pandera 0.34.1, duckdb 1.5.6, polars 2.0.0, mypy 2.4.0, pyright 1.1.414, ty 0.0.89, pyrefly 1.4.0, and CPython 3.15.0.

## What matters

1. **ibis has not released since 12.0.0 (2026-02-07), and its momentum has dropped.**
   - Human commits fell from 512 in the year before 12.0.0 to 87 since.
   - The lead maintainer (cpcloud) last committed on 2026-02-04. Most work now comes from Deepyaman Datta (50 commits) and Nick Crews (8).
   - A 13.0.0 release is planned (ibis#12102): new backends, Flink 2, Polars 2 and DuckDB 2. Expect breaking changes.
2. **None of the four ibis typing problems is fixed in a release.**
   - These are unchanged on `main`:
     - `Table.__getattr__ -> Column`
     - `mutate(**kw)` rejects literals
     - `Schema.names` is typed as `Attribute`
   - Comparison operators rejecting scalars has a draft fix, ibis#11966. It has been open since 2026-03-06, with no reviews and a merge conflict.
   - ibis still has no `py.typed`, and the maintainers declined to re-add it (#6844, after #5279 added and later removed it).
   - Each checker behaves differently:
     - pyright raises errors on all of these.
     - ty and pyrefly infer `t.x` as `Unknown`, so they report no false positives.
     - mypy sees `ir.Table` as `Any`, even with `--follow-untyped-imports`.
   - Cheap fix: `schema.py` can drop its two `# type: ignore` comments by using `set(schema)` or `list(schema.keys())` (verified with pyright).
3. **Two of the four `dev/contributions/` items are already resolved upstream.**
   - `pandera.ibis` gained `__all__` in pandera 0.31.0 (commit edff92db).
     - pyright now reports 0 errors on `src/` with `reportPrivateImportUsage` on.
     - One nit: `__all__` lists `set_config` but never imports it, so `from pandera.ibis import *` raises `AttributeError`.
   - The `fetch_arrow_table` fix is merged on ibis `main` (#12001, 2026-05-12) but unreleased. ibis 12.0.0 still warns with duckdb 1.5.6, so keep the pytest filter.
4. **pandera's limitations on ibis are unchanged.**
   - Coercion is still a no-op (`col.coerce = False`).
   - `schema.example()` raises `NotImplementedError`, so Hypothesis strategies remain unsupported.
   - `SchemaError.column_name` is `None` in every scenario tested.
   - `failure_cases` is polymorphic: a pandas DataFrame for check failures, an `ibis.Table` for null failures, and a `str` for structural failures.
   - The tacit suite passes on Python 3.13 and 3.14.8, and also with pandera's opt-in narwhals backend.
5. **The assumption "no mapped types; TypeForm is years away" is out of date.**
   - PEP 747 (TypeForm) and PEP 728 (closed TypedDict) are Final and shipped in Python 3.15.0 (2026-10-09). All four checkers support TypeForm.
   - PEP 827 "Type Manipulation" (TypeScript-style mapped and conditional types) is a Draft targeting 3.16, now dependent on PEP 849. Only a mypy prototype exists.
   - PEP 764 is still a Draft, and no intersection-type PEP has been accepted.
   - Plugins are still unavailable: pyright still refuses them (#607), and ty has no plugin API.
6. **pyrefly 1.x tracks Polars and pandas DataFrame schemas natively.**
   - It reports `unknown-column` and supports `Annotated[DataFrame, Schema(...)]`.
   - Verified: `df.select("nonexistent")` is an error in pyrefly, but not in pyright or ty.
   - ibis is not covered. This is the closest thing to the "type-checker plugin" path that tacit assumed.
7. **Variance trap.** With a phantom PEP 695 `S`, pyright, ty and mypy infer covariance, while pyrefly stays invariant. A legacy `Generic[S]` with a `TypeVar` is invariant in all four checkers.
8. **A descriptor `Column[T]` works on all four checkers.** Overloaded `__get__` resolves to `Deferred` on class access and `float` on instance access. pyrefly adds `bad-dataclass-descriptor` for non-data descriptors under `dataclass_transform`.
9. **Polars 2.0.0 (2026-10-06) breaks ibis 12's polars backend** on `cast("time")` from a string. The fix is on `main` but unreleased. tacit's dev dependency `polars>=1.0.0` is uncapped.
10. **Docs toolchain.**
    - Material for MkDocs reaches end of life on 2026-11-05.
    - Zensical 0.0.71 reads `mkdocs.yml` and supports mkdocstrings and llmstxt, with caveats.
    - mkdocs 2.0 exists only as dev releases.
11. **Python 3.14 is fine.** The suite passes on 3.14.8. 3.15 could not be tested because numpy and pyarrow have no cp315 wheels.

## Assumption audit

| # | Assumption | Status | Evidence | Impact |
|---|---|---|---|---|
| 1 | ibis has no `py.typed` | STILL TRUE | absent in 12.0.0 and `main`; re-add declined (#6844) | mypy cannot enforce `DataFrame[S]` |
| 2 | `Table.__getattr__` returns `Column` | STILL TRUE | `relations.py:1166` | pyright false positives |
| 3 | comparison operators reject scalars | STILL TRUE | #11966 draft stalled | review or help #11966 |
| 4 | `mutate(**kw)` rejects literals | STILL TRUE | same signature on `main`; #11809 stale | smallest upstream PR, still unclaimed |
| 5 | `Schema.names` typed `Attribute` | STILL TRUE | `schema.py:65-70` | use `set(schema)` instead |
| 6 | `pandera.ibis` has no `__all__` | FIXED (0.31.0) | edff92db | drop `reportPrivateImportUsage=false`; require pandera>=0.31 |
| 7 | duckdb `fetch_arrow_table()` deprecation | FIXED on `main`, unreleased | #12001 | keep the warning filter until ibis 13 |
| 8 | pandera ibis has no coercion | STILL TRUE | `coerce=False` | tacit's own cast step stays |
| 9 | pandera Hypothesis support is pandas-only | STILL TRUE | `example()` raises `NotImplementedError` | test data generation is tacit's job |
| 10 | `validate()` returns the same object/subclass | STILL TRUE | probe | the subclass design holds |
| 11 | `SchemaError.column_name` is `None` for ibis | STILL TRUE | 5 scenarios | handle `failure_cases` polymorphically |
| 12 | `Relation.to_expr()` hard-codes `Table(self)` | STILL TRUE | `relations.py:78-81` | ops always return a plain `Table` |
| 13 | pandera on Python 3.14 misses bare annotations | NOT REPRODUCIBLE | 3.14.8 | none |
| 14 | pyright plugins unsupported | STILL TRUE | #607; ty has no plugin API either | only a mypy plugin is possible |
| 15 | no mapped types; TypeForm years away | CHANGED | PEP 747 and 728 Final in 3.15; PEP 827 Draft for 3.16 | mapped types possible, earliest in 3.16 (Oct 2027) plus checker support |
| 16 | invariance via `Generic[S]` | STILL TRUE, with a trap | `phantom_variance_probe.py` | don't convert to PEP 695 syntax without a test |
| 17 | descriptor `Column[T]` works | STILL TRUE, now on all 4 checkers | `descriptor_probe.py` | portable upgrade path |
| 18 | Material for MkDocs maintenance ends Nov 2026 | CONFIRMED | EOL 2026-11-05 | migrate now |
| 19 | Zensical reads `mkdocs.yml` | PARTLY | 0.0.71; gen-files unsupported; issue #1046 | do a trial build |
| 20 | polars is a harmless dev dependency | NEW RISK | `ibis_polars2_probe.py` | cap `polars<2` until ibis 13 |
| 21 | pandera ibis feature surface | NEW | `drop_invalid_rows` needs `lazy=True`; per-column drop is ignored (#2529); lazy mode reports all missing columns; `add_missing_columns` raises `NotImplementedError` on ibis; `infer_schema()` and `to_json()` work | see below |

## New upstream features worth exploiting

- **pyrefly's DataFrame schema tracking.**
  - Ask the pyrefly team for ibis support, or for a hook so that `DataFrame[S]` exposes its schema.
  - Add pyrefly to CI.
- **PEP 827 (Draft).** Keep schemas introspectable as plain annotated classes so they can map onto it later.
- **TypeForm.** `returns=` could accept `Annotated` or union forms. Low priority.
- **pandera ibis modes.**
  - `lazy=True` reports every failure at once.
  - `drop_invalid_rows` (lazy only) gives a quarantine mode.
  - `infer_schema()` can back a `Schema.from_table()` scaffolder.
  - `to_json()` supports export.
- **pandera's `FieldType[T]` (#2448) and its dataframe-agnostic API spec (#2401)** are worth reading.
- **PEP 810 lazy imports (3.15)** could defer the ibis and pandera imports behind `import tacit`.

## Risks

- **ibis is the biggest risk.**
  - Typing PRs are stale, few contributors are active, 127 PRs are open, and a major release with Polars and DuckDB 2.0 is coming.
  - tacit relies on `Expr.__slots__`, `Immutable`, and `Table(self)` in `to_expr`. All are unchanged on `main`.
  - Re-run the suite against ibis `main` before 13.0.0 ships.
- **DuckDB 2.0 and Polars 2.0.** Removing `fetch_arrow_table()` would break ibis 12 on DuckDB, and Polars 2.0 has already broken one ibis code path.
- **pandera is healthy** (7 minor releases in 8 months), but ibis is a second-class backend there.
- **Type checkers.**
  - pyright's release cadence has slowed.
  - ty is still in beta, so snapshot tests against it will churn.
  - mypy 2.4 made the native parser the default.
- **Python 3.15** (released 2026-10-09) is not yet advertised by ibis or pandera.

## Cheap actions

1. Use `set(schema)` in `schema.py` and drop the two `# type: ignore` comments.
2. Retire the `pandera-ibis-missing-all` and `ibis-duckdb-fetch-arrow-table` contribution docs. Re-point the comparison-operators doc at #11966.
3. Require pandera>=0.31 and drop `reportPrivateImportUsage=false`.
4. Add typecheck tests for both assignment directions before converting to PEP 695 generics.
5. Cap `polars<2` in the dev dependency group.
6. Do a trial docs build with Zensical before 2026-11-05.
7. Add pyrefly to CI.
