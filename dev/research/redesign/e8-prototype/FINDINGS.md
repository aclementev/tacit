# E8 — tacit-next: the consolidated prototype

> The E8 subagent (Opus) returned this report as text, and the main session saved it here.
> The main session also re-ran the spot checks: 35/35 runtime tests pass, the ported examples report 0 diagnostics on all four checkers, the e-commerce pipeline runs, and the bug matrix was reproduced.
> Environment: stock ibis 12.0.0, pyright 1.1.414, mypy 2.4.0 (`follow_untyped_imports`), ty 0.0.89, pyrefly 1.4.0.

**Headline:**
- **Type checks:** of 185 expected-result cases, the checkers score 185/185 (pyright), 182 (mypy), 180 (ty) and 182 (pyrefly). Every miss and wrong type traces to ibis annotations, or is cosmetic in ty.
- **Ported examples:** the three examples type-check with 0 diagnostics on all four checkers and produce the same results as tacit 0.2.
- **E6 bugs:** every static bug class from E6 is now caught by all four checkers.
- **Runtime:** 35/35 tests pass on duckdb.

## 1. Design as built

```python
import tacit_next as tc
from tacit_next import Column

class RawOrder(tc.Frame):                       # wrapper over an ibis Table, not a subclass
    order_id: Column[int]
    order_ts: Column[datetime]
    status: Column[str] = tc.field(isin=["pending", "shipped", "cancelled"])
    amount: Column[float] = tc.field(ge=0, description="gross")
    discount: Column[float | None] = tc.field(ge=0)          # nullable = `| None`
    price: Column[Decimal] = tc.field(dtype="decimal(12, 2)") # physical dtype override

class NetAmount(tc.Frame): net_amount: Column[float]          # delta: only the new columns
class Order(RawOrder, NetAmount): pass

def clean_orders(orders: RawOrder) -> Order:
    kept = orders.filter(orders.status != "cancelled")       # -> RawOrder (Self)
    return Order.extend(kept, NetAmount(net_amount=kept.amount - kept.discount.fill_null(0)))

def country_month_stats(orders: Order, customers: RawCustomer) -> CountryMonthStats:
    j = tc.join(orders, customers, on=lambda o, c: o.customer_id == c.customer_id)
    o, c = j.left, j.right                                    # typed Order / RawCustomer views
    return CountryMonthStats(                                 # reductions => GROUP BY
        country=c.country, order_month=o.order_ts.truncate("M").date(),
        order_count=o.order_id.count(), total_net=o.net_amount.sum(),
        avg_net=o.net_amount.mean(), distinct_customers=o.customer_id.nunique())

def latest_per_key[F: tc.Frame](df: F, key: Column[Any], ts: Column[datetime]) -> F:
    return df.filter(tc.row_number().over(group_by=key, order_by=ts.desc()) == 0)

def add_score[O: Scored](df: tc.Into[O], amount: Column[float], out: type[O]) -> O:
    return out.extend(df, Scored(score=amount * 0.1))       # caller: class ScoredOrders(Orders, Scored)

orders = RawOrder.parse(con.read_csv(...))   # coerce + validate: 1 query (+1 only on failure)
RawOrder.cast(table)                          # structural only; "at least these columns" -> projects
Stats.aggregate(by=[o.status])(status=o.status, n=o.order_id.count(), total=o.amount.sum())
@tc.step(validate=True)                       # optional: runtime frame checks + data checks + step names
```

### `Column[T]`

**Static type.** `Column[T]` is a generated facade (`_column.pyi`).
- It is declared as `class Column(ir.Value, Generic[T_co])` and is covariant.
- It is a descriptor: `__get__` returns `Self`, and `__set__(value: Column[T] | Scalar[T] | T)` types the parameters of the `dataclass_transform` constructor.
- It has about 55 methods plus all operators, with overloads per value family: bool, int, float, Decimal, str, datetime, date and time, each in a non-null and a nullable variant.

**Runtime.**
- Instance access returns the plain ibis column. Nothing is wrapped.
- Class access returns `ibis._["name"]`.

**Hovers** read `Column[float]`, `Column[str | None]`, `Scalar[int]` and `Join[Orders, Customers]`.

