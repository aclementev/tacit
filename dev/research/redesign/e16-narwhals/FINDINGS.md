# E16: narwhals as tacit's engine

> The E16 subagent (Opus) returned this report as text, and the main session saved it here.
> The main session re-ran two checks:
> - `tests/test_runtime.py`: 25 tests pass locally. `E16_SPARK=1` adds the PySpark tests, for 29 in total.
> - `tests/score.py`: the numbers match the matrix in section 3.
>
> `NOTES.txt` indexes every script and output and explains how to regenerate them. This folder is its own uv project on Python 3.13.

**Versions:**
- narwhals 2.27.1 (`stable.v2`)
- polars 2.0.0
- duckdb 1.5.6
- pyspark 4.2.0, classic and Spark Connect
- sqlframe 4.6.0
- ibis 12.0.0
- pandera 0.34.1
- postgres 17 (rootless podman)
- pyright 1.1.414, mypy 2.4.0, ty 0.0.89, pyrefly 1.4.0

**ibis broke twice during setup.** This adds to the evidence in E12.
- **sqlglot.** sqlglot ≥ ~30.18 breaks ibis 12's `create_table(name, obj)`: the generated SQL is `DROP VIEW IF EXISTS` with no name. Bisected to 30.10 working and 30.18 failing. The shared research venv has sqlglot 30.23 and is affected.
- **pyspark.** `ibis-framework[pyspark]` 12 requires pyspark < 4.1, so it can't be installed next to pyspark 4.2.

## Bottom line

**Recommendation: option (c).**
- Make narwhals `stable.v2` the engine.
- Keep ibis reachable as one of narwhals's backends.
- Make native-frame boundaries (`tag` and `step`) first-class.

**Why narwhals suits PySpark and Polars users:**
- It works with PySpark 4.2 and Spark Connect.
- It supports window functions on Polars.
- Native frames go in and come back out.
- It is fully typed on all four checkers, mypy included.
- It promises in writing never to break `stable.v2`.
- It is widely adopted.

**What it costs:**
- A smaller expression API than ibis.
- Five upstream bugs, three of which return silently wrong results.
- A weaker path to SQL warehouses.
- About 6–9 weeks of work.

**Ruled out:**
- **(b), narwhals alone:** gives up BigQuery and Snowflake reach for nothing.
- **(d), ibis primary with narwhals only at boundaries:** keeps two engines and still leaves PySpark users without a typed authoring path.

## 1. Capability coverage

The three examples (iris, TPC-H Q1 and ecommerce) were ported to narwhals: 117 lines, against 60 for ibis.

**Example results**, compared with ibis-duckdb as the reference:
- **Correct** on polars (eager and lazy), duckdb (both connection styles), sqlframe-duckdb and ibis-duckdb.
- **Failures:**

  | Backend | Score | Failure | Whose bug |
  |---|---|---|---|
  | pyspark / Spark Connect | 6/7 | boolean `.sum()` is rejected | narwhals |
  | sqlframe-postgres | 6/7 | `sum(boolean)` is rejected | narwhals |
  | ibis-polars via narwhals | 4/7 | no window functions | ibis |
  | ibis-postgres via narwhals | 4/7 | a cast inside `n_unique`, and a window-in-filter scope bug | narwhals and ibis |

- **Native ibis on the same examples:** duckdb 7/7, polars 4/7, postgres 5/7, pyspark 4.0 6/7. ibis's own SQL compiler isn't clean outside duckdb either.

**72-operation probe.** "ok" counts operations that match the reference. "Silent" counts operations that run but return wrong values.

| Backend | ok | silent | raises |
|---|---|---|---|
| nw: polars eager | 71 | 0 | 1 |
| nw: polars lazy | 68 | 0 | 4 |
| nw: duckdb | 65 | 2 | 5 |
| nw: duckdb (explicit connection) | 63 | 1 | 8 |
| nw: pyspark / Spark Connect | 62 | 1 | 9 |
| nw: sqlframe-duckdb | 63 | 1 | 8 |
| nw: sqlframe-postgres | 54 | 4 | 14 |
| nw: ibis-duckdb | 65 | 0 | 7 |
| nw: ibis-postgres | 61 | 0 | 11 |
| ibis: duckdb | 65 | 2 | 0 (5 n/a) |
| ibis: polars | 51 | 2 | 14 |
| ibis: postgres | 59 | 2 | 6 |
| ibis: pyspark | 64 | 1 | 2 |

