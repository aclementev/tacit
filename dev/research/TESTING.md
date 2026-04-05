# Testing Strategy

This document captures the testing plan for tacit v0 — what we test, how, and
why. The goal is to test **tacit's concerns only**: the glue between ibis and
pandera, the schema-to-type-safety pipeline, and the user-facing error messages.
We explicitly avoid re-testing ibis internals or pandera validation logic.


## Principles

1. **Test our value prop, not our dependencies.** Pandera validates checks
   correctly; ibis compiles expressions correctly. We test that our orchestration
   of these tools produces the right behavior at the seams.
2. **Static type safety is a first-class testable property.** The "can't forget
   parse/cast" guarantee is enforced by pyright, not runtime code. We test it
   with pyright, not pytest.
3. **Error messages are API surface.** When a pipeline fails at 3am, the error
   message is the product. We assert on message content, not just exception type.
4. **Examples are tests.** The iris and TPC-H examples are integration tests and
   living documentation. If they break, a test catches it.
5. **No unnecessary abstraction.** Tests should be straightforward pytest. No
   custom test framework, no complex fixtures, no over-parameterization.


## Test structure

```
tests/
├── conftest.py                # Shared fixtures (DuckDB connection, sample data)
├── test_schema.py             # Schema class mechanics
├── test_parse.py              # parse() and cast() behavior
├── test_dataframe.py          # DataFrame[S] identity and ibis transparency
├── test_contract.py           # @tacit.contract decorator (when implemented)
├── test_examples.py           # Examples as integration tests
└── typechecking/              # Static type safety (pyright, not pytest)
    ├── pyproject.toml         # pyright config
    ├── check_safety.py        # "can't forget parse/cast" contract enforcement
    ├── check_transparent.py   # DataFrame[S] usable where ibis.Table expected
    └── check_invariance.py    # DataFrame[Iris] ≠ DataFrame[IrisFeatures]
```


## Layer 1: Schema mechanics (`test_schema.py`)

Unit tests for the `Schema` base class. No engine, no data, pure Python.

**What we test:**

- `_get_fields()` returns correct `{name: type}` mapping from annotations
- Inheritance composes fields: `IrisFeatures._get_fields()` includes both
  parent `Iris` fields and child `IrisFeatures` fields, in order
- `_ibis_schema()` maps Python builtins to ibis types correctly
  (`float → float64`, `int → int64`, `str → string`, `bool → boolean`)
- `_pandera_schema()` produces a `DataFrameSchema` with matching columns
  and `strict=True`

**What we don't test:**