**Numeric families are kept apart.**
- `int / int` gives `Column[float]`.
- `count()` gives `Scalar[int]`.
- `Decimal + 1.5` is rejected.
- An `int` widens into a float field, and the constructor applies a lossless cast.

### Frame

**Members.**
- `.ibis` is the escape hatch to the raw ibis Table.
- Schema-preserving methods return `Self`: `filter`, `order_by`, `limit`, `distinct(on=)`, `cache`.
- Output methods: `execute`, `to_pandas`, `to_polars`, `to_pyarrow`.
- Classmethods: `parse`, `cast`, `extend`, `aggregate`.
- Metadata comes from the free functions `tc.fields()` and `tc.schema()`.

**Checks at class creation.**
- A column whose name collides with a member raises, and the error suggests `tc.field(name="filter")`.
- Columns with conflicting types across base classes also raise.

**Field order** is base-first.

### Construction

**`Out(...)`** builds a strict projection.
- Every expression must come from one relation; for more than one, use `tc.join`.
- Literals are broadcast.
- Deferred class refs are resolved.
- If any reduction is present, the column-valued arguments become GROUP BY keys.

**`Out.extend(base, delta, *more)`.**
- `Into[Self]` is contravariant, so the checker requires `Out` to subclass `type(base)` and every delta's class.
- At least one delta is required.
- The result is checked strictly at runtime.

**`tc.join`.**
- Both sides are prefixed internally, so column names cannot collide.
- The output constructor names every column.
- `on=` takes a lambda over the typed views, or `(left_col, right_col)` pairs.

### Validation

There is no pandera. Validation uses the E4 design, in about 200 lines (`_validate.py`).

**On every parse, one `aggregate()` query computes:**
- a `try_cast` failure count per column,
- null counts (NaN counts as null for non-nullable floats),
- one sum per check,
- `count - nunique` for uniqueness.

**On failure only**, one bounded `UNION ALL` query fetches sample rows.

**Checks:** `ge`, `gt`, `le`, `lt`, `between`, `isin`, `notin`, `pattern`, `str_matches`, `length`, `unique`, and `tc.check(fn)`, where `fn` has type `Callable[[Column[Any]], Column[bool]]`.

**Structural comparison.**
- It ignores nullability, so a NOT NULL `!float64` column passes.
- It ignores timestamp precision, so `timestamp(6)` matches `timestamp`.
- Without an explicit dtype, types are compared by family. With `tc.field(dtype=...)`, the comparison is exact.
- Results are memoised.

### Errors

There is one exception type, `tc.ValidationError`. Its `.issues` is a list of `Issue(code, column, expected, actual, count, samples)`.

```
RawOrder.parse: 1 issue for RawOrder
  - amount: constraint ge(0) failed; 1 row; e.g. ['-33.74']
step clean_orders(), argument 'orders': 1 issue for RawOrder
  - wrong frame; expected RawOrder; got RawCustomer
```

## 2. Checker matrix (`tests/typecheck/run_matrix.py` → `out/typecheck/`)

| feature (cases) | pyright | mypy | ty | pyrefly |
|---|---|---|---|---|
| column access + hover; typos on frame/class (9) | 9 | 9 | 9 | 9 |
| wrong method for the type (9) | 9 | 9 | 9 | 9 |
| arithmetic int/float/Decimal/str (16) | 16 | 16 | 16 | 16 |
| comparisons with literals, bool ops (13) | 13 | 13 | 13 | 13 |
| typed methods (str, temporal, round, ifelse, isin, between) (16) | 16 | 16 | 15 (cosmetic) | 16 |
| reductions, cast / try_cast (19) | 19 | 19 | 19 | 19 |
| nullability: `fill_null` solves T / nullable into non-null / propagation (18) | 18 | 18 | 18 | 18 |
| `tc.field()` vs `Annotated` (11) | 11 | 11 | 11 | 11 |
| custom checks (2) | 2 | 2 | 2 | 2 |
| Frame methods return Self; parse/cast; `.ibis` (13) | 13 | 12 (`.ibis` is Any) | 13 | 13 |
| nominal subtyping; raw `ir.Table` rejected (4) | 4 | 3 | 3 | 3 |
| constructor missing/extra/wrong type (7) | 7 | 7 | 7 | 7 |
| implicit GROUP BY + `aggregate(by=)` (7) | 7 | 7 | 7 | 7 |
| extend `Into[Self]`: wrong base, wrong delta, no delta (7) | 7 | 7 | 7 | 7 |
| additive generic step `Into[O]` (4) | 4 | 4 | 4 | 4 |
| generic steps: handles, mixin bounds, `F \| None` (10) | 10 | 10 | 10 | 10 |
| join scope (8) | 8 | 8 | 8 | 8 |
| `@step` keeps signatures (5) | 5 | 5 | 5 | 5 |
| interop: `as_ibis`, `as_column`, `cases`, `lit` (7) | 7 + 3 FP | 6 | 4 + 3 FP | 5 + 1 FP |
| **TOTAL (185)** | **185 (3 FP)** | **182** | **180 (3 FP)** | **182 (1 FP)** |

