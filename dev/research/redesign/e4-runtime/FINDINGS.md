# E4: Runtime and performance of tacit validation (pandera vs ibis-native)

> The E4 subagent reported these findings as text (subagents may not write report files). The main session saved them here.

**Environment:**
- Machine: 2 vCPU, 3.8 GB RAM, idle box.
- Software: Python 3.13, ibis 12.0.0, duckdb 1.5.6, pandera 0.34.1, polars 2.0.0.
- Timings: wall-clock minimum of N runs after a warm-up. N is 5 at 1M rows, 3 at 10M, and 2 for coercion at 10M.

**Test schema** (`common.Customer`):
- 10 columns, 7 of them non-nullable.
- 9 checks:
  - `age` ge and le
  - `score` ge and le
  - `status` isin
  - `email` str_matches
  - `country` str_length(2,2)
  - `amount` ge
  - `qty` gt
- Optional `unique(id)`.
- Data is generated inside DuckDB.
- "Bad" data: about 0.1% of rows violate each of 7 checks.

## Reproduce

```
cd dev/research/redesign/e4-runtime
./run_all_timed.sh        # Q1 + coercion
uv run python cov_matrix.py duckdb|polars; uv run python cov_extra.py   # Q2/Q6 coverage
uv run python bench_import.py                                            # Q3
uv run python bench_contract.py; uv run python bench_contract2.py        # Q4
REPEAT=3 uv run python bench_lazy.py 1000000 10000000                   # Q5
uv run python bench_polars.py 1000000 [0.001]                            # Q6 perf
```

- **Query counts** come from DuckDB's query log (`CALL enable_logging('QueryLog')`, read from `duckdb_logs`). DESCRIBE and housekeeping queries are excluded.
- **Prototype validator:** `ibisval.py`.
- **Lazy-validation prototype:** `lazy_proto.py`.

## Q1. Query count and cost of `parse()`

**Valid data: pandera runs 16 queries.**
- 7 `bool_and(NOT isnull)` queries, one per non-nullable column.
- 9 `bool_and` queries, one per check.
- Each check query is a one-column projection combined with `POSITIONAL JOIN`, so ibis compiles 16 heavy SQL strings.

**Invalid data: pandera runs 30 queries.**
- `lazy=False` does not stop at the first failing column.
- For every failing check, `run_check` makes two extra full-length fetches:
  - `failure_cases.to_pandas()`, which fetches every offending row because `n_failure_cases` is None.
  - `check_output.to_pandas()`, which fetches one boolean per row.
- That is O(N) data movement on the failure path.

| rows | data | pandera queries / wall | native queries / wall | speedup |
|---|---|---|---|---|
| 1M | valid | 16 / 0.41 s | 1 / 0.11 s | 3.8x |
| 1M | 0.1% bad | 30 / 1.11 s | 2 / 0.22 s | 5.1x |
| 10M | valid | 16 / 2.73 s | 1 / 1.03 s | 2.6x |
| 10M | 0.1% bad | 30 / 8.48 s | 2 / 1.15 s | 7.4x |
| 1k | valid (fixed overhead) | 16 / 132 ms | 1 / 15.6 ms | 8.5x |
| 1M / 10M | + unique(id), native only | n/a | 1 / 0.17 s; 1 / 2.04 s | about +1 s at 10M for `count distinct` |

**Where the time goes:**
- A full-scan aggregate over every column takes 0.02 s at 1M rows and 0.17 s at 10M.
- The floor is the check computation itself. The 9 checks run on their own sum to 117 ms at 1M, of which the regex is 73 ms.
- So on valid data the gain at scale is about 2.5x. It is much larger on the failure path and for small or many tables.

