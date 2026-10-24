# E15: The completed T3 prototype and an end-to-end user experience

> The E15 subagent (Opus) returned this report as text. The main session saved it here and re-checked the headline claims:
> - `examples/e2e.py` reports 0 diagnostics on pyright, mypy, ty and pyrefly.
> - The pipeline runs.
> - 10 of 10 runtime tests pass.
> - The planted-bug check (`out/e2e_bugs_check.txt`) shows 7 of 8 bugs caught.
>
> `run_all.sh` regenerates everything.

## Bottom line

**T3 is complete.** It lives in `src/tacit_t3/`: 1,105 hand-written runtime lines on top of the derived facade (E11) and the generated Table stub (E13).

**The example.** `examples/e2e.py` is an idiomatic e-commerce pipeline. Its outputs match the plain ibis + pandera version up to float rounding.

**What it buys, compared with plain ibis + pandera:**
- **Static bug detection:** 7 of the 8 planted bugs are caught on all four checkers. The plain version catches none.
- **Schema-typed expressions:** 87% of the pipeline's data expressions, against 0%.
- **Validation:** about 6 times faster than pandera at 1M rows.
- **Total runtime:** 31% above unvalidated plain ibis.

**What it costs:** 52% more code (131 lines against 86).

**Where the real costs are:**
- the number of classes;
- untyped "islands" wherever raw ibis is used.

Runtime ergonomics are roughly equal to ibis, because the frame *is* an ibis Table.

## What T3 contains

| Piece | Status |
|---|---|
| E13 T2 base | `DataFrame[S]` is an ibis Table subclass with the generated stub. Includes `df.c`, `build`, `extend`, `parse` and `conform`. |
| E11 derived facade | Copied by `tools/patch_facade.py` with two hand rules: `assume_not_null()` and nullable `cases` predicates. |
| Validation | E10's hybrid. `field(ge, isin, pattern, ...)` is lowered to pandera Checks lazily, and `field(checks=[pa.Check...])` is passed through. Checks run in one fused query, plus a sample query on failure. Results go into `ValidationError.issues`. File-backed sources are materialised once. |
| Typed join | `tacit.join(a, b, on=lambda l, r: ... \| [(a.c.k, b.c.k)])` returns a `Join[L, R]`; the output is built with `Out.build`. |
| `aggregate(by=)` | Explicit grouping. `build()` raises when it is given a mix of reductions and plain columns. |
| `@tacit.step` | Understands `DataFrame[S]`, TypeVars, unions, tuples and lists. `validate=True` runs the data checks. Errors are annotated with the step name. |
| E9 fixes | `assume_not_null()` narrows the type and is verified when the output is built. Durations use `ts.delta(other, unit=...)`. |

The facade is isolated: one `_column.pyi`, swappable through `tools/patch_facade.py`.

### Type-check matrix (81 cases)

| | pyright | mypy | ty | pyrefly |
|---|---|---|---|---|
| E13's T2 cases (38) | 38 (1 FP) | 37 | 37 | 37 |
| New T3 cases (43) | 42 | 41 | 41 | 41 |
| Total | 80 | 78 | 78 | 78 |

Misses:
- A raw `ir.Table` passed as a frame (upstream).
- `Column[datetime]` passed into `Column[date]`, missed by all four. Python's `datetime` subclasses `date`; the runtime dtype check catches it at construction.
- ty reveals a `cases(...)` literal (cosmetic).

The one false positive is `x: ir.Table = df` (pyright and ty).

## The example

The full code is in `examples/e2e.py`. Its schemas:
- **Sources:** Customers and OrderEvents.
- **Derived:**
  - OrderMetrics + Orders;
  - DeliveryTime + DeliveredOrders;
  - OrderFacts;
  - MonthlyRevenue;
  - CustomerValue;
  - Rank + TopCustomers.

Its steps:

| Step | What it does |
|---|---|
| `keep_latest[S]` | generic, keeps the latest row per key |
| `add_metrics` | `extend` |
| `delivered` | filter + `assume_not_null` + duration |
| `with_customer` | typed join |
| `monthly_revenue` | `aggregate(by=)` with `count(where=)` |
| `customer_value` | raw ibis `group_by`/`mutate` with `_`, re-entered through `conform`, under `@step(validate=True)` |
| `top_customers` | rank via `extend` + filter |
| `run` | parse sources and write outputs |

## The runtime experience (`out/session.txt`)

**What it looks like interactively.**
- `isinstance(events, ir.Table)` is `True`.
- `repr` is ibis's own dump, with a `DataFrame[OrderEvents]` header line.
- In interactive mode, `head()` shows ibis's rich table.
- `dir(events.c)` lists only the columns.
- In `help(OrderEvents)`, the column list (with constraints and descriptions) is readable; the rest is noise.
- After `events.mutate(x=1)` you get back a plain ibis `Table`, by design.

**Error messages.** A bad CSV produces one `ValidationError` listing every issue, each with a count and samples:

```
ValidationError: OrderEvents.parse: 4 issues for OrderEvents
  - status: constraint isin([...]) failed; 1 row; e.g. ['refunded']
  - amount: cannot convert string to float64; 1 row; e.g. ['12,50']
  - amount: constraint ge(0) failed; 1 row; e.g. ['-19.99']
  - ordered_at: NULL in a non-nullable column (declare `Column[T | None]` to allow it); 1 row
```

Other failures behave as follows:

| Failure | Result |
|---|---|
| Wrong frame passed to a step with `@step` | `ValidationError`, "step customer_value(), argument 'facts': wrong frame; expected DataFrame[OrderFacts]; got DataFrame[Orders]" |
| Wrong frame passed to a step without `@step` | `AttributeError: Orders has no column 'country'` |
| Typo through `.c` | "Did you mean" |
| `events.amount` (bypassing `.c`) | works at runtime; it is only a static error |
| `conform` on data with NULLs | **passes silently.** `conform` is structural only; `parse` catches them. |
| Join on the wrong key of the same type | **no error anywhere**, the same as plain ibis |
| A handle from another frame inside a window | raw ibis `IbisInputError` |

For comparison, pandera on the same bad CSV (`out/plain_errors.txt`):
- `"12,50"` becomes a `CHECK_ERROR` plus a dtype error.
- Each failure has one sample and no count.
- Coercion is ignored. Coercing by hand turns the bad value into an unexplained NULL.

## Is static safety worth it?

### More cumbersome than plain ibis

- **Class count.** 11 schema classes against 3 pandera models (52 lines of contract code against 23). Six of the 11 only name a derived shape: the delta plus the combined class for each `extend`.
- **Step bodies.** 51 lines against 34, about 50% longer.
  - `OrderFacts.build` restates 8 columns.
  - `aggregate(by=...)` restates its keys.
- **`.c` everywhere.** Five of the 8 steps alias it.
- **Two column spellings.** `MonthlyRevenue.country` (a class ref) after `build`, and `df.c.x` everywhere else. E14's typed refs would make the class ref sound.
- **Typed land ends at most ibis operations.** Only filter, order_by, limit, head, distinct and cache keep the schema. The raw-ibis step is fully untyped, and re-entering needs `conform`. `conform` is structural only; data guarantees need `@step(validate=True)` or `parse`.
- **Generic steps need explicit column handles.**
- **Some steps run queries while the pipeline is being built:** `assume_not_null()` and `@step(validate=True)`.

### Better

**Static checks.** All four checkers catch these 7 planted bugs at the exact line:
- a nullable value into a non-null column;
- the wrong frame passed to a step;
- a column-name typo;
- a forgotten `conform`;
- an `int == str` join key;
- a float where a count belongs;
- a column read without `.c`.

The 8th, a `datetime` passed into a `date` column, is caught at construction.

**Validation.**
- All issues are reported together, including coercion failures.
- Output structure is checked at construction, with no query.
- `unique=True` is enforced (pandera's ibis backend ignores it).
- No `timestamp(6)` workaround is needed.

### How typed is the pipeline? (`tools/typed_coverage.py`)

| | e2e (tacit) | e2e_plain (ibis + pandera) |
|---|---|---|
| pyright strict: Unknown diagnostics | 2 | 4 |
| Schema-typed data expressions | **87%** | 0% |
| Deferred `_` | 6% | 38% |
| Unknown or Any | 4% | 6% |
| Typed only as an ibis table | 2% | 56% |
| mypy precise expressions | 94% | 38% |

**Where typing is lost:**
- the raw `group_by`/`agg`/`mutate` step;
- `ibis.duckdb.connect()`, which is `Any`;
- `.execute()`.

So the pipeline is **not fully typed**. It is typed everywhere except deliberate raw-ibis islands, and each island is fenced by `conform`.

## Size and overhead

| | Total | Contracts | Steps | Runner |
|---|---|---|---|---|
| e2e.py (code lines) | 131 | 52 | 51 | 17 |
| e2e_plain.py (code lines) | 86 | 23 | 34 | 20 |

Benchmark (minimum seconds, with the number of duckdb queries; 2-core machine):

| Variant | 1.4k events | 1.2M events | Queries |
|---|---|---|---|
| tacit | 0.80 s | 2.97 s | 13 |
| ibis + pandera | 7.60 s | 18.1 s | 30 |
| ibis + pandera, cached inputs | 1.01 s | 4.35 s | 34 |
| ibis only, no validation | 0.79 s | 2.27 s | 4 |

**Expression building:** 15.5 ms for tacit against 8.9 ms for plain ibis.

**Import time:** `import tacit_t3` takes 1.20 s, against 1.16 s for `import ibis`.

## Defects found

**Upstream:** ibis 12 with sqlglot 30.23 renders `DROP TABLE IF EXISTS` without a table name. This breaks `create_table(overwrite=True)` and the cleanup of `.cache()`.

**In the prototype** (all fixed during the experiment):
- the `assume_not_null` marker crossed relations;
- the `assume_not_null` check ran twice;
- pandera's Project output was unwrapped incorrectly;
- the "Did you mean" hint was printed twice.
