# E11: Is the generated column facade sound, and can it stay cheap to maintain?

> The E11 subagent (Opus) returned this report as text. The main session saved it here and checked the key claims:
> - The conformance summaries in `out/conformance_{e8,derived}_pyright.txt` match the numbers below.
> - `probes/p2_null_lie.py` reproduces a NOT NULL field holding NULLs. The code type-checks clean, and only `Flags.parse` catches the problem.
> - Large regenerable outputs (`out/*.json`, `conformance/gen_*`, `conformance/cfg_*`) are gitignored. `run_all.sh` regenerates them.
>
> Environment: ibis 12.0.0, duckdb 1.5.6, pyright 1.1.414, mypy 2.4.0, ty 0.0.89, pyrefly 1.4.0. The version diff used ibis 10.8.0, 11.0.0 and main at `90656f7`.

## Verdict

**The hand-written E8 facade is not sound, and nothing checks it.** The conformance harness found:
- 630 cases where a column declared non-null is NULL at runtime. These are silent.
- 62 cases where the declared value family is wrong. These fail loudly when the frame is constructed.
- 17 methods whose parameters have drifted from ibis. The most important is that every reduction is missing `where=`.

**The limits are static, not runtime.**
- At runtime, every ibis method works on a tacit column.
- In the type checker, 36–81 ibis methods per value family are attribute errors.
- Methods on Scalar values get almost nothing.

**It can be made sound and cheap.** A derived generator reads method names, parameters and family membership from ibis, and finds result types by calling ibis. On the same harness it produces:
- 0 null lies and 0 family lies.
- 24 false positives, down from 270.
- About 95% coverage of each scalar family, up from about 30%.

It keeps typo and wrong-method detection on all four checkers. Methods it can't type precisely fall back to ibis's own annotations, so the facade only adds precision and never removes access.

**The hand-written part shrinks to about 70 lines**, mostly nullability rules.

## 1. Coverage (ibis 12 public API vs the facade)

"Unreach" counts methods that exist on the ibis class but are a static error on `Column[T]`/`Scalar[T]`.

| Class | Methods / ops | E8 typed | E8 unreach | Derived typed | Derived unreach |
|---|---|---|---|---|---|
| IntegerColumn | 107 / 35 | 29 / 19 | **81** | 103 / 32 | 2 |
| FloatingColumn | 103 / 24 | 29 / 19 | 66 | 98 / 21 | 3 |
| DecimalColumn | 101 / 24 | 27 / 19 | 66 | 96 / 21 | 3 |
| StringColumn | 96 / 14 | 30 / 8 | 59 | 92 / 10 | 3 |
| BooleanColumn | 108 / 31 | 32 / 26 | 68 | 105 / 28 | 1 |
| TimestampColumn | 73 / 13 | 27 / 6 | 40 | 68 / 10 | 3 |
| DateColumn | 66 / 13 | 24 / 6 | 36 | 62 / 10 | 2 |
| TimeColumn | 62 / 13 | 18 / 6 | 37 | 51 / 6 | 13 (duckdb rejects them) |
| `*Scalar` (8 families) | 36–70 / 12–34 | **6** / 6–26 | 17–56 | 24–65 / 6–32 | 0–11 |
| Interval / Array / Struct / Map / JSON | 53–72 / 9–17 | 0 | 32–56 | 0 | same |

**Common methods E8 is missing:**
- Math: `log`, `ln`, `exp`, `sqrt`, `pow`/`**`, `sign`.
- Window and ranking: `cumsum`, `lag`, `lead`, `rank`, `dense_rank`, `ntile`.
- Aggregates: `quantile`, `mode`, `approx_*`, `argmin`, `argmax`.
- Strings: `split`, `like`, `ilike`, `concat`, `lpad`, `rpad`, `find`, `re_replace`, `left`, `right`, `as_date`, `as_timestamp`.
- Date and time: `minute`, `second`, `quarter`, `day_of_week`, `delta`, `bucket`, `ts - ts`, `ts + interval`.
- Every Scalar method, for example `o.amount.mean().round(2)`.
- The `where=` argument on reductions.

