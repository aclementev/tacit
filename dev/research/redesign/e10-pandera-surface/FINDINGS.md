# E10 — pandera's feature surface vs a native validator, tuned pandera, and a hybrid

> The E10 subagent (Opus) returned this report as text, and the main session saved it here.
> The main session re-ran the parity battery (`cd e10-pandera-surface && PYTHONPATH=../e4-runtime uv run --frozen python parity.py duckdb`) and got 685 cases: 682 MATCH, 2 COUNT-DIFF (by design) and 1 MISMATCH (the empty-table case, deliberate). Data queries: pandera 2,827, hybrid 1,220.
>
> Environment: Python 3.13, pandera 0.34.1, ibis 12, duckdb in-memory. The box was shared with other running experiments, so timings are the minimum over repeated runs. `run_bench.sh` and `run_bench2.sh` reproduce them.

**Short answer.**
- **Scope:** E4 understated it. Its ~150-line validator covered about 20% of what pandera's ibis backend does, and its parity was tested on one schema.
- **Performance:** E4's claim holds. Tuned pandera cannot close the gap, because pandera's ibis backend runs one query per check.

**Recommendation:**
- **(B), a hybrid:** pandera stays the check library and spec, and tacit executes the checks in one fused query. It is 213 code lines, matches 682 of 685 parity cases, and runs within about 10% of the native validator's speed.
- **(D), in parallel:** contribute single-query execution upstream.

## Q1. Feature inventory (pandera ibis backend on duckdb)

Columns:
- **ibis (native / nw):** pandera's native ibis backend, or its narwhals backend.
- **tacit:** whether tacit exposes the feature today.
- **C needs?:** whether a fully native validator (option C) would need it.
- **LOC for C:** rough lines of code for C to reach parity.