**Missing in narwhals:**
- `dt.truncate("1w")`.
- `Expr.filter` inside an aggregation (`sum(where=...)`) on SQL backends.
- `first(order_by=)`.
- Lazy `pivot`.
- `map_batches` UDFs on SQL backends.
- `join_asof` on Spark and sqlframe.
- `dt.total_*` on Spark and ibis.
- `fill_null(strategy=)` on ibis.
- Unsigned casts on Spark.

On duckdb, ibis covers all of these, so it is roughly a superset of narwhals there.

**Upstream narwhals bugs found** (none had been reported; candidates for `dev/contributions/`):
1. **duckdb `dt.total_seconds()` / `total_minutes()` (silent).** It ignores days and hours: 1,260 where polars returns 8,979,660.
2. **Spark and sqlframe `dt.weekday()` (silent).** Sunday is 0 instead of ISO 7.
3. **duckdb `unpivot` (silent).** It drops null values: 86 rows instead of 120.
4. **Boolean `.sum()` on Spark and Postgres (raises).**
5. **duckdb relations from a non-default connection (raises).** `top_k`, `unpivot` and `join_asof` fail. Issue #3997 fixed only `concat`.

**sqlframe-postgres:**
- It lacks `substr`, `contains`, `count_if` and `last_value`.
- `str.split` silently doesn't split.
- `collect` needs Arrow.

**SQL warehouses (compile-only; no credentials):**
- The ports compile to BigQuery, Snowflake, Databricks and Postgres via sqlframe and via ibis.
- Redshift compiles only through sqlframe.
- On a real Postgres, sqlframe passed 54/72 operations and ibis-via-narwhals 61/72.
- Spark Connect matches classic PySpark.
- sqlframe is real but young: about 59k downloads a month and seemingly a single maintainer.

## 2. Native frames

**What exists** (`src/tacit_nw/_native.py`):
- `tc.tag(Orders, native)` validates a native frame in one query and returns the same native type. Accepted inputs:
  - polars eager or lazy
  - duckdb
  - pyspark
  - sqlframe
  - ibis
- `PolarsFrame[S]`, `PolarsLazyFrame[S]` and `SparkFrame[S]` are static tags that subclass the native frame classes.
- `Orders.amount` (class access) is the column name as a `str`, so `pl.col(O.amount)` and `F.col(O.amount)` are typo-checked.
- `@tc.step` conforms and parses tagged frames.

**Results:**
- The ecommerce example in native polars and in native PySpark matches the reference.
- 29 tests pass across 7 backends.
- 0 diagnostics on all four checkers, apart from a pyspark stub bug (`countDistinct` not exported).

**What the checkers catch on native code** (`tests/typecheck/t_native.py`):
- **Caught on all four checkers, 9/9:**
  - typos made through the schema;
  - the wrong schema's frame;
  - an untagged frame;
  - a Spark frame passed into a polars step;
  - forgetting to re-tag after `with_columns`. polars and pyspark annotate their methods as returning the concrete class, so every operation drops the tag. `filter` drops it too, so users re-tag with `validate=False`.
- **Missed on every checker, 0/5:**
  - raw-string typos, such as `pl.col("amout")`;
  - dtype misuse, because `pl.Expr` and pyspark `Column` carry no dtype;
  - PySpark's `df.amout`, because pyspark's `__getattr__` returns a `Column` for any name.

**So, over native code, column typing reaches the name level only.** Dtype-level typing over native code would need a separate facade for each engine:
- polars has 223 Expr methods;
- pyspark has 580 functions in a style that doesn't chain.

## 3. Typing

**Plain narwhals:**
- Results are identical on all four checkers, mypy included.
- `Expr` has no dtype, so tacit would still need a column facade.
- Frames have no column `__getattr__`, so `lf.amount` is an error everywhere.
- Method typos are caught.
- Schema-changing methods return `Self`, so `with_columns` keeps the input's type.

**T2 on narwhals** (`src/tacit_nw`, about 1,000 lines, including a hand-written facade subset):
- `DataFrame[S]` is a runtime subclass of `nw.LazyFrame`, built on three private names: `_with_compliant`, `_compliant_frame` and `_level`.
- `filter`, `sort`, `head`, `tail`, `unique`, `drop_nulls` and `top_k` keep the `DataFrame[S]` type.
- `df.c.amount` is `Column[float]` over `nw.col`.
- `build`, `extend`, `parse`/`conform` and generic steps all work.
- `isinstance(df, nw.LazyFrame)`, `nw.to_native` and `nw.concat` work both statically and at runtime, so the `as_table` false positive seen with ibis is gone.