## 3. E6 bug matrix, before and after (`examples/ecommerce/inject_bugs.py` → `out/bugs/`)

| bug | E6 static P/M+/T/R | E6 runtime | tacit-next static P/M/T/R | tacit-next runtime |
|---|---|---|---|---|
| (a) column typo: attribute, filter, after join, join key | silent in all four | raw ibis AttributeError | **caught by all four** (4 variants) | AttributeError with "Did you mean" |
| (b) wrong frame / swapped args | P, T, R; mypy silent | StructuralError | **caught by all four** (3 variants) | AttributeError, or `wrong_frame` naming the step with `@step` |
| (c) forgot `net_amount` | silent in all four | caught | **caught by all four** | caught |
| (d) `order_count` float via cast / `*1.0` | silent in all four | caught | **caught by all four** (3 variants) | dtype issue |
| (d3) schema declares `order_count: Column[float]` | silent | caught | silent (int→float widening, by design) | widened |
| (e) 10 bad CSVs | n/a | caught, no values in the message | n/a | **10/10 caught**, with count and samples |
| bonus: forgot `fill_null` (nullable into a non-null field) | n/a | n/a | **caught by all four** | n/a |

## 4. Remaining false positives on correct code

The examples themselves have 0 false positives on all four checkers.

1. **`orders.ibis.filter(typed_bool_col)`** fails on P, T and R.
   - Cause: our facade subclasses `ir.Value`, not `ir.BooleanValue` or `ir.Column`. Subclassing `ir.Column` brings back the E2 Unknown base.
   - Workaround: use `Frame.filter`, or `tc.as_ibis(col)`.
2. **`orders.ibis.order_by(col.desc())` / `ibis.desc(col)`** fail on P and T.
   - Cause: the same, plus ibis annotations.
   - Workaround: `Frame.order_by`.
3. **Cosmetic, ty only:** `ifelse` and `cases` reveal `Column[Literal["y","n"]]`, which is still assignable to `Column[str]`.
4. **Methods behind ibis's untyped `@util.backend_sensitive`** are untyped.
   - Workaround: add the method to the facade.
5. **Methods outside the facade** (about 55 are typed today) fall back to `ir.Value` typing.
   - Workaround: `tc.as_ibis(col).method()`, then `tc.as_column(...)`.
6. **Library-internal only:**
   - 23 pyright errors against ibis annotations in tacit_next's runtime code.
   - 497 deliberate `# type: ignore`s in the generated stub (Liskov narrowing against `ir.Value`, overlapping overloads).

**Static misses that remain:**
- A raw `ir.Table` passed where a Frame is expected, or a raw ibis expression passed to a constructor, is missed by mypy, ty and pyrefly. The cause is upstream (E1/E2). The runtime still catches it.
- `str_col == 5` returns `bool`, because `object.__eq__` applies. It is still rejected inside `filter` and constructors.

## 5. What changed from the hypothesis, and why

**The facade's base is `ir.Value`, not `ir.Column`.**
- This keeps a clean MRO on ty and pyrefly.
- The cost is the interop false positives #1 and #2.

