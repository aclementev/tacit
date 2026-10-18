# E0 — Code review of the current implementation (tacit 0.2.0)

Reproduce: `uv run python e0-code-review/probes.py` from `dev/research/redesign/`.

## Runtime bugs / sharp edges (verified by `probes.py`)

| # | Finding | Severity | Evidence |
|---|---------|----------|----------|
| 1 | `cast()` rejects tables whose columns are `NOT NULL` (`!float64` vs `float64`). Any warehouse table with NOT NULL constraints fails the "free" structural check, while `parse()` on the same table passes. Nullability is part of the ibis dtype, and tacit compares dtypes with `!=`. | High | `StructuralError: ... x expected float64, got !float64` |
| 2 | `x: float \| None` / `Optional[float]` is silently accepted as **non-nullable** (ibis drops the Optional, pandera gets `nullable=False`). The most idiomatic Python spelling of "nullable" means the opposite of what users intend. | High | `(float64, nullable=False)` |
| 3 | `@contract` resolves annotations with `get_type_hints` **at decoration time** → `NameError` if schemas are imported under `if TYPE_CHECKING:` (common in large codebases to avoid import cycles) or defined later in the module. | Medium | `NameError: name 'Late' is not defined` |
| 4 | `@contract` silently ignores `DataFrame[S] \| None`, `tuple[DataFrame[A], DataFrame[B]]`, `list[...]`, `dict[...]`. A wrong table passed to an `Optional[DataFrame[A]]` param flows through unchecked. Silent non-enforcement is worse than an error. | High | wrong table returned unchanged |
| 5 | Generic steps are impossible: `def f[S: Schema](df: DataFrame[S]) -> DataFrame[S]` with `@contract` raises `TypeError: found no DataFrame[S] annotations`. Without the decorator, nothing checks at runtime. | Medium | TypeError |
| 6 | Schema classes expose no column references: `Iris.sepal_length` → `AttributeError`. DESIGN.md promises "`Schema.column_name` (returning the column name as a string)"; it isn't implemented. Users fall back to string literals (`group_by("l_returnflag")`) that no tool checks. | Medium | AttributeError |
| 7 | Constraint error messages say *which* check failed but not *how many* rows or *which values*: `column 'x' failed check greater_than_or_equal_to(0).` (data is on `exc.failure_cases`, not in the message). For humans and agents the message is the main debugging surface. | Medium | message text |
| 8 | `validate=True` on chained contracts validates the same data twice (step N's output parse + step N+1's input parse), and each `parse()` re-executes the full upstream lazy expression per check query (no materialization/caching). On Spark/BigQuery this multiplies cost. | Medium | code reading; see E4 for numbers |
| 9 | The README/docs headline pattern `@tacit.contract def f(...) -> DataFrame[X]: return df.mutate(...)` is a **static type error** (the body returns `ir.Table`). The flagship example contradicts the flagship value prop; `returns=` exists but is documented as the alternative. See E1. | High (trust) | code reading; E1 |
| 10 | Strict mode is the only mode, though docs say "you can opt into loose mode". A child-schema frame cannot be passed to a parent-schema contract at runtime (`extra columns ['z']`) nor statically (invariance). Reuse requires an explicit `select`. | Medium (design) | StructuralError |

## Implementation-quality notes (code reading)

- `contract.wrapper` calls `inspect.signature(fn)` on **every call**; it should be computed once at decoration time (E4 measures the cost).
- `Schema.cast()` duplicates `_check_columns()` logic inline instead of calling it.
- Field metadata is three parallel dicts (`_fields`, `_field_checks`, `_field_nullable`); a single `Field` record (name, dtype, nullable, checks, description, …) would be easier to extend (descriptions, units, PII tags, defaults, aliases).
- Python-type → ibis-dtype mapping is whatever `ibis.schema()` accepts. `int` means `int64`, and there is no first-class way to say `int32`, `decimal(12,2)`, `timestamp('UTC')`, `array<string>`, or `struct`. DESIGN.md says "re-export ibis types", but nothing is re-exported, and an annotation such as `dt.Int32` is not a valid type expression for checkers.
- `_from_table` uses `object.__setattr__` to store the schema type on a `__slots__` subclass of `ir.Table`. The schema type is never read back at runtime: no `df.schema_type`, no repr showing the contract.
- `parse()` mixes three responsibilities (structure check, coercion, pandera validation) plus heuristic error classification (`looks_like_coercion_failure`), which is regex-matching on backend error strings and is fragile across backends.
- Error types are good (phase, schema, column, check, failure_cases). That's a solid base worth keeping. But `ValidationError` carries a single `column`/`check`, while real failures are usually *many* (pandera `SchemaErrors`, lazy mode). The API should be a list of issues (a pydantic-like `errors()`).
- Test suite: runtime tests are decent. The typechecking suite runs pyright only, with `reportOperatorIssue = false`, which hides the main in-body typing gap.