| Feature | ibis (native / nw) | tacit | C needs? | LOC for C |
|---|---|---|---|---|
| 15 builtins (eq, ne, gt, ge, lt, le, in_range/between, isin, notin, str_matches, str_contains, str_startswith, str_endswith, str_length, unique_values_eq) | work, with bugs: interval comparisons raise CHECK_ERROR on duckdb; unique_values_eq fails on NULL (fixed in #2538, after 0.34.1); str_matches anchors only the first alternative (#2533) | yes (`pa.Check` passthrough) | yes | ~70 |
| NaN handling | non-null checks treat NaN as a value (`ge` passes it; `le`/`in_range`/`isin` fail it); `nullable=False` treats NaN as null | inherited | yes | 5 |
| `ignore_na` | True works; **False has no effect** on builtins | passthrough | yes | 5 |
| `raise_warning`, `n_failure_cases`, name/error/title | work (nw: `n_failure_cases` crashes) | passthrough | yes | 15 |
| `element_wise` | only with an annotated function (python UDF) | passthrough | maybe | 10 |
| `groupby` | accepted, then **silently ignored** | passthrough | no | 0 |
| Custom `Check(fn(IbisData))` returning a column, table, dict, scalar or bool | works | passthrough | yes | 50 |
| `register_check_method` | works | via passthrough | own registry | 25 |
| dtype check | exact equality, so `timestamp(6)` vs `timestamp` is wrongly rejected | tacit checks structure itself | yes | 20 |
| nullable (+NaN) | works | `Nullable()` | yes | 8 |
| `Column(unique=True)` | **ignored** (native); works on nw | no | yes | 5 |
| `coerce` | **ignored** on both backends (docs claim otherwise) | tacit casts itself | yes | 30 |
| `required`, regex columns | work | no | optional | 15 |
| `default=` | ignored (native) | no | optional | 5 |
| `strict` (incl. `"filter"`), `ordered` | work | `strict=True` only | yes | 20 |
| schema `unique=[...]`, `report_duplicates` | duckdb works; polars raises | no | yes | 20 |
| dataframe-level checks | work | no | yes | 15 |
| `drop_invalid_rows` | works | no | optional | 15 |
| `add_missing_columns`, head/tail/sample, parsers | not implemented or ignored | no | no | 0 |
| `lazy=True` `SchemaErrors` (pandas failure_cases, JSON message, reason codes) | works, needs pandas; nw: `RelationError` when errors are mixed | mapped by `errors.py` | own report | 100 |
| `validation_depth=SCHEMA_ONLY` / `validation_enabled` | works (0 queries) / no-op | no | optional | 10 |
| DataFrameModel, Field, Config, `check_types` | work | no (tacit has its own) | no | 0 |
| yaml/json/to_script IO, `infer_schema` | work | no | no | 200–300 if wanted |
| Hypothesis strategies | NotImplementedError on ibis | – | – | – |
| Empty table | **false failure**: `bool_and` over 0 rows is NULL | inherited | – | – |

**What tacit exposes today:** `pa.Check` objects passed straight through, plus nullability, dtype and `strict=True`. Most schema-level pandera features never reach tacit users. In practice, only the Check library flows to them "for free".

**How much has flowed for free on ibis:**
- All 15 ibis builtins landed between January and May 2025, and none has been added since.
- 2026 activity on the ibis backend is bug fixes (#2296, #2269, #2538) and the narwhals migration.
- "Free" has meant about one bug fix a month.

## Q2. What E4 and E8 actually covered

**E4 (`ibisval`):**
- 14 of 15 builtins, nullable/NaN, unique, `try_cast` coercion and samples.
- Custom checks raise `KeyError`.
- No Check options.

**E8 (`_validate`):**
- 9 of 15 builtin kinds.
- One custom-check shape.
- unique, dtype, and missing/extra columns.

**Non-check features:** of the ~28 that work in pandera's native ibis backend, E4 covered about 3 and E8 about 6.

**Testing:** E4 tested its own parity only on its 9-check schema, covering 6 builtin kinds on 3 dtypes.

**Re-run on a 330-case builtin battery:**

| Result | E4 | E8 |
|---|---|---|
| agrees with pandera | 246 | 168 |
| unsupported | 56 | 140 |
| both error (interval) | 26 | 18 |
| disagrees | 2 | 4 |

The predicate semantics are essentially right. The understatement is in scope.

**Hidden divergence: NULLs in `unique`.** There are three different semantics:
- pandera: two NULLs count as a duplicate.
- E4: a single NULL fails.
- E8: NULLs are ignored.

## Q3. Performance (queries / minimum wall time in seconds)

Configurations:
- **A0:** current tacit.
- **A1:** pandera with `lazy=True` and `n_failure_cases=5`.
- **A2:** A1, plus cast once and materialize.
- **B:** hybrid.
- **C:** E4 native validator.

| Data | A0 | A1 | A2 | B | C |
|---|---|---|---|---|---|
| 1k valid | 16 / 0.137 | 16 / 0.149 | 18 / 0.127 | 1 / 0.025 | 1 / 0.017 |
| 1k bad | 30 / 0.294 | 30 / 0.359 | 32 / 0.317 | 2 / 0.071 | 2 / 0.054 |
| 1M valid | 16 / 0.42 | 16 / 0.42 | 18 / 0.59 | 1 / 0.133 | 1 / 0.124 |
| 1M 0.1% bad | 30 / 1.84 | 30 / 1.35 | 32 / 1.86 | 2 / 0.27 | 2 / 0.255 |
| 10M valid | 16 / 3.84 | 16 / 3.22 | 18 / 4.74 | 1 / 1.10 | 1 / 0.98 |
| 10M 0.1% bad | 30 / 9.50 | 30 / 8.53 | 32 / 10.18 | 2 / 1.41 | 2 / 1.39 |
| 1M CSV view (varchar) | 16 / 13.4 | 16 / 10.6 | 18 / **1.75** | 1 / 0.98 | 1 / 1.02 |
| 1M, pandera narwhals backend | 16 / 0.25 (valid) | lazy bad: 37 / 0.54, then `RelationError` | – | 1 / 0.15 | – |

**What tuning buys:**
- `lazy=True` with capped failure cases gives 10–25% on the failure path and nothing on valid data. pandera still fetches N booleans for every failing check.
- Materializing is a real 7.6× win for file-backed sources, but it costs about 40% on in-memory tables. **tacit should materialize file sources regardless of which option it picks.**
- Overall, tuning recovers about 1.1–1.4× of a 3–7× gap. The rest is inherent to pandera's execution model.

**Import time:**
- `import tacit`: 3.51 s, against 1.24 s for `import ibis`.
- A lazy pandera import moves about 2.3 s to the first `parse()`. B still pays about 2.1 s there, because `pandera.api.checks` imports pandas.
- Only C removes the import cost entirely.

**B vs C:** B is 5–15% slower than C at 1M+ rows, with about 8 ms more fixed cost (its schema-only pandera pass).

## Q4. Hybrid prototype (`hybrid.py`, 213 code lines)

**How it works.**
- **Structural checks** (dtype, strict/filter, ordered, required, presence) are delegated to pandera itself under `config_context(validation_depth=SCHEMA_ONLY)`, with 0 data queries.
- **Data checks:** every column and dataframe check is evaluated with pandera's own check function, `check._check_fn(IbisData(t, key), **check._check_kwargs)`, and its output is normalized into a boolean ibis expression.
- **Fused query:** pandera's `ignore_na`, table-AND and `.all()` NULL semantics are reproduced exactly. Nulls (with the IsNan rule), column and schema `unique`, and every check go into **one** `t.aggregate`.
- **Samples:** a bounded sample query runs only when something fails.
- **Robustness:**
  - A check that raises becomes CHECK_ERROR.
  - If the fused query fails, items are re-run individually to isolate the bad one.
  - Outputs that can't be fused fall back to pandera's own `CheckBackend`.
- **`drop_invalid_rows`** is provided as a lazy filter.

**Parity vs `pandera.validate(lazy=True)`.** The battery covers every builtin × {int, float+NaN, decimal, string, date, timestamp, timestamptz, time, interval, boolean} × null/no-null × nullable × `ignore_na=False`, plus 18 custom/option cases and 7 dataframe-level/unique cases.

| Reference | Cases | Match | Differences |
|---|---|---|---|
| duckdb, native backend | 685 | 682 | 2 by design (`n_failure_cases`: B reports the true count; one table-returning lambda falls back to pandera); 1 deliberate (an empty table passes in B, while pandera wrongly fails it) |
| polars | 613 | 608 | 3 where pandera crashes on schema unique and B works; 2 by design |
| duckdb, pandera narwhals backend | 685 | 677 | 7 where pandera-narwhals raises CHECK_ERROR and B works |

**APIs B relies on:**
- Public: `Check` attributes, `schema.columns`, `.checks`, `.unique`, `config_context`, `IbisData`, `Check.__call__`.
- Undocumented: `Check.get_builtin_check_fn`, `is_builtin_check`.
- **Private:** `_check_fn`, `_check_kwargs`.
- Semantics copied from `backends/ibis/checks.py`.
- ibis internals: `ops.Project`, `op().relations`, `ops.IsNan`.

**Observed fragility:** switching on pandera's narwhals backend removed the `IbisData` builtin dispatch, so every check became CHECK_ERROR. A 12-line narwhals path fixed it: builtins become `nw.Expr`, compiled back to ibis. `hybrid_nw.py` (41 lines) shows that pandera's narwhals builtins fuse into one `select` with identical counts.

## Q5. Upstream

- **No issue or PR exists about batching ibis checks.** The nearest are #1879 (pandas overhead, fixed within days by #1882) and #1399 (polars lazy validation, open).
- **Spec #2401** (merged 2026-10-05) defines a dataframe-agnostic `pandera.dataframe` API on narwhals, phasing out per-library backends in the order **ibis → polars → pyspark → pandas**.
  - The native ibis backend goes first.
  - Known narwhals gaps: coerce is a no-op; no defaults or `add_missing_columns`, no groupby, no element-wise on SQL backends, no IO, no strategies.
- **A single-query contribution is plausible.**
  - Builtins are pure expressions, the backend's principle is "lazy stays lazy", and the maintainer is responsive.
  - The natural place is the narwhals `run_checks`/`ColumnBackend`. Estimated size: about 300–500 lines plus tests.
  - Next step: open an issue first. It can't be relied on for a release timeline.
- **Candidates for `dev/contributions/`:**
  - An empty table fails validation.
  - `timestamp` vs `timestamp(6)` is a false mismatch.
  - Interval comparisons raise CHECK_ERROR on duckdb.
  - `Column(unique)`, `coerce`, `default` and parsers are silently ignored.
  - `ignore_na=False` has no effect.
  - `update_column` raises NotImplementedError.
  - `validation_enabled` is a no-op.
  - Narwhals backend: lazy `RelationError`, `n_failure_cases` crash, and broken element-wise and table-output checks.

## Q6. Options

| Option | Initial work | Ongoing cost | Flows through for free | Performance |
|---|---|---|---|---|
| A: keep pandera, tuned | ~20 lines | absorb pandera bugs and the forced narwhals switch | everything, bugs included | 16–30 queries; 3–7× slower; +2.1 s on first use |
| B: hybrid | ~220 lines + error mapping; parity battery exists | private attrs and copied semantics; run `parity.py` against every pandera release | builtins and their fixes, registered/custom checks, Check options, structural features | ≈ C (5–15%); +2.1 s on first use, deferrable |
| C: native | ~450–550 lines + ~500 test lines | track semantics yourself (~1 upstream fix a month to mirror) | nothing; lose `register_check_method` and familiarity with `pa.Check` | best; −2.1 s import; fully typed check API |
| D: batch upstream, keep pandera | issue + PR, ~300–500 lines, uncertain timeline | lowest once merged | everything | ≈ B once merged |

**Did E4 understate the work?** Yes on scope and testing: realistic parity is about 3× the claim, plus a test battery. No on performance: tuned pandera cannot close the gap.

**Recommended path:**
1. **Ship B.** tacit's Check declarations become pandera Checks lazily, on the first `parse()`, so that `import tacit` costs about the same as `import ibis`. Keep `parity.py` in CI, run against pandera releases.
2. **Pursue D in parallel.** If it lands upstream, delete B's executor and return to A, at B's speed. That is the "thin glue" end state.
3. **Choose C only if** dropping the 2 s pandas import, or a fully typed check API, outweighs the ecosystem.