**The stub is still needed, for a different reason.**
- `tools/gen_frame_stub.py` (107 lines) rewrites `Self` to `LazyFrame[Any]` on the 11 schema-changing methods. Its output is 30 lines, with 0 hand fixes.
- Without the stub, `with_columns` would claim to return `DataFrame[Orders]`, which is a lie. "Forgot cast" would then be missed on all four checkers.

**Matrix** (`tests/typecheck/t_nw.py`: 27 expected errors, 29 reveals):

| | pyright | mypy | ty | pyrefly |
|---|---|---|---|---|
| errors caught | 27/27 | 27/27 | 25/27 | 27/27 |
| false positives | 0 | 0 | 0 | 0 |
| reveals correct | 29/29 | 29/29 | 27/29 | 29/29 |
| without the stub: caught / FP | 25 / 1 | 25 / 1 | 23 / 0 | 25 / 1 |

- **ty's gaps:** it doesn't resolve the overloaded descriptor on class access, and it misses one `dt` method used on a str column.
- **A raw frame passed where `DataFrame[S]` is expected is caught on all four checkers.** With ibis this was pyright-only.
- **Example ports:** 0 diagnostics on all four. They pass on every backend except ibis-polars (windows) and ibis-postgres (the `n_unique` cast).
- **Facade caveat:** the prototype's facade is a hand-written subset of about 60 methods. Production would need E11's derive-by-execution generator retargeted at narwhals and run on several backends, because result dtypes differ between backends.

## 4. Validation

**tacit's fused executor over narwhals** (`src/tacit_nw/_validate.py`, about 100 lines):
- One `select` computes all the failure counts.
- A bounded sample query runs only for failing checks.
- Sums use `when/then`, because of bug 4.

**Results at 1M rows:**

| | valid | 0.1% bad |
|---|---|---|
| tacit on polars | 1 collect, 0.07 s | 3 collects, 0.07 s |
| tacit on duckdb | 1 query, 0.16 s | 3 queries, 0.15 s |
| tacit on ibis-duckdb | 1 query, 0.17 s | 3 queries, 0.20 s |
| pandera narwhals backend, polars | 11 collects, 0.08 s | 21 collects, 0.17 s |
| pandera native backend, polars | 21 collects, 0.13 s | 23 collects, 0.13 s |
| pandera narwhals backend, ibis-duckdb | 11 queries, 0.38 s | 17 queries, then **RelationError** |
| pandera native backend, ibis-duckdb | 10 queries, 0.29 s | 14 queries, 0.45 s |
| **tacit on PySpark** | **6 Spark jobs, 2.9 s** | **19 jobs, 3.5 s** |
| **pandera on PySpark** | **40 jobs, 5.4–5.8 s** | **83–115 jobs, 4.9–7.8 s** |

**Notes on these numbers:**
- **One query is not one Spark job.** With adaptive execution on, an aggregate costs 2 jobs, or 3 when it includes a count-distinct. Each sample query costs several more.
- **pandera on Spark needs pandas < 3.**
- **pandera's lazy validation footgun.** On lazy inputs, pandera validates SCHEMA_ONLY by default, so bad data passes unless `PANDERA_VALIDATION_DEPTH=SCHEMA_AND_DATA` is set.
- **No dataframe-agnostic API yet.** pandera main has no `pandera.dataframe` API from spec #2401 yet; it has added a DataFusion backend instead.
- **pandera's narwhals builtin checks** plug into the fused select unchanged.

**Coercion:**
- narwhals has no `try_cast`, so a value that fails to cast raises everywhere: polars, duckdb, sqlframe, ibis, and Spark 4 in ANSI mode. Spark with ANSI mode off was not tested.
- So tacit can coerce, but can't portably report how many rows failed to coerce.
- **Regression:** narwhals schemas carry no nullable flag, so `conform` can't check NOT NULL structurally. Only `parse` can.

## 5. Performance

**Expression building:**
- native polars: 0.14 ms
- narwhals on polars: 1.5 ms
- tacit_nw on polars: 1.9 ms
- native duckdb: 2.9 ms
- ibis: 6.7 ms
- narwhals on duckdb: 14.5 ms
- ibis including SQL compilation: 29 ms

All of these are negligible next to execution.

**Execution** (median seconds; in-memory inputs):

