# E9 — Agent usability trial on tacit-next (ride-hailing domain)

> The E9 subagent (Sonnet) returned this report as text, and the main session saved it here. The main session also re-ran the checks: the pipeline runs, all four checkers report 0 diagnostics on `pipeline.py`, and bug (f) is caught by all four.

**Setup:**
- The agent read only `e8-prototype/GUIDE.md`. It read the library source 0 times.
- It used two workarounds:
  - It called `dir()` at runtime on the IntervalColumn returned by `datetime - datetime`.
  - It guessed `Column.epoch_seconds()`.
- Files in this folder:
  - `pipeline.py`
  - `drivers.csv` (24 rows) and `trips.csv` (60 rows)
  - `log.txt`
  - `bugs/{a..f}_*.py` and `bugs/trips_bad.csv`
  - extra probes: `bugs/x_*.py`

**Result:**
- The pipeline runs end to end.
- `parse` returns typed timestamps and dates.
- The aggregation produces 12 city × vehicle_type rows.
- All four checkers report 0 diagnostics on the correct code, including the two steps decorated with `@tc.step`.

## Bug matrix

| Bug | pyright | mypy | ty | pyrefly | runtime |
|---|---|---|---|---|---|
| (a) typo `done.tipp` | caught | caught ("maybe "tip"?") | caught | caught | AttributeError with "Did you mean: 'tip'?" (not a ValidationError) |
| (b) drivers frame passed to the trips step | caught | caught | caught | caught | with `@tc.step`: `ValidationError` "step completed_trips(), argument 't': wrong frame; expected Trips; got Drivers"; without it: a raw AttributeError deep in the step |
| (c) forgot `total` | caught ("Argument missing for parameter "total"") | caught | caught | caught | `ValidationError` "Derived(...): total: missing column" |
| (d) `trip_count` is a float | caught (`Scalar[float]` is not assignable to `Column[int] \| Scalar[int] \| int`) | caught | caught | caught | `ValidationError`, dtype int64 vs float64 |
| (e) CSV row violates a constraint | n/a | n/a | n/a | n/a | `ValidationError`: 5 issues in one report, each with a count and samples; the duplicate `trip_id` is flagged too |
| (f) nullable `tip` used where non-null is required | caught | caught | caught | caught | **not caught**: rows with a null tip silently get NaN totals |

**Diagnostics on correct code:** 0 on pyright, mypy, ty and pyrefly.

## Top 10 friction points (most severe first)

1. **Timestamp arithmetic is missing from the facade and the guide.**
   - `datetime - datetime` is a static error in all four checkers.
   - At runtime it returns an IntervalColumn with no `total_seconds`.
   - The agent had to guess `epoch_seconds()`.
2. **Nullability cannot be narrowed after a filter.**
   - After `filter(status == "completed")`, `completed_at` is still `Column[datetime | None]`.
   - So `duration_min` has to be declared nullable.
   - The guide offers no "assume not null" tool.
3. **Reductions over nullable columns are typed unsoundly.**
   - `rating.mean()` is typed `Scalar[float]`.
   - A group where every value is null produces NaN, and neither the types nor the runtime catch it.
4. **Generic-step handles are not tied to the frame.**
   - `top_n_per_group(trips, drivers.city, trips.fare)` type-checks.
   - At runtime it fails with a raw ibis `IbisInputError` that names neither the step nor the parameter.
5. **The guide wrongly says "every failure raises tc.ValidationError".** Typos, wrong frames passed without `@tc.step`, and bad windows raise other exceptions.
6. **Bug (f) is silent at runtime.** Derived columns are never checked for nullability.
7. **The generic step has doc gaps.**
   - It is not stated that `row_number()` is 0-based.
   - There is no top-n example.
   - There is no way to type "a column of F chosen by the caller", so `Column[Any]` loses typing.
8. **`aggregate(by=...)` makes you restate each key as an output column**, and the guide does not say whether leaving one out is an error.
9. **The `extend` pattern needs three classes** to add two columns: the delta frame, the combined frame, and the function.
10. **No foreign-key or relationship validation.** Inner joins silently drop orphan rows.

## What worked well

- **Static checks.** Five of the six bugs were caught, all on the exact line, and all four checkers agreed.
- **No false positives on idiomatic code.** This held across `@tc.step`, PEP 695 generics, `extend` with multiple inheritance, and `tc.join` views.
- **Constructors as typed projections** were the best feature.
- **`parse` reporting.** It reports every violation in one query, with counts and samples.
- **`@tc.step` error messages** name the step and the argument.
- **The guide's examples** all worked as written.

**Confidence that the type checker had its back: 7/10.**
- For structure, names, types and wrong frames: 9/10.
- Points were lost for nullable narrowing and aggregates, untyped handles, and missing duration arithmetic.

## Design responses (main session)

| Friction | Response proposed in the report |
|---|---|
| 1 duration math | Add `Column[datetime] - Column[datetime] -> Column[timedelta]` with `.total_seconds()` / `.total_minutes()` to the facade |
| 2 narrowing after a filter | `col.assume_not_null() -> Column[T]`. It is recorded on the frame and checked when the output is constructed (cheap null count in `validate`), so it is a checked assertion, not a cast |
| 3 nullable aggregates | Reductions over `Column[T \| None]` return `Scalar[T \| None]` (sound). `fill_null` or `assume_not_null` narrows them back |
| 4 / 6 handle and nullability runtime gaps | Wrap ibis relation errors in `ValidationError` naming the step and parameter. Under `validate=True`, check non-null fields on constructed outputs |
| 5 guide inaccuracy | Fixed in `e8-prototype/GUIDE.md` |
| 8 / 9 verbosity | Accept for 1.0. Consider `by=` keys implying outputs, and inline delta declarations once PEP 764 (inline TypedDict) or PEP 827 lands |