**Per-family overloads, not bounded TypeVars.**
- mypy ignores TypeVar bounds on `self`, and ty and pyrefly widen method TypeVars to unions.
- So the facade is generated: `tools/gen_facade.py` (425 lines) produces a 1,073-line `.pyi`.

**Nullability rules.**
- Reductions drop `None`.
- Comparisons always give `Column[bool]`.
- Arithmetic, string, temporal, `cast` and `try_cast` propagate nullability exactly. `try_cast` returns `T | None`.

**Constraints.**
- Both `tc.field(...)` and `Annotated` work everywhere.
- `tc.field(...)` is recommended: it also carries the description, physical name and dtype.

**`extend` requires a delta.**
- This made E6 bug (c2) a static error.

**`cast("float64")` is typed** through literal-dtype overloads. This caught (d1) statically.

**The escape hatch is `.ibis`, not `.t`**, because `t` is a plausible column name.

**`@step` keeps a registry of Frame classes.**
- Names imported under `if TYPE_CHECKING:` never exist at runtime, so lazy resolution alone is not enough.

**Aggregation: recommend `Out.aggregate(by=[...])(...)`.**
- Statically it is identical to the implicit form, but it adds a runtime grain check.
- In the implicit form, forgetting `.sum()` silently turns that column into a GROUP BY key.
- With `by=`, the same mistake raises `not_a_reduction`.

**`@step` is opt-in.** Structure is already guaranteed by construction. `@step` is still useful for:
- `validate=True`,
- step names in errors,
- untyped callers and raw tables.

It enforces TypeVar bounds, `F | None`, `tuple` and `list`, and raises on annotations it cannot enforce instead of skipping them.

**Validation uses the native validator from E4, not pandera.**

## 6. Open problems

1. **Class-level refs are unsound.** `Orders.amount` is `Column[float]` statically but a `Deferred` at runtime. Fix: give them a distinct `Ref[T]` type, or drop class access.
2. **Outer-join nullability is not tracked.** It would need nullable views, e.g. `tc.left_join`.
3. **Joins are basic:**
   - no join-of-join scope;
   - join views cannot be used as an `extend` base;
   - a cross-frame handle used in a body gets ibis's own error.
4. **`bool <: int` and `datetime <: date`.** A `Column[bool]` is accepted as a `Column[int]` statically, and fails only at runtime.
5. **Additive generic steps** still need the caller to name the output class. This is a language limit (E3).
6. **Interop false positives:** fix by upstreaming annotation fixes, or by changing the facade's bases.
7. **Upstream E1/E2 bugs** still keep mypy, ty and pyrefly from rejecting raw tables. Under mypy, `.ibis` is `Any`.
8. **Not done:**
   - lazy guard mode;
   - bounding the memo cache;
   - datetime and decimal check semantics;
   - editor autocomplete, which is unmeasured;
   - Python 3.14's `annotationlib` as a replacement for the registry.

## 7. File index

- **`src/tacit_next/`** (`py.typed`, about 1,300 lines of runtime code):
  - `_column.pyi`: the facade, generated by `tools/gen_facade.py`.
  - `_column.py`: runtime markers and helpers.
  - `_fields.py`
  - `_frame.py`
  - `_join.py`
  - `_step.py`
  - `_validate.py`
  - `_errors.py`
- **Configs:** `pyrightconfig.json`, `mypy.ini`, `pyrefly.toml`, and `chk.sh`, which runs all four checkers on given files.
- **Type-check cases:** `tests/typecheck/t01..t10_*.py` with `run_matrix.py`; output in `out/typecheck/`.
- **Runtime tests:** `tests/test_runtime.py` (35 tests). Run them from `redesign/` with `uv run --frozen pytest e8-prototype/tests/test_runtime.py`.
- **Examples:**
  - `examples/iris_pipeline.py`
  - `examples/tpch_q1.py`
  - `examples/ecommerce/pipeline.py` (run with `PYTHONPATH=e8-prototype/src`)
  - `out/compare_examples.txt`
- **Bug re-injection:** `examples/ecommerce/inject_bugs.py` and `bugs/`; output in `out/bugs/matrix.txt`.