**What an uncovered method does today:** it is an error on all four checkers. The result is then `Unknown` (or `Any` on mypy), so everything after it is unchecked.

## 2. Conformance harness

The harness lives in `conformance/`: `cases.py`, `runtime.py`, `static.py`, `compare.py`. It runs 169 templates × 8 families × {nullable, non-null} × {Column, Scalar} receivers, for 5,408 cases.

- **Runtime side:** each case is built on real columns and executed on duckdb. Each run includes an all-NULL group, a single-row group, and an empty global aggregate. The harness then counts the NULLs in the result.
- **Static side:** each case gets a `reveal_type`, and the output of all four checkers is parsed.
- **Agreement:** the four checkers agree on 5,372 of the 5,408 cases, so CI can run pyright only.

| Category (severity) | E8 | Derived |
|---|---|---|
| NULL_LIE: declared non-null but NULL at runtime (**HIGH**, silent) | **630** | **0** |
| FAMILY_LIE: wrong value family (MED, loud at construction) | **62** | **0** |
| ACCEPT_ERROR: type-checks, but ibis raises when building | 226 | 136 |
| ACCEPT_BACKEND: type-checks, but the duckdb binder rejects it | 334 | 296 |
| EMPTY_NULL: non-null reduction over empty global input (LOW) | 36 | 34 |
| WIDER: imprecise declared type (LOW) | 120 | 24 |
| FALSE_POS: rejected statically, fine at runtime (LOW) | 270 | 24 |
| ok | 3,730 | 4,894 |

### Null lies in the E8 facade

1. Comparisons, `between`, `isin`/`notin`, `contains`/`startswith`/`endswith`/`re_search`, and `&`/`|`/`^` are always typed `Column[bool]`. With a nullable operand they actually return NULL. That includes a non-null column compared against a nullable one.
2. `cast` drops nullability: `Column[float | None].cast("float64")` is typed `Column[float]`. E8's FINDINGS claimed the opposite.
3. Reductions on nullable columns (`min`, `max`, `first`, `sum`, `mean`, `median`, `any`, `all`) are typed non-null. They return NULL for an all-NULL GROUP BY group. The stub comment "never for GROUP BY groups" is wrong.
4. `std()` and `var()` return NULL for a single-row group.

### Family lies in the E8 facade

Each of these type-checks clean, then fails at construction with `expected dtype decimal, got float64` (`probes/p5_family_lie.py`):

| Expression | E8 declares | ibis returns |
|---|---|---|
| `Decimal / x` | Decimal | float64 |
| `Decimal // x` | Decimal | int64 |
| `int.round(n)` | int | float64 |
| `Decimal.std` / `.var` / `.median` | float | decimal |
| `-bool` | int | boolean |
| `bool.median` | float | boolean |

### Code that type-checks but fails at runtime

E8 and derived counts are given in parentheses.
- `bool` is a subtype of `int`, so arithmetic on `Column[bool]` matches the int overloads (236 / 222). This is inherent to using Python `bool` as `T`.
- `==` across families falls back to `object.__eq__` (64 / 64).
- Casts to an unsupported family (68 / 0).
- String-literal casts to a wrong pair, e.g. int to `"date"` (56 / 56).
- `x OP None` (72 / 0).
- `.over()` on a non-analytic column (14 / 14).
- `asc`/`desc` on a Scalar (24 / 24).

### Other findings

**False positives (270 in E8):**
- Every Scalar method.
- `Decimal.ceil`, `.floor` and `.round()`.
- Integer bitwise operators and `~`.
- `str * int`.
- `Decimal + 1.5`.
- `between` and `isin` on Scalars.