- That ibis `Schema` objects work correctly (ibis's job)
- That pandera `DataFrameSchema` validates correctly (pandera's job)

**Example test shape:**

```python
class Iris(Schema):
    sepal_length: float
    species: str

class IrisFeatures(Iris):
    sepal_ratio: float

def test_get_fields_basic():
    assert Iris._get_fields() == {"sepal_length": float, "species": str}

def test_get_fields_inheritance():
    fields = IrisFeatures._get_fields()
    assert "sepal_length" in fields  # from parent
    assert "sepal_ratio" in fields   # from child

def test_ibis_schema_types():
    schema = Iris._ibis_schema()
    assert schema["sepal_length"] == dt.float64
    assert schema["species"] == dt.string
```


## Layer 2: parse() and cast() (`test_parse.py`)

Integration tests for the boundary operations. Requires DuckDB + small
synthetic data via `ibis.memtable()`.

**What we test:**

- `parse()` on valid data returns `DataFrame[S]` with correct type and metadata
- `parse()` coerces compatible types (e.g., `int64` column → `float64` when
  schema says `float`)
- `parse()` rejects missing columns → error names the missing columns
- `parse()` rejects extra columns (strict mode) → error names the extras
- `parse()` rejects wrong types that can't be coerced → error names column
  and types (expected vs actual)
- `parse()` rejects constraint violations (once constraint syntax is finalized)
  → error identifies which check failed
- `cast()` accepts structurally matching tables, returns `DataFrame[S]`
- `cast()` rejects missing columns → same error format as parse
- `cast()` rejects extra columns → same error format as parse
- `cast()` rejects type mismatches → same error format as parse
- `cast()` does NOT execute queries (structural/metadata check only)

**What we don't test:**

- That pandera's check logic is correct (e.g., `Check.ge(0)` works)
- That ibis `.cast()` coerces types correctly at the engine level
- Multiple backend engines — DuckDB only for v0

**Error message testing pattern:**

```python
def test_parse_missing_columns():
    table = ibis.memtable({"species": ["setosa"]})
    with pytest.raises(ValueError, match="sepal_length"):
        Iris.parse(table)

def test_cast_extra_columns():
    table = ibis.memtable({
        "sepal_length": [5.1], "species": ["setosa"], "EXTRA": [1]
    })
    with pytest.raises(ValueError, match="EXTRA"):
        Iris.cast(table)

def test_cast_wrong_type():
    table = ibis.memtable({
        "sepal_length": ["not_a_float"], "species": ["setosa"]
    })
    with pytest.raises(TypeError, match="sepal_length.*float64.*string"):
        Iris.cast(table)
```


## Layer 3: DataFrame identity (`test_dataframe.py`)

Tests that `DataFrame[S]` behaves correctly as an ibis Table subclass.

**What we test:**

- `isinstance(df, ir.Table)` is `True`
- `isinstance(df, DataFrame)` is `True`
- ibis operations (`.mutate()`, `.filter()`, `.select()`, `.group_by()`)
  return plain `ibis.Table`, NOT `DataFrame` — this is correct by design
- `df._tacit_schema` is set to the schema class after parse/cast
- Column access (`df.sepal_length`) returns an ibis column expression
- `df.columns` matches the schema's field names

**What we don't test:**

- That ibis operations produce correct SQL/results (ibis's job)
- That ibis subclassing internals work (verified in feasibility spike)


## Layer 4: @tacit.contract decorator (`test_contract.py`)

*Deferred until the decorator is implemented.* Placeholder for:

- Decorator calls `cast()` on inputs/outputs by default
- With `validate=True`, calls `parse()` instead
- Works with multiple `DataFrame[S]` parameters
- Raises clear error on contract violation
- Non-DataFrame parameters are passed through unchanged


## Layer 5: Static type safety (`typechecking/`)

**This is the critical differentiator.** Tacit's core value prop is that
the type checker prevents you from forgetting `parse()`/`cast()`. This must
be tested mechanically, not just claimed.

### Approach: the pydantic pattern

We use pyright's `reportUnnecessaryTypeIgnoreComment` to test both positive
and negative type-checking cases in the same file. This requires zero custom
test infrastructure.

**How it works:**

1. Write `.py` files with type annotations exercising tacit's API
2. Lines that should type-check clean: just write normal code
3. Lines that SHOULD produce type errors: add `# pyright: ignore[reportXxx]`
4. Enable `reportUnnecessaryTypeIgnoreComment = true` in pyright config

If a "should error" line stops producing an error (e.g., we accidentally
made the types too loose), pyright flags the ignore comment as unnecessary
→ CI fails. If a "should pass" line starts erroring, pyright reports it →
CI fails.

**Verified working** with pyright 1.1.408 against tacit's actual DataFrame
subclass. See the proof-of-concept commands in the research logbook.

### pyright configuration

```toml
# tests/typechecking/pyproject.toml
[tool.pyright]
pythonVersion = "3.13"
reportUnnecessaryTypeIgnoreComment = true
reportOperatorIssue = false  # ibis type stub false positives
```

The `reportOperatorIssue = false` suppresses known false positives in ibis's
type annotations (e.g., `Column / float` not recognized). See
[ibis_type_stub_issues.md](ibis_type_stub_issues.md) for details.

### Test files

**`check_safety.py`** — the "can't forget parse/cast" property:

```python
# --- Positive: these should type-check clean ---

def correct_parse(raw: ir.Table) -> DataFrame[Iris]:
    return Iris.parse(raw)                                # goes through parse

def correct_cast(df: DataFrame[Iris]) -> DataFrame[IrisFeatures]:
    result = df.mutate(...)
    return IrisFeatures.cast(result)                      # goes through cast

# --- Negative: these SHOULD produce type errors ---

def forgot_parse(raw: ir.Table) -> DataFrame[Iris]:
    return raw  # pyright: ignore[reportReturnType]       # Table ≠ DataFrame[Iris]

def forgot_cast(df: DataFrame[Iris]) -> DataFrame[IrisFeatures]:
    return df.mutate(...)  # pyright: ignore[reportReturnType]  # Table ≠ DataFrame[S]
```

**`check_invariance.py`** — schema type parameter is invariant:

```python
def wrong_schema(df: DataFrame[Iris]) -> DataFrame[IrisFeatures]:
    return df  # pyright: ignore[reportReturnType]        # Iris ≠ IrisFeatures

def wrong_direction(df: DataFrame[IrisFeatures]) -> DataFrame[Iris]:
    return df  # pyright: ignore[reportReturnType]        # IrisFeatures ≠ Iris
```

**`check_transparent.py`** — DataFrame[S] is usable as ibis.Table:

```python
def takes_ibis_table(t: ir.Table) -> ir.Table:
    return t

def transparent_usage(df: DataFrame[Iris]) -> None:
    takes_ibis_table(df)       # should pass — DataFrame IS an ibis.Table
    _ = df.mutate(x=1)         # ibis operations work
    _ = df.filter(df.species == "setosa")
    _ = df.select("sepal_length", "species")
```

### Running type checks

```bash
# In CI or locally:
cd tests/typechecking && pyright

# Expected: 0 errors, 0 warnings
# Any error means either:
#   - A "should pass" line is broken (regression in our types)
#   - A "should error" line stopped erroring (our types got too loose)
```

### Integration with pytest

Type checking runs as a **separate CI step**, not inside pytest. Rationale:
pyright analyzes files statically; mixing it into pytest's runtime test
collection adds complexity for no benefit. CI runs both:

```yaml
# CI pseudo-config
- run: pytest tests/
- run: cd tests/typechecking && pyright
```

Optionally, we can add a single pytest test that shells out to pyright and
asserts exit code 0, so `pytest` alone runs everything:

```python
# tests/test_typecheck.py
import subprocess

def test_pyright_typechecking():
    result = subprocess.run(
        ["pyright", "-p", "tests/typechecking"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
```

### Future alternative: pyright --outputjson

If we later need finer-grained assertions (e.g., "this specific line should
produce `reportReturnType` with a message mentioning `DataFrame[Iris]`"), we
can switch to parsing pyright's JSON output:

```python
def run_pyright(path: str) -> dict:
    result = subprocess.run(
        ["pyright", "--outputjson", path],
        capture_output=True, text=True,
    )
    return json.loads(result.stdout)

def test_forgot_cast_produces_error():
    output = run_pyright("tests/typechecking/check_safety.py")
    errors = [d for d in output["generalDiagnostics"] if d["severity"] == "error"]
    assert any("reportReturnType" in d.get("rule", "") for d in errors)
```

This is more work but gives precise, per-line, per-rule control. The pydantic
pattern is simpler and sufficient for v0.


## Layer 6: Examples as integration tests (`test_examples.py`)

The examples in `examples/` are the target user experience. They should be
runnable and correct — both as documentation and as regression tests.

**Approach:** Make example pipeline functions importable and call them from
pytest with test data.

```python
# tests/test_examples.py
from examples.iris_pipeline import pipeline

def test_iris_pipeline(iris_csv):
    result = pipeline(str(iris_csv))
    assert set(result.columns) == {
        "sepal_length", "sepal_width", "petal_length", "petal_width",
        "species", "sepal_ratio", "petal_ratio", "petal_area",
        "predicted_species",
    }
    executed = result.execute()
    assert len(executed) == 150
    assert set(executed["predicted_species"].unique()) == {"setosa", "versicolor", "virginica"}
```

For this to work, examples need to be importable (no top-level side effects).
The current examples already have this shape — `pipeline()` is a function,
not top-level code.

**Note:** The examples currently use API that doesn't exist yet (`tacit.Schema`,
`tacit.DataFrame`, `@tacit.contract`). Example tests will be written alongside
the implementation. The test plan here defines the target shape.


## Dependencies

Add to `[dependency-groups]` in `pyproject.toml`:

```toml
[dependency-groups]
dev = [
    "ipython>=9.7.0",
    "pytest>=8.4.2",
    "pyright>=1.1.400",
]
```

pyright is already usable via `uv run --with pyright`, but adding it to dev
deps ensures consistent versions and simplifies CI.


## What we explicitly do NOT test

- **ibis expression compilation** — ibis's job. We trust `.mutate()` etc.
- **pandera check logic** — pandera's job. We trust `Check.ge(0)` works.
- **Multiple backends** — DuckDB only for v0. Tacit is backend-agnostic via
  ibis, but testing N backends is ibis's responsibility.
- **mypy compatibility** — pyright only for v0. Add mypy later if users ask.
  The pydantic pattern supports adding mypy trivially (same test files, run
  `mypy` as an additional CI step).
- **Performance** — no benchmarks for v0. The key performance property
  (cast is metadata-only, no query) is tested by asserting it doesn't
  execute queries, not by measuring speed.
- **Hypothesis / property-based testing** — deferred. Pandera's hypothesis
  integration is pandas-only. Would need generate-then-convert via Arrow.


## Running tests

```bash
# All runtime tests:
uv run pytest tests/

# Type checking only:
uv run pyright -p tests/typechecking

# Everything (if using the pytest wrapper):
uv run pytest tests/  # includes test_typecheck.py that shells out to pyright
```
