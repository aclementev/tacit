# E5 — Prior-art survey (2026-10-19)

> The E5 subagent returned this report as text (subagents may not write report files), and the main session saved it here.
> Try-out scripts are in this folder: `dy/` (dataframely), `ts/` (typedspark), `pa/` (pandera), `pt/` (patito), `tc/` (tacit baseline),
> `sa/` (SQLAlchemy), `nw/` (narwhals), and the prototypes `proto/descr.py` and `proto/poly.py`. Re-run them with `uv run --with <pkg> ...`.
> For ty against a third-party package, use a throwaway venv and `ty check --python <venv>`.
> Method: docs, `gh api` and PyPI lookups, plus hands-on trials with pyright 1.1.414, mypy 2.4.0 and ty 0.0.89 on a 2-step `Raw -> Enriched` pipeline. Claims that were not verified are marked *(unverified)*.

## Top ideas worth stealing (ordered by value/effort)

1. **Typed class-level column refs.**
   - Pattern: `Raw.amount: Col[float]`, where `Col[T]` is a `str` subclass, the attributes are annotation-only, and the values are filled in `__init_subclass__`. No metaclass hook.
   - `proto/descr.py` passes on pyright, mypy and ty:
     - `Raw.amnt` is an error.
     - `Raw.amount` is `Col[float]`.
     - Passing `Raw.status` to a `Col[float]` parameter is an error.
     - It still works as `t.select(Raw.amount)` and `t[Raw.amount]`, because it is a `str`.
   - Today tacit's `Raw.amount` is typed `float` but raises `AttributeError` at runtime.
   - Pandera had the same bug and fixed it with `FieldType[T]`: class access is a `str`, merged Aug 2026, no plugin (PR #2448). SQLAlchemy `Mapped[T]` is the same pattern.
   - typedspark shows the trap to avoid: its metaclass `__getattribute__ -> Any` makes `Schema.typo` pass every checker.
2. **Soft validation.**
   - dataframely's `Schema.filter(df)` returns the valid rows plus a `FailureInfo` (`.counts()` per named rule, `.invalid()`, `.cooccurrence_counts()`).
   - Pandera on ibis has `drop_invalid_rows=True`, which drops bad rows silently and reports nothing (verified).
3. **Schema-polymorphic helpers work on current tacit with no new machinery.**
   - `def f[S: HasAmount](df: tacit.DataFrame[S]) -> tacit.DataFrame[S]` returns `DataFrame[Orders]` and rejects an unrelated schema (`proto/poly.py`; pyright and ty).
   - typedspark needs a special `DataSetImplements[Protocol, T]` for the same thing.
   - Keep invariance: dataframely's covariance would conflict with "unexpected columns are an error".
4. **Keep `S` on row-preserving ops** (`filter`, `order_by`, `limit`, `distinct`, `head`). typedspark overrides these on `DataSet`; dataframely overrides only a few (`lazy`, `clone`, `pipe`).
5. **Named schema-level rules and multi-table Collections** (dataframely).
   - `@dy.rule()` failures are keyed by rule name.
   - A `Collection` has a shared primary key and `@dy.filter` cross-table rules (e.g. `require_relationship_one_to_at_least_one`), plus per-collection parquet IO.
   - `Schema.sample()` and `Collection.sample(overrides)` generate test data. `Collection.sample` raised a ValidationError when a cross-table filter was present, until overrides were passed.
6. **Codegen and schema comparison.** dataframely has `infer_schema`, `to_pydantic_model`, `to_sqlalchemy_columns` and `Schema.matches`. typedspark has `create_schema` and notebook support. Pandera has an `infer`/`generate` CLI.
7. **Cross-team contracts.**
   - ODCS v3.2.0 and datacontract-cli v1.2.7 offer `lint`, `test`, `changelog` and `breaking` between contract versions.
   - dbt contracts with versioned models and `state:modified` treat these as breaking: a removed column, a changed type, or a removed or changed constraint. Adding a column is not breaking.
   - Idea: ODCS import/export for `tacit.Schema`, and a `tacit diff old new` that applies those rules.
8. **Ship `py.typed`.**
   - `src/tacit/py.typed` is missing, and ibis 12.0.0 has none either. Under mypy both resolve to `Any` ("Skipping analyzing ... missing py.typed"), so tacit's revealed types are all `Any`.
   - Only pyright and ty work today, because they read the source. ibis typing PRs are still landing (#11966 is open).
9. **No type-checker plugins, so avoid designing around one.**
   - ty (issue #2551, Jan 2026): "We do not plan to add a plugin system". Built-in support is planned for Django, pydantic and attrs; pandas "could be considered".
   - pyrefly has no plugin loader and cannot run mypy plugins. pyright has none *(from memory)*.
   - Only mypy has plugin support, and pandera's plugin is pandas-only and "experimental".
10. **Pandera is converging on tacit's space.**
    - The Narwhals backend (0.32, opt-in via `PANDERA_USE_NARWHALS_BACKEND`) covers polars, ibis, pyspark SQL and pandas.
    - A merged spec (PR #2401) describes a dataframe-agnostic `pandera.dataframe` API, replacing the per-library classes in phases (ibis first).
    - Under Narwhals, `coerce=True` is a no-op on polars, ibis and pyspark (with a warning). SQL-lazy backends lack element-wise checks and sampling.
11. **Narwhals cannot replace ibis as the authoring layer.**
    - It is full support for pandas, Polars, PyArrow, cuDF and Modin, but lazy-only for Dask, DuckDB, Ibis, PySpark and SQLFrame. `nw.from_native(ibis_table)` returns a `LazyFrame` (verified).
    - The expression API is a subset, and typing is limited to `IntoFrameT` round-trips, so column names are unchecked.
12. **The "typo inside a function body" gap is open for every library.**
    - `df["custmer"]`, `pl.col("amnt")` and `t.amnt` pass all three checkers in every library tried.
    - The only attempt is the external linter `w-martin/typedframes` (a 14-star proof of concept, Rust, with a `--coverage-fail-under` gate).

## Versions and activity (2026-10-19)

| Project | Version | Date | Stars | Notes |
|---|---|---|---|---|
| dataframely | 3.1.2 | 2026-09-20 | 619 | BSD-3, polars only, Rust ext, frequent releases |
| typedspark | 1.7.0 | 2026-04-28 | 109 | recent commits are Renovate bumps only |
| pandera | 0.34.1 | 2026-10-06 | 4.5k | very active |
| patito | 0.8.6 | 2026-02-04 | 642 | `py.typed` merged May 2026, unreleased |
| narwhals | 2.27.1 | 2026-10-10 | 1.7k | Typing :: Typed |
| ibis | 12.0.0 | 2026-02-07 | 6.7k | 39 commits on main since Sept 1; 13.0.0 release PR open since Oct 2; no `py.typed` |
| SQLAlchemy | 2.1.5 | 2026-10-16 | | |
| Great Expectations | 1.24.0 | 2026-10-07 | | |
| Soda Core | 4.27.0 | 2026-10-13 | | v4 pivoted to YAML contracts; GitHub shows license NOASSERTION, a secondary source claims Elastic License 2.0 *(unverified)* |

Type checkers and PEPs:

- mypy 2.0 shipped 2026-05-06.
- ty is still beta; Astral targets a stable release in 2026.
- PEP 747 TypeForm is Final (2026-02-20) and targets Python 3.15; it is implemented in pyright and mypy.
- PEP 764 (inline TypedDict) is still Draft.
- Intersection types have no accepted PEP; a reduced form is under discussion.

## Trial results (S = static error on pyright+mypy+ty, p = pyright/ty only, R = runtime only)

| Scenario | dataframely | typedspark | pandera (polars) | patito | tacit today |
|---|---|---|---|---|---|
| Wrong schema passed | S | S | S | p | p |
| Plain untyped frame passed | S | S | S | p | p |
| Wrong schema returned | S | S | S | p | p |
| Subclass schema for parent | allowed (covariant) | rejected (invariant) | rejected | rejected | rejected |
| Typo on schema class (`Raw.amnt`) | S | **R** (metaclass hides it) | S | not tested | flagged, but valid names are typed `float` and raise `AttributeError` |
| Typo via frame (`df.amnt`, `col("amnt")`) | R | R | R | R | R |
| Wrong column dtype | R | partly | R | R | R |
| Class-level column ref type matches its runtime value | yes (`Column` object) | yes | no (`float` vs name; fixed by `FieldType`) | no (`float` vs `AttributeError`) | no |

Other trial notes:

- **patito:** `Model.DataFrame(...)` is `DataFrame[Unknown]`, and mypy treats the package as untyped. `Raw.examples()` crashed on polars 2.0.
- **dataframely:** no function-level runtime enforcement; there is no equivalent of `@contract`.
- **tacit baseline:** `return df.mutate(...)` in a `@contract` body errors on pyright (`Table` is not assignable to `DataFrame[Enriched]`). The `Column * float` operator errors are the known ibis stub issue.

## Per-library: what they do better, what tacit does better

- **dataframely** (`amount = dy.Float64(nullable=False)`, `dy.DataFrame[Raw]`)
  - Better than tacit:
    - Soft `filter` with `FailureInfo`, named rules, and `Collection` with cross-table rules.
    - `sample()` and `infer_schema`.
    - Pydantic and SQLAlchemy export.
    - Rust speed.
  - Tacit does better:
    - Supports any ibis backend; dataframely is polars only.
    - `amount: float` annotations are lighter.
    - `@contract` enforces at function boundaries.
    - The `cast` vs `parse` split.
    - The structured error API.
- **typedspark** (`Column[LongType]`, `DataSet[Raw]`)
  - Better than tacit:
    - Declarative output building: `transform_to_schema(df, Out, {Out.col: expr})`.
    - `DataSetImplements`.
    - Schema-preserving row ops.
    - Codegen and typed catalogs.
    - Self-join aliasing via `register_schema_to_dataset`.
  - Tacit does better:
    - Checks constraints and nullability; typedspark checks only column presence and type.
    - Multi-backend.
- **pandera** (`DataFrameModel`, `pa.Field(ge=0)`, `@pa.check_types`)
  - Better than tacit:
    - Breadth of checks and backends.
    - Lazy aggregated errors.
    - YAML IO, `infer` and a CLI.
    - Hypothesis strategies, pandas only.
  - Tacit does better:
    - Pydantic-style classes with no `Series[...]`/`Field` ceremony.
    - Coercion on ibis; pandera's is a no-op under Narwhals.
    - A plugin-free typing story.
- **patito** (`class Raw(pt.Model)`, `Raw.validate(df)`)
  - Better than tacit:
    - Pydantic reuse: a model is also a row.
    - `examples()`.
  - Tacit does better: backends, typing quality, and maintenance activity.
- **SQLAlchemy `Mapped[T]`**
  - Trial: pyright, mypy and ty all flag `Order.amnt`, and `Order.amount` is `InstrumentedAttribute[float]` with typed operators.
  - No plugin is needed: it is annotation-only plus `__get__` overloads.

## Comparison table

| | Backends | Static typing depth | Typo detection | Validation engine | Soft validation | Test data | Multi-table | Codegen | Maturity |
|---|---|---|---|---|---|---|---|---|---|
| tacit 0.2 | any ibis backend | `DataFrame[S]` invariant, no `py.typed` | no | pandera (ibis) + own cast | no | no | no | no | early |
| dataframely 3.1 | polars | `DataFrame/LazyFrame[S]`, covariant | schema class | native Rust/polars | yes (`filter`+`FailureInfo`) | yes | yes (`Collection`) | infer, pydantic, sqlalchemy | active |
| typedspark 1.7 | PySpark | `DataSet[S]` invariant, `DataSetImplements` | no (metaclass) | own (columns/types) | no | empty/partial datasets | no | `create_schema` | small |
| pandera 0.34 | pandas, polars, ibis, pyarrow, pyspark; Narwhals opt-in | `DataFrame[M]` invariant, `FieldType[T]` | schema class | own + Narwhals | `drop_invalid_rows`, lazy errors | Hypothesis (pandas) | no | `infer`, CLI, YAML | mature |
| patito 0.8 | polars | partial | runtime lie | own | no | `examples()` | no | no | slowing |
| narwhals 2.27 | pandas/polars/pyarrow/cudf/modin; lazy: dask, duckdb, ibis, pyspark, sqlframe | `IntoFrameT` | no | n/a | n/a | n/a | n/a | n/a | stable |
| SQLAlchemy 2.1 | SQL DBs | `Mapped[T]` descriptors | yes | DB constraints | n/a | n/a | FKs | reflection | mature |
| dbt contracts | warehouse SQL | none | build time | DDL | n/a | n/a | refs | n/a | mature, breaking-change diff |
| ODCS / datacontract-cli | many | none | n/a | server tests | n/a | n/a | per contract | many | ODCS 3.2.0 |

## Links

- dataframely: https://github.com/Quantco/dataframely
- typedspark: https://github.com/kaiko-ai/typedspark
- pandera: https://github.com/unionai-oss/pandera
  - Narwhals backend: https://pandera.readthedocs.io/en/stable/narwhals_backend.html
  - `FieldType` PR: https://github.com/unionai-oss/pandera/pull/2448
  - Generic-API spec PR: https://github.com/unionai-oss/pandera/pull/2401
- patito: https://github.com/JakobGM/patito
- narwhals: https://narwhals-dev.github.io/narwhals/
- ibis: https://github.com/ibis-project/ibis
- dbt model contracts: https://docs.getdbt.com/docs/collaborate/govern/model-contracts
- ODCS: https://github.com/bitol-io/open-data-contract-standard
- datacontract-cli: https://github.com/datacontract/datacontract-cli
- ty column-schema thread: https://github.com/astral-sh/ty/issues/2551
- typedframes: https://github.com/w-martin/typedframes
- PEP 747: https://peps.python.org/pep-0747/
- PEP 764: https://peps.python.org/pep-0764/
- pyrefly plugin stance: https://pyrefly.org/en/docs/migrate/mypy/plugins/