**Native validator** (`ibisval.validate`, about 150 lines):
- One `t.aggregate(...)` query computes:
  - the null count per column;
  - `(~pred).sum()` for each check, where a NULL predicate result is ignored (matching pandera's `ignore_na`) and a float NaN counts as null;
  - `count - nunique` for unique columns.
- A second query runs only if something failed: one `UNION ALL` of `filter(bad).select(...).limit(5)`, one branch per failing item.
- Predicates are built from pandera's `Check.name` and `.statistics`, so pandera is used only as a spec.
- Pandera's own check functions can also be reused. `check._check_fn(IbisData(t, col), **check._check_kwargs).op().values[col]` yields a plain ibis predicate (verified for `Check.ge`).

### Coercion (string to typed)

| source | rows | data | tacit parse (pandera) | native `validate(coerce=True)` |
|---|---|---|---|---|
| VARCHAR table | 1M | valid | 16 q / 0.74 s | 1 q / 0.25 s |
| VARCHAR table | 10M | valid | 16 q / 6.03 s | 1 q / 2.26 s |
| VARCHAR table | 10M | 10k bad `'N/A'` | 15 q / 5.54 s, then CoercionError | 2 q / 2.40 s, report `{qty: 10000}` plus samples |
| CSV `read_csv` view | 1M | valid | 16 q / **10.5 s** | 1 q / 0.68 s |
| CSV view | 1M | bad | 15 q / 9.4 s, then CoercionError | 2 q / 0.96 s |

**Current tacit (pandera path):**
- The cast happens inside the expression, so each of the 16 queries casts again.
- Over a file-backed view, each query also re-reads and re-parses the file, which makes it about 15x slower on CSV.
- A failure surfaces only as the first DuckDB `ConversionException`.
- `CoercionError` lists every cast column, not just the one that failed.

**Native path:**
- Uses `try_cast` and counts cells where the raw value is not null but the cast result is null.
- This counts every bad cell, per column, inside the same aggregate.

## Q2. Pandera ibis backend coverage (duckdb)

**Works correctly.** These fail bad data and pass good data and NULLs (`ignore_na=True`):
- `ge`, `le`, `gt`, `lt`, `eq`, `ne`.
- `in_range`, including exclusive bounds.
- `isin`, `notin`.
- `str_matches` (anchored with `^`), `str_contains`, `str_startswith`, `str_endswith`, `str_length` (range and exact).
- `unique_values_eq`.
- Custom checks that return a boolean column, a boolean table, or a boolean scalar. The scalar form has no failure cases.
- Dataframe-level checks.
- dtype, nullable, strict, missing column, and regex columns.
- `DataFrameSchema(unique=[...])`, on duckdb only.
- `element_wise=True`, but only with a fully annotated function. A lambda raises `MissingReturnAnnotationError`.

**Silently ignored or unsupported:**
- **`Column(unique=True)` is silently ignored, so duplicates pass.**
  - tacit cannot express dataframe-level `unique` either, because it only forwards checks and nullable.
  - So uniqueness cannot be enforced through tacit today.
- `coerce=True` has no effect, and the column fails with WRONG_DATATYPE.
- `Check(..., groupby=...)` is accepted but has no effect.
- In DuckDB, `NaN >= 0` is true, so `ge` and `le` don't catch NaN.

**Shape of failure cases:**
- `SchemaError.failure_cases` is a pandas DataFrame with one row per offending row.
- Its `index` is the position in the fetched result, not a stable row id.
- pandas is needed at failure time.

**A tacit bug found along the way:** `Customer.cast(duckdb_table)` raises `StructuralError: column 'created' expected timestamp, got timestamp(6)` for a plain `datetime` field. DuckDB reports `timestamp(6)`, while tacit's schema says `timestamp`. `parse()` works only because it casts first.

## Q3. Dependency weight

| environment | packages | site-packages |
|---|---|---|
| ibis, bare | 9 | 26 MB |
| ibis[duckdb] | 19 | 352 MB (pyarrow 162, duckdb 58, pandas 41, numpy 57) |
| + pandera[ibis] (tacit's dependency closure) | 27 | 362 MB |

**Install size is not the problem.**
- pandera core adds 8 packages and 10 MB: pydantic, pydantic-core, typeguard, typing_inspect, and others.
- pandas and numpy come from ibis's duckdb extra, not from pandera.

**Import time is the problem.**

| statement | wall |
|---|---|
| `import ibis` | 1.1–1.3 s, 68 MB RSS |
| `import pandera.ibis` | 3.1–3.4 s |
| `import tacit` | 3.2 s, 161 MB RSS, 989 modules |

- `-X importtime` attributes 2.94 s to `import tacit`.
- 2.73 s of that is `pandera.ibis`. pandera accounts for 2.0 s cumulative, of which pandas is 1.2 s.
- `tacit.*` itself takes about 8 ms. `importlib.metadata.version` takes 0.2 s.
- Dropping pandera would bring `import tacit` down to about the cost of `import ibis`.

## Q4. `@contract` overhead (µs, minimum of 7 runs)

| operation | µs |
|---|---|
| plain function call | 0.05 |
| `inspect.signature(fn)` | 5.5 |
| `inspect.signature(fn).bind(df)` | 7.0 |
| `Schema.cast(df)`, 3 columns | 51 |
| … of which `_ibis_schema()`, rebuilt on every call | 44.5 |
| `Schema.cast(df)`, 100 columns | 726 |
| `@contract`, 1 param + return | 128 |
| `@contract`, 2 params + return | 183 → 110 with the signature cached |
| `cast_fast` (cached target schema plus `==` fast path), 3 or 100 columns | 1.2 |
| `@contract` with cached signature + `cast_fast` | 3.9 |

**Caching the signature is not the real fix.** It saves only about 18 µs.

**The real cost is that `ibis.schema(cls._fields)` is rebuilt on every `cast()`.**
- Fix: memoise it, and add an equality fast path.
- Effect: a 1-param contract drops from 128 µs to about 4 µs (30x), and a 100-column cast from 726 µs to about 1 µs.

**Deep expressions:**
- `table.schema()` is O(1) at any depth: 0.07 µs at depth 1 and at depth 1000.
- What grows is expression build time and `to_sql`:
  - 50 mutates: 14 ms build, 61 ms SQL.
  - 200 mutates: 60 ms build, 442 ms SQL.
  - 1000 mutates: 295 ms build, 7.7 s SQL.
- pandera recompiles the graph for each of its 16 queries. A 50-deep chain therefore costs about 1 s of pure compile time in `parse()`, while a one-query validator compiles once.

## Q5. Lazy validation (`lazy_proto.py`)

**How it works:**
- A `t.filter(CASE WHEN <null or violation> THEN error('... first bad value') ... ELSE TRUE END)`, using DuckDB's built-in `error()` declared as an ibis builtin UDF.
- The checks are fused into whatever query the user eventually runs.
- `unique` becomes a scalar subquery.

| 10M rows, query = group-by on 2 columns | wall |
|---|---|
| baseline | 0.16 s |
| eager native validate, then query | 1.18 s |
| eager pandera parse, then query | 2.90 s |
| lazy guard | 1.25 s |
| lazy guard + unique subquery | 2.78 s |
| 2 queries: eager native (validates once) / lazy (validates per query) | 1.44 s / 2.52 s |
| 0.1% bad: lazy fails at the first bad row | 0.02 s |

**Pros:**
- No extra pass and no extra round trip. Nothing runs unless the data is used.
- Fails fast.
- In Spark the equivalent would be `assert_true` or `raise_error` inside a filter. That avoids the extra job per `parse()` that eager validation forces.

**Cons:**
- Validation is paid on every materialisation.
- It validates only what the query reads. For example, `guard(t).limit(10)` passes even when the last row is bad.
- The error is the engine's exception, with no counts and only one sample.
- The guard has to be a filter: if it is projected as a column, `select()` prunes it.
- It needs an engine function that raises.
- The `CASE` expression is repeated in every downstream query.

**Verdict:** a good opt-in mode, not a replacement for eager `parse()`.

## Q6. Polars backend

- pandera behaves the same as on duckdb: same pass/fail results, 16 queries on valid data and 30 on invalid.
- One exception: `DataFrameSchema(unique=...)` raises `OperationNotDefinedError`, because the polars backend has no window functions.
- At 1M rows:
  - pandera: 0.15 s on valid data, 0.41 s on bad.
  - native validator: 0.08 s on valid data, 0.17 s on bad.
- The native validator, including `nunique` and `try_cast`, runs unchanged on polars.

## Recommendation

**Build a small ibis-native validator, and stop using pandera as the validation engine.**

**Why** (pandera compared with the native validator):
- 16–30 queries instead of 1–2.
- 2.6–3.8x slower on valid data, and 5–7x slower on invalid data.
- 8.5x the fixed overhead.
- Fetches O(N) data into pandas on failure.
- 15x slower at coercing file-backed views.
- Adds about 2 s and 90 MB at import.
- Silently ignores `unique`, `groupby` and `coerce`.

**What to build:**
- **One aggregate query** covering nulls, checks, uniqueness and `try_cast` coercion.
- **A bounded sample query that runs only on failure.**
- **A structured report** with counts and sample values.
- **A `tacit.Check` with its own constructors**, plus custom checks typed as `Callable[[Column], BooleanColumn]`.
- **Optionally, read pandera `Check` objects** as a spec, for compatibility.

**Fix in the current code regardless of that decision:**
- Memoise `_ibis_schema()` and add an `==` fast path in `cast()`.
- Normalise `timestamp(6)` versus `timestamp` in structural comparisons.
- Stop casting inside an expression that then gets queried 16 times.

**Offer lazy guard validation as an opt-in mode.**

**Caveats:**
- These are single-machine numbers on in-memory DuckDB. A remote warehouse would widen the round-trip gap between 16 queries and 1.
- Semantic parity of the native validator is verified only for this schema and the Q2 matrix. Datetime, decimal and interval checks were not tested.