**Parameter drift** (`sigcheck.py`), comparing E8's declarations with ibis's signatures:
- Missing `where=`: on `sum`, `mean`, `min`, `max`, `count`, `nunique`, `any`, `all`, `median`, `std`, `var`, `first`.
- Missing `how=`: on `std` and `var`.
- Missing `rows=` and `range=`: on `over`.
- Missing `include_null` and `order_by`: on `first`.
- Missing `by` and `name`: on `topk`.
- Positional-only in E8, though ibis accepts keywords: `between` and `replace`.

**ibis's `dtype.nullable` is useless as an oracle.** Of the agreeing non-null declarations, 645 of 728 have `nullable=True` in ibis. Nullability can only be verified by execution.

## 3. Derived generator (`derived/gen_derived.py`, 616 lines, plus `make_pkg.py`)

The output is an ~8.3k-line `.pyi`. E8's hand-written stub was 1,073 lines.

**Read mechanically from ibis:**
- Which methods and operators exist, per family and container (via `dir()` of `ir.<Fam>Column`/`Scalar`).
- Parameter names, kinds and defaults (via `inspect.signature`).
- Parameter types, mapped from ibis's annotations: `XValue` becomes `x | Column[x] | Scalar[x]`, and `Deferred` is dropped.
- The result container and value family, found by calling each method on a sample column. Results outside tacit's families keep ibis's class, for example `split` returns `ArrayColumn` and `ts - ts` returns `IntervalColumn`.
- Operator operand matrices.
- Valid cast pairs.
- Argument-dependent variants, such as `round()` returning int but `round(n)` returning float.

Every candidate is executed once on a one-row duckdb table, and pairs the backend rejects are omitted.

**Still hand-written (~70 lines):**
- Nullability rules:
  - Propagate by default.
  - Never-null set: `isnull`, `count`, `nunique`, rank, ...
  - Always-nullable set: `try_cast`, `nullif`, `lag`/`lead`, `std`/`var`/`corr`, `first`/`last`, ...
- About 25 sample-argument overrides.
- The skip list.
- The descriptor, `ifelse` and `fill_null`, copied from E8.
- The dtype strings accepted by `cast`.

**Results:**
- 155 methods derived, plus 32 operator dunders.
- 14 methods fall back to ibis's own annotations.
- E8 bug matrix: identical detection on all four checkers (14/14/14/13).
- Examples: 0 errors on all four checkers.
- E8's 185-case matrix scores 181 on pyright (mypy 178). The four differences:
  - `str * 2` and `Decimal + 1.5` are now accepted. Both are valid ibis, so E8 was stricter by policy. A small DENY table can restore that if wanted.
  - `o.discount.sum()` is now `Scalar[float | None]`, and `o.discount > 0` is now `Column[bool | None]`. These are the soundness fixes.
- API consequence: `Frame.filter`, `join(on=)` and `tc.check` must accept `Column[bool | None]`, because SQL treats NULL as false.

**Checker time on the ecommerce example:**

| Checker | E8 facade | Derived facade |
|---|---|---|
| pyright | 4.2 s | 4.2 s |
| mypy | 12.1 s | 13.2 s |
| ty | 0.3 s | 0.4 s |
| pyrefly | 0.6 s | 1.1 s |

**Fallback modes for methods the generator can't type** (`probes/p3_fallback.py`, all four checkers):
- `--fallback ibis`: an uncovered method gets ibis's own type, and later misuse is still caught.
- `--fallback any`: types it as `Any`, and later misuse is lost.
- In every mode, a wrong-family call or a typo is still an error, because the overloads are restricted by self-type.
- **Recommended default: `ibis`.**

**Residual unsoundness in the derived facade:**
1. `bool` is a subtype of `int` (222 cases). Fixing it needs a non-`bool` marker type.
2. `==` across families falls back to `object.__eq__`.
3. `cast("str")` falls back to `Any`.
4. `.over()` needs an `Analytic[T]` type.
5. Global aggregates over empty input.
6. `datetime` is a subtype of `date`.

## 4. Maintenance cost of ibis upgrades

