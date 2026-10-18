# E1 — Baseline type-checker matrix for the current tacit API

> Reported by the E1 subagent as text (subagents may not write report files) and saved here by the main session.
> Scripts, probes and raw outputs are in this folder; raw outputs are under `out/`.

## Versions

- Type checkers: pyright 1.1.414, mypy 2.4.0, ty 0.0.89, pyrefly 1.4.0 (all the latest on PyPI on 2026-10-19).
- Python 3.13.
- ibis 12.0.0, which ships **no `py.typed`**.
- pandera 0.34.1, which ships `py.typed`.
- tacit 0.2.0, which ships **no `py.typed`**.

## Commands

Run these from this folder. Each tool has its own config, so the repo's `[tool.pyright]` section is not picked up.

- `uv run pyright -p pyrightconfig.json <path>` uses the default rules. `pyrightconfig_repo.json` adds the repo's `reportOperatorIssue=false`.
- `uv run mypy --config-file {mypy,mypy_strict,mypy_ignoremissing,mypy_follow,mypy_tacittyped}.ini --show-error-codes <path>`:
  - `follow` sets `follow_untyped_imports`.
  - `tacittyped` puts `src/` on `mypy_path` to simulate tacit shipping `py.typed`, with ibis ignored.
- `uv run ty check --config-file ty.toml --output-format concise <path>`
- `uv run pyrefly check --config pyrefly.toml --output-format min-text <path>`
- Helpers: `run_matrix.py <dir>`, `chk.sh <variant> <file>`, `reveal.sh <file>`, `compare_expected.py`.
- Inputs:
  - `tc/` is a copy of `tests/typechecking`. `tc_raw/` is the same with the 7 `# pyright: ignore` comments stripped.
  - `examples/`.
  - `docs_snippets/`: 23 modules assembled from the code blocks in `docs/` and the README.
  - `probe/`.

## Matrix

| Check | pyright | mypy | ty | pyrefly |
|---|---|---|---|---|
| Existing 7 expected errors caught | 7/7 | 0/7 (all variants) | 3/7 | 3/7 |
| False positives on `tc_raw`, default config | 11 reportOperatorIssue (0 with repo config) | 13 import-untyped (default); 17 more with `--strict` | 0 | 0 |
| tacit and ibis types visible | yes | **no**: import-untyped, everything `Any` | yes | yes |
| `DataFrame[Child]` → `DataFrame[Parent]` rejected | works | fails | works | works |
| `__tacit_type_is_invariant__` hack needed | yes (without it, S is covariant) | moot (Any base) | yes | no (invariant anyway) |
| Legacy `TypeVar` + `Generic[T]` invariant with no hack | yes | no (Any base) | yes | yes |
| Plain `ir.Table` returned as `DataFrame[S]` flagged | works | **fails** | **fails** | **fails** |
| Plain `ir.Table` passed to a `DataFrame[S]` param flagged | works | fails | fails | fails |
| `DataFrame[Iris]` passed to a `DataFrame[IrisFeatures]` param flagged | works | fails | works | works |
| Unrelated type accepted as or from `DataFrame` | no | `DataFrame` → `int` accepted | `DataFrame` → `int`/`str` accepted | `int`/`str` → `DataFrame` accepted |
| `@contract(returns=X)` call site is `DataFrame[X]` | works | `Any` (works only if tacit is typed) | works | works |
| Bare `@contract` keeps the signature | works | same as above | works | works |
| `df.sepal_length` resolves to | `Column` | `Any` | Unknown | Unknown |
| `df["sepal_length"]` resolves to | `Column` | `Any` | `Column` | `Column` |
| Typo `df.sepal_lenght` flagged | **no** | **no** | **no** | **no** |
| `a / b`, `a > 5`, `a * 2.0` on columns | false positive (reportOperatorIssue) | accepted (Any) | accepted (Unknown) | accepted (Unknown) |
| `.sum()`, `.mean()`, `.upper()` on columns | **false positive** (reportAttributeAccessIssue, not silenced by repo config) | accepted | accepted | accepted |

## Examples and docs (error counts)