| Engine | Q1 1M | Q1 10M | ecommerce 1M | ecommerce 10M |
|---|---|---|---|---|
| native polars | 0.020 | 0.205 | 0.237 | 3.34 |
| narwhals → polars | 0.021 | 0.209 | 0.236 | 3.53 |
| native duckdb SQL | 0.031 | 0.282 | 0.215 | 2.77 |
| narwhals → duckdb | 0.037 | 0.283 | 0.289 | 3.31 |
| ibis → duckdb | 0.040 | 0.283 | 0.243 | 2.82 |
| narwhals → ibis → duckdb | 0.045 | 0.303 | 0.290 | 3.12 |
| ibis → polars | 0.066 | 1.29 | no windows | no windows |

- narwhals adds 0–6% over native polars.
- On duckdb it adds up to about 20% on window-heavy queries. ibis adds about 2%.

## 6. Project health

**narwhals:**
- **Releases:** 216 in total, 24 in the last 12 months, one every 2–4 weeks. Latest is 2.27.1 (2026-10-10).
- **Activity:** about 496 human commits in the last year; 9 contributors have 5 or more. Lead maintainers are FBruzzesi and MarcoGorelli.
- **Trend:** velocity is falling gently, from 140–180 commits a month in early 2025 to 22–73 a month in 2026, but from a high base.
- **Funding:** independent, with credits to Quansight Labs, OpenTeams, POSSEE, BYU-Idaho and Intella.
- **Stability policy:** *"If you write code using `narwhals.stable.v1` or `narwhals.stable.v2` … we promise to never change or remove any public function you're using."*
- **Hard dependency of:** scikit-learn 1.9, plotly 7, altair 6, marimo, bokeh, shiny, panel, vegafusion, formulaic, fairlearn, darts, scikit-lego.
- **Optional extra of:** pandera.
- **Downloads last month:**
  - narwhals: 113M (mostly transitive)
  - polars: 51M
  - pyspark: 48M
  - pandera: 8.4M
  - ibis: 3.3M
  - sqlframe: 59k

**ibis (from E12):**
- No release in 258 days.
- External PR merge rate of 20%.
- The two incompatibilities found above.

## 7. Options

| | (a) stay on ibis (T2) | (b) narwhals only | (c) narwhals primary, ibis as a backend | (d) ibis primary, narwhals at boundaries |
|---|---|---|---|---|
| What users write | `df.c.x` + ibis API + `_` | `df.c.x` + narwhals API, plus native tag/step | same as (b) | ibis inside; native frames at parse |
| Backends | about 20 ibis SQL backends; polars without windows; PySpark < 4.1 | polars, duckdb, PySpark 4.x, Spark Connect, sqlframe (young) | (b) plus everything ibis reaches | ibis's |
| Typing | 38/37/37/37 (E13); mypy needs a flag; raw tables caught by pyright only | 27/27 on pyright, mypy and pyrefly, 25/27 on ty; raw frames caught everywhere; native code checked at name level | same as (b) | as (a), plus name-level native tags |
| Validation | hybrid on ibis internals | about 100–250 lines of narwhals expressions; Spark 6 jobs against pandera's 40 | same as (b) | two executors |
| Lost | – | ibis breadth, week truncation, filtered aggregates, ordered `first`, lazy pivot, UDFs, NOT NULL-aware `conform`, coercion failure counts | the same on direct backends; ibis still reachable | – |
| Effort | as in the report | 6–9 weeks | (b) plus about 0.5 week | (a) plus 1–2 weeks |
| Risks | ibis velocity; dependency breakage; no PySpark 4.2 | 5 upstream bugs; per-backend drift; sqlframe maturity; 3 private narwhals names | (b) plus ibis compiler bugs leaking through | two engines; PySpark users stuck |

**What the (b)/(c) effort covers:**
- **Runtime:** about 1,200–1,400 lines (about 1,000 already exist in the prototype).
- **Stub generator:** done.
- **Derived facade generator:** about 700 lines.
- **Conformance and parity harness:** about 900 lines.
- **CI:** the 72-operation probe.
- **Upstream:** the five narwhals fixes.
- **Docs and examples:** migrate to narwhals syntax.

**Conditions for (c):**
- Pin `stable.v2`.
- Upstream the five bugs, the three silent ones first.
- Run the operation probe per backend in CI, and document the unsupported-operation table.
- Treat sqlframe on warehouses as "compiles, partially executes". Steer BigQuery and Snowflake users through ibis-via-narwhals.

**When (a) would be better:** if the users turn out to be mostly SQL-warehouse analysts rather than PySpark and Polars engineers.

**Not done:**
- Real warehouse runs.
- A derived narwhals facade and its conformance run.
- Spark with ANSI mode off.
- Re-running the planted bugs.
- Checking editor autocomplete.