| Upgrade | Public API diff | Behaviour diff (harness cases) | E8 entries to touch | Derived generator |
|---|---|---|---|---|
| 10.8 → 11.0 | 4 removed (none in E8) | 24 (duckdb 1.2 → newer: time comparison, `between`, `fill_null` start failing) | 0 by API; 24 silently wrong under E8 | regenerates and omits the failing cases |
| 11.0 → 12.0 | 515 annotation-only changes across 108 names; 1 real change | **64: decimal-literal arithmetic, comparisons and `fill_null` went from error to working** | 0 by API; under ibis 11, E8 accepted the 64 failing cases | 680-line stub diff |
| 12.0 → main | +1 method (`tanh`, on 8 classes) | 0 | 0 (it stays unreachable) | +24 lines |

**ibis's API surface is stable. The real churn is behaviour**: dtype rules and backend support.
- The hand-written spec misses both kinds of change.
- The derived pipeline flags both automatically:
  - API changes: `introspect.py` plus `version_diff.py`.
  - Behaviour changes: `runtime.py` plus `runtime_diff.py`.
  - The exact typing delta: regenerate and diff the stub.
  - A CI gate: `compare.py`.
- Expected human work per ibis release since 10.x: about 0–2 table entries.

## 5. Does the facade limit features?

**At runtime: no.** `type(o.amount)` is `ir.FloatingColumn`. No public attribute is missing, and `log`, `split`, `minute`, `cumsum(order_by=)` and `**` all execute (`probes/p4_runtime_access.py`).

**Statically, with E8: yes.**
- An uncovered method is a hard error.
- The escape hatches are weak:
  - `tc.as_ibis(col).method()` is typed by ibis.
  - `tc.as_column(...)` is an unchecked assertion that types any `NumericValue` as non-null `Column[float]`.

**With the derived facade and `--fallback ibis`: no.**
- Every ibis method is typed, precisely where the probe succeeds and with ibis's own annotation otherwise.
- Only combinations the backend rejects stay unreachable.

## What it would take to adopt

1. Replace `tools/gen_facade.py` with the derived generator. Keep the small hand tables: nullability rules, sample arguments, skip list, TypeVar signatures, and policy denies.
2. Ship the conformance harness as a test, and run it on every ibis or duckdb upgrade. Gate on NULL_LIE = 0 and FAMILY_LIE = 0, and add `sigcheck` alongside.
3. Fix the nullability semantics:
   - Comparisons and `cast` propagate nullability.
   - Reductions propagate nullability.
   - `std`, `var`, `lag`, `first` and similar are always nullable.
   - `filter`, `join(on=)` and `tc.check` accept `Column[bool | None]`.
   - Empty-input aggregates are documented or validated.
4. Decide on these:
   - A marker type so `bool` isn't a subtype of `int`.
   - Strict string casts.
   - An `Analytic[T]` type for window functions.
   - `Column[list[V]]` and `Column[timedelta]`.
5. Multi-backend support: probe each target backend, since the probe currently runs on duckdb only. Give `as_column` per-family nullable overloads.

## Files

- **Coverage:** `introspect.py`, `facade_parse.py`, `coverage.py`, `out/coverage*.txt`, `versions/api_{10,11,12.0.0,main}.json`.
- **Harness:** `conformance/`; results in `out/conformance_*.txt`, with the JSON regenerable.
- **Parameter drift:** `sigcheck.py` → `out/sigcheck.txt`.
- **Generator:** `derived/gen_derived.py`, `derived/make_pkg.py`, `derived/out_{ibis,any,none}/`, `derived/gen_{10,11,main}/`.
- **E8 matrix runner:** `e8matrix/`, results in `out/matrix_*/`.
- **Timing and bug matrix:** `out/checker_timing.txt`, `out/bugs_matrix.txt`.
- **Probes:** `probes/p1..p5`.
- **Version diff:** `version_diff.py`, `runtime_diff.py`, `out/*version_diff.txt`.
- **Runner:** `run_all.sh`. Every step ran individually; the script itself was not run end to end.