| Input | pyright default | pyright repo cfg | mypy (imports ignored) | mypy follow | ty | pyrefly |
|---|---|---|---|---|---|---|
| iris_pipeline.py | 7 | 2 | 0 | 0 | 0 | 0 |
| tpch_q1.py | 11 | 7 | 0 | 0 | 0 | 0 |
| README quick example | 4 | 1 | 0 | 0 | 0 | 0 |
| 23 docs snippets | 25 | 6 | 69 (default) / 117 (strict) | 1 | 3 | 2 |

- **Returning a plain ibis expression from a function annotated `-> DataFrame[X]` is a real error, but only pyright reports it.** pyright flags `Type "Table" is not assignable to return type "DataFrame[...]"` at iris:32, iris:41, readme:21, tpch:50 and tpch:58.
- In tpch, `.sum()` and `.mean()` add 5 reportAttributeAccessIssue errors, which remain even with the repo config.
- mypy, ty and pyrefly stay silent because of the blind spots in the next section, not because the code is correct. The typed-clean spelling is `@contract(returns=X)` with `-> ir.Table`.
- **Every shipped example fails pyright.** The "we don't run pyright on examples" rule hides this.

## Root causes

1. **mypy is effectively unsupported.**
   - Neither tacit nor ibis ships `py.typed`, so mypy reports `Skipping analyzing "tacit": module is installed, but missing library stubs or py.typed marker [import-untyped]`. If you ignore that, every tacit symbol becomes `Any`, and 0 of 7 expected errors are caught.
   - `--strict` adds `Class cannot subclass "Schema" (has type "Any")` and `Untyped decorator makes function ... untyped`.
   - Simulating a typed tacit (with ibis still untyped) makes `@contract` and `DataFrame[X]` flow through correctly. But `DataFrame` then has an **`Any` base**, so mypy treats it as a subtype of anything: invariance has no effect, and `DataFrame[Iris]` is accepted as `int`. A control class with the same shape and no `Any` base is correctly invariant.
   - `follow_untyped_imports` does not help, because ibis builds `__all__` through `@public` and `ir.Table` still ends up as `Any`.
2. **ty and pyrefly miss "forgot to cast".**
   - ibis `Table` inherits `FixedTextJupyterMixin`, which `ibis/expr/types/rich.py` defines twice: inside a `try:/except ImportError` around `from rich.jupyter import JupyterMixin`.
   - ty warns `unsupported-base` and pyrefly reports `invalid-inheritance`. Both then treat `Table` as having an unknown base.
   - As a result, `Table` is assignable to any subclass of `Table`, which accounts for the 4 missed expected errors, and `df.col` is Unknown. `probe/p_repro_mixin.py` reproduces this with a local class.
   - pyrefly is the most lenient: it also accepts `str` and `int` where `DataFrame[S]` is expected.
3. **Phantom-type variance.** For a PEP 695 phantom `S`, pyright and ty infer covariant, so they need the hack; pyrefly is invariant either way. A legacy `TypeVar` with `Generic[T]` is invariant in pyright, ty and pyrefly without any hack.
4. **pyright is noisy by default.**
   - `Table.__getattr__` returns the bare `ir.Column`, which has no arithmetic and no `.sum()`/`.mean()`. Idiomatic ibis code fails at default settings.
5. **No checker flags a column-name typo.** Schema-driven column typing is not delivered by the current design.

## What this means for users

- **pyright:** it is the only checker that delivers the advertised guarantees: a forgotten cast is flagged, invariance holds, and contract signatures flow through. Even then, you must silence reportOperatorIssue, and `.sum()`/`.mean()` on columns still fail.
- **mypy:** you get import errors, then `Any` everywhere.
- **ty and pyrefly:** you get partial safety (invariance, wrong-schema arguments), but a forgotten cast passes silently and columns are Unknown.
- **Making the checker claims true needs two changes:** ship `py.typed` in tacit, and design a frame type that does not rely on the ibis `Table` hierarchy for static typing. Otherwise the README's claims about mypy, ty and pyrefly should be softened.

## Not tested

- pyright strict mode.
- ibis stub packages.
- ty and pyrefly with `rich` uninstalled. The mixin theory is supported by the local repro, not by removing rich.
- Editor/LSP behaviour.
