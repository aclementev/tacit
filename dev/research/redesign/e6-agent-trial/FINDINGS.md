# E6: Agent usability trial (current API, docs only)

> The E6 subagent (Sonnet) returned this report as text, and the main session saved it here. The agent read only the README and `docs/`, never `src/tacit/`, though it called `dir()` on exceptions to find `.failure_cases`.
> Artifacts in this folder:
> - `pipeline.py`: the final version, which runs end to end.
> - `customers.csv` (20 rows) and `orders.csv` (60 rows).
> - `LOG.md`: the timestamped log.
> - `bugs/*.py`: 12 variants, each with one injected bug.
> - `bad/*.csv`: 10 CSV files with bad data.
> - `alt/docs_style.py`: the same logic written the way the docs show.
>
> Versions: tacit 0.2.0, ibis 12.0.0, pandera 0.34.1, pyright 1.1.414, mypy 2.4.0, ty 0.0.89 (plus pyrefly).

**Headline: the runtime half works well. The static half mostly doesn't deliver what the README and index.md promise.**

## 1. Bug matrix

In the table, `mypy` is the default config, where only `import-untyped` errors appear and nothing else is checked. `mypy+` is mypy run with `--follow-untyped-imports`.

| Bug | pyright | mypy | mypy+ | ty | runtime |
|---|---|---|---|---|---|
| (a) column typo, 4 forms: `_.discont`, `orders.statu`, `joined.ordr_id`, join key `"custmer_id"` | silent | not checked | silent | silent | caught at call time as a raw ibis error (`'Table' object has no attribute 'statu'. Did you mean: 'status'?`), not a tacit error |
| (b) customers frame passed to an orders step (also swapped args, and raw orders passed to the aggregate step) | caught, 3 lines of invariance jargon | not checked | **silent** (ibis is `Any`) | caught, best message: `Expected DataFrame[RawOrder], found DataFrame[RawCustomer]` | caught: `StructuralError ... schema RawOrder on parameter 'orders': missing columns [...]; extra columns [...]` |
| (c) forgot `net_amount` | silent with `returns=`; the README form errors identically on correct code, so it's noise | not checked | silent | silent | caught: `StructuralError ... Order on return value: missing columns ['net_amount']`; the message doesn't name the function |
| (d) `order_count` is float instead of int | silent | not checked | silent | silent | caught: `column 'order_count' expected int64, got float64` |
| (e) a CSV row violates a constraint | n/a | n/a | n/a | n/a | caught by `parse()` (`ConstraintError ... failed check greater_than_or_equal_to(0)`), but **the message omits the failing values and rows** |

pyrefly behaves like pyright on (b) and is silent on the rest.

The index.md claim "Forget to add a column after a .mutate()? Your editor underlines it immediately" did not hold in any configuration.

## 2. Type-checker errors on correct code

| Checker | final `pipeline.py` (written defensively) | docs-style form (`alt/docs_style.py`) |
|---|---|---|
| pyright | 0 | **7 errors** |
| mypy | 4 `import-untyped`; nothing else is checked | same 4 |
| mypy+ | 0 | 0 |
| ty | 0 | 0 |
| pyrefly | 0 | 0 |

The final `pipeline.py` gets zero errors through two workarounds:
- `@contract(returns=X)` with `-> ir.Table` as the declared return type.
- ibis deferred `_` for every column expression, which gives up column typing entirely.

The 7 pyright errors on the docs-style form:
- 2× `Table` not assignable to `DataFrame[X]`.
- `Operator "-" not supported for "Column" and "Column"`.
- `fill_null(0)`: `Literal[0]` is not assignable to `Scalar`.
- `.truncate`, `.sum` and `.mean` unknown on `Column`.

The README's own Iris example also fails pyright, with 4 errors.

## 3. Top 10 friction points, with fixes

1. **No static column-name safety.** `df.col` is typed as `Column`, so typos and renames pass every checker. Fix: typed column access per schema, or document that these errors are runtime-only.
2. **Correct ibis code fails pyright, and no workaround is documented.** The only clean option is `_`, which gives up item 1. Fix: typed column stubs, or a "Type checking" docs page. Run the examples through pyright in CI.
3. **The README and getting-started show the form pyright rejects.** Fix: show `returns=` first everywhere, or make the decorator accept `ir.Table` returns.
4. **mypy gets nothing from tacit.** There is no `py.typed`, the needed flag isn't discoverable, and even with it, bug (b) is missed. Fix: ship `py.typed` and state the support level honestly.
5. **No pattern for generic steps.**
   - `@contract` with a TypeVar parameter raises a misleading "found no DataFrame[S] annotations to enforce".
   - What worked: `latest_per_key(df: DataFrame[S], schema: type[S], key: str, ts: str) -> DataFrame[S]`, ending with `schema.cast(...)`. But the schema is passed twice, and `key` and `ts` are untyped strings.
   - Fix: support TypeVars in `@contract`, and add typed column-handle arguments.
6. **Constraint errors hide the failing values.** The docs promise the failing values, but `str(e)` has only the column and the check. `e.failure_cases` has an odd layout and is `None` for `CoercionError`. Fix: include the count, the first N values and the rows in the message.
7. **`float | None` / `Optional[float]` is silently ignored.** The class defines fine, then `parse()` rejects nulls. Fix: honour Optional, or raise at class creation.
8. **Date, timestamp and decimal types are undocumented.** They work, including coercion from strings. Fix: complete the type table.
9. **Contract errors don't name the step.** They say `parameter 'orders'`, not `clean_orders()`, and the useful last line is buried under wrapper frames and a chained exception. Fix: include `__qualname__`, and raise with `from None`.
10. **Small doc inconsistencies:**
    - constraints.md says `SchemaError`; the actual class is `ConstraintError`.
    - schemas.md shows `ValueError: Extra columns`; dataframes.md says `StructuralError`.
    - A `CoercionError` lists columns that converted fine.
    - There's no example with a join or a group-by.

## 4. What worked well

- Runtime contracts are the strongest part, and the structural messages are excellent.
- `parse()` coerced all-varchar CSV columns to int, float, timestamp and date.
- Schema inheritance, `Nullable()` and stacked `Check`s were easy to use.
- Steps 1–3 ran on the first try.
- `latest_per_key` returns the correct result.

## Caveats

- The fixtures are small and generated, so this trial says nothing about performance.
- It covers one pipeline shape.
