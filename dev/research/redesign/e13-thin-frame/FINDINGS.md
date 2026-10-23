# E13 — Thin runtime subclass + generated clean stub

> The E13 subagent (Opus) returned this report as text, and the main session saved it here. The main session also re-checked the key claims:
> - 46 of 46 runtime tests pass.
> - The getattr-mode matrix total is 231/231 (pyright), 228 (mypy), 226 (ty) and 227 (pyrefly).
> - The T2 matrix is 38/38 on pyright and 37/38 on the other three.
> - The T2 port of TPC-H Q1 is clean on all four checkers.
>
> Versions: ibis 12.0.0, pyright 1.1.414, mypy 2.4.0 (`follow_untyped_imports`), ty 0.0.89, pyrefly 1.4.0.

**Question.** The owner was concerned that E8's wrapper re-implements part of a large dataframe API and limits which features users can reach. The alternative tested here keeps the frame a real `ir.Table` subclass at runtime. Type checkers instead see a stub generated from ibis's own Table signatures, with `__getattr__` removed and a clean MRO.

**Headline: the hypothesis holds, with two corrections.**
- **What holds:**
  - Users get the whole ibis Table API directly on the frame.
  - Typos are caught on all four checkers.
  - "Forgot to cast" is caught on all four checkers.
  - The stub is generated from ibis 12 with **zero hand-fixes**.
  - The three E8 examples give identical output and 0 diagnostics on all four checkers.
- **Correction 1: forgot-cast needs a rewritten return type.** A clean *base* class is not enough. If ibis methods return the real `ir.Table`, forgot-cast is caught on pyright only, because `ir.Table` is `Any` in mypy and has an Unknown base in ty and pyrefly. The stub must rewrite ibis's return types to a clean mirror `Table`.
- **Correction 2: statically, a frame is not an `ir.Table`.** Passing a frame to ibis APIs typed `ir.Table` (`ibis.union(o, o)`, `t.join(o, ...)`) is a false positive on pyright and ty. Use `tc.as_table(o)`. At runtime it works.

## 1. The generator (`tools/gen_table_stub.py`, 341 lines)

**What it copies, mechanically:**
- It walks the runtime MRO of `ir.Table` and `GroupedTable` and copies signatures with `inspect`, keeping ibis's annotation strings.
- It recovers overloads with `typing.get_overloads` and `@deprecated` from the AST.
- It handles join factory methods and aliases.
- It resolves every annotation name against the defining module's imports, including `TYPE_CHECKING` blocks. No names were left unresolved.

**What it omits:** `__getattr__`, `__dir__`, `__init__`, private members, and the dataclass fields on GroupedTable. The emitted classes have no base class.

**Output:** about 160 lines, covering 102 methods, 1 property and 5 aliases.

**Rewrite rules** (mechanical, applied across all members):
- `Table` in a return type becomes the mirror class (56 sites). `GroupedTable` likewise (4 sites).
- `Table` in a parameter becomes `TableAPI | ir.Table` (18 sites).
- 68 parameters are widened so that ibis methods accept tacit's `Column[T]`. For example, `ir.XxxColumn` becomes `ir.XxxColumn | Column[..]`. This removes E8's interop false positives.

**Hand-fixes:** none. There are 3 opt-in patches for upstream annotation bugs. Each is a candidate for `dev/contributions/`:

| Upstream bug | Patched in |
|---|---|
| `t.join(s, pred)`: a single predicate isn't accepted, only a Sequence | 10 join methods |
| `t.select(s.numeric())`: Selector is missing from `select` | `select`, `projection` |
| `t.mutate(one=1)`: Python literals are rejected | `mutate` |

**Three stub modes:**

| Mode | What ibis methods return | Notes |
|---|---|---|
| `ibis` | real `ir.Table` | |
| `mirror` | a clean mirror `Table` with no `__getattr__` | |
| `getattr` (default) | `Table(TableAPI)`, which adds `__getattr__ -> ir.Column` | Frame's static base is `TableAPI`, which has no `__getattr__`. Plain `.x` keeps working on intermediate results. |

**Runtime feasibility.**
- `Expr` uses `__slots__`, but the Jupyter mixin gives instances a `__dict__`, so the frame can store `_arg`, `_names` and `_exprs` with `object.__setattr__`. This is the same trick tacit 0.2 uses.
- `op().to_expr()` returns a plain Table, so every ibis method drops the schema.
- `__reduce__` is overridden to keep pickling working.
- A `__getattr__` defined only at runtime gives "did you mean" hints.
- Verified at runtime: `isinstance(o, ir.Table)`, `ibis.union(o, o)`, `con.create_table("x", o)`, joins, windows, caching and pickling.

## 2. Descriptors and name collisions

**Descriptors take precedence.** `Column` is a data descriptor, and ibis's `__getattr__` only runs when normal lookup fails.

**Collisions are the real cost.**
- The frame shares one namespace with the whole ibis Table API, so **84 names are reserved**: 80 ibis members plus `conform`, `parse`, `extend` and `aggregate_by`. The E8 wrapper reserves 14.
- About 25 of those are plausible column names: `count`, `sample`, `view`, `info`, `schema`, `columns`, `describe`, `alias`, `sql`, `rowid`, `op`, `limit`, `cast`, `head`, `drop`, `rename`, `filter`, `select`, `union`, `distinct`, `difference`, `topk`, `nunique`, `preview`, `cache`.
- A collision is reported twice:
  - at class creation, which raises with a suggested fix (`count_: Column[int] = tc.field(name="count")` or `frame["count"]`);
  - statically, on all four checkers.
- Raising is mandatory. A column named `select` would break ibis internals that call `self.select`.
- E8's `cast` and `aggregate` had to be renamed to `conform` and `aggregate_by`.

**Upgrade hazard:** if a future ibis release adds a Table method, any existing column with that name becomes an import-time error.

## 3. Type-check matrix (231 cases)

The test cases are E8's t01–t10 adapted, plus t11 (direct use of the ibis API) and t12 (collisions).

| Mode | pyright | mypy | ty | pyrefly |
|---|---|---|---|---|
| T-getattr (default) | 231/231 f6 | 228 m1 w2 f3 | 226 m2 w3 f4 | 227 m2 w2 f1 |
| T-mirror | 231/231 f6 | 228 m1 w2 f3 | 226 m2 w3 f5 | 227 m2 w2 f2 |
| T-ibis returns | 231/231 f9 | 203 m6 **w22** | 221 m7 w3 f6 | 222 m7 w2 f1 |

Legend: `f` = false positives, `m` = missed errors, `w` = wrong inferred types.

**Results by area:**
- **Same as E8 on all four checkers:** typed columns, typos, wrong methods, arithmetic, nullability, constructor, aggregation, `extend`/`Into`, generic steps, join scope, `@step`.
- **Typos inside ibis calls** (`o.group_by(..).agg(t=o.amout.sum())`) **or in ibis method names** (`o.mutat`): caught on all four.
- **Calling ibis methods directly on the frame:** 27 revealed types checked. pyright, mypy and ty get 27/27; pyrefly gets 26/27 (union order only, cosmetic). In `ibis` mode, mypy gets 8/27 because everything is `Any`.
- **Forgot cast after an ibis operation** (5 cases): in getattr and mirror modes, 5/5 on all four. In `ibis` mode, pyright only.
- **Raw `ir.Table` passed where a frame is expected:** caught by pyright only. This is upstream (E1/E2), the same as in E8.

**Remaining false positives:**
- A frame passed to an ibis API typed `ir.Table`: pyright and ty.
- In getattr mode, a frame passed to a function annotated `tc.Table`: all four checkers. Annotate with `tc.TableAPI` instead.
- `m["x"] > 1` on untyped intermediate results: pyright and mypy. These are ibis's own comparison and `Column` typing bugs.

## 4. Examples and overhead

**Examples.**
- iris and TPC-H port with only the renames, and their output is identical.
- ecommerce adds a step using plain ibis directly on the frame (`group_by().agg`, then `mutate` with a window share), which re-enters through `StatusSummary.conform`.
- 0 diagnostics on all four checkers in every mode when written with `_.revenue`.
- The attribute spelling on untyped intermediates (`by_status.revenue.sum()`) falls back to ibis's own typing quality. That gives false positives in pyright and mypy, exactly as `.ibis` did in E8.

**Overhead.** The cost of building expressions is the same order of magnitude in W, T and plain ibis (`out/overhead.txt`).

## 5. Variant T2: `DataFrame[S]` + clean stub + typed `df.c`

**Package:** `src/tacit_t2/`, 243 lines. It reuses T's facade, fields, validation and stub.

**Spelling.**
- Schemas are declared as `class Orders(tc2.Schema)`.
- `DataFrame[S]` is an `ir.Table` subclass at runtime, while its static base is `TableAPI` (S is covariant).
- `df.c` is an `S` bound to `df`, so `df.c.amount` is `Column[float]`.
- Construction is `Out.build(**kw) -> DataFrame[Out]`, using the ParamSpec-on-`cls` trick.
- Adding columns is `Out.extend(base, Delta.build(..))`.
- `Schema.parse` and `Schema.conform` return `DataFrame[Self]`.
- Generic steps look like `def f[S: HasTs](df: DataFrame[S]) -> DataFrame[S]`.

**Matrix (38 cases):** pyright 38/38 (1 false positive), mypy 37 (1 miss), ty 37 (1 miss, 1 false positive), pyrefly 37 (1 miss).
- The only miss is the raw `ir.Table` case (upstream).
- The only false positive is `x: ir.Table = df`, on pyright and ty.

**Control: T2 without the clean stub** (`tacit_t2n`): pyright 36, **mypy 25, ty 31, pyrefly 31**.
- Typos via `.c` are still caught.
- `df.anything` passes silently.
- The forgot-cast, wrong-frame and extend checks are lost on mypy, ty and pyrefly.
- So the stub is what buys the frame-level guarantees on those three checkers.

**T2 compared with schema-as-frame:**
- **Pros:**
  - The collision surface is about 5 names: `c`, plus `build`, `parse`, `conform` and `extend` on the schema.
  - Columns can be named `count`, `schema` or `view`.
  - Future ibis methods never break user schemas.
  - It is closest to tacit 0.2's spelling.
  - ibis attributes and tacit columns are visibly separated.
- **Cons:**
  - `.c.` appears on every column access.
  - Construction is `Out.build(...)` rather than `Out(...)`.
  - T2 join views were not built.
  - The ParamSpec trick needs a library-internal `type: ignore` for pyrefly and an `S: Schema` bound for ty.

## Comparison

| | W (E8 wrapper) | T (thin + stub, getattr) | T2 (`DataFrame[S]` + stub + `.c`) |
|---|---|---|---|
| Typo `frame.col` | Y on all four | Y on all four | Y on all four (`df.c.x`; `df.x` is also an error) |
| Forgot cast: ibis-op result passed as a frame | n/a (only through `.ibis`) | Y on all four | Y on all four |
| Forgot cast: raw `ir.Table` passed as a frame | pyright only | pyright only | pyright only (upstream E1/E2) |
| ibis API directly on the frame | no (~10 typed methods; the rest via `.ibis`) | yes, all 80 members | yes, all 80 members |
| Static coverage of the ibis API | ibis annotations via `.ibis` (`Any` on mypy) | all 102 members, clean on mypy too | same as T |
| Frame where ibis expects `ir.Table` | `.ibis` | works at runtime; static false positive on pyright/ty (use `tc.as_table`) | same as T |
| Column-name collision surface | 14 names | 84, growing with each ibis release | about 5 |
| Generated code besides the shared facade | 0 (hand-written subset) | 160-line stub from a 341-line generator; 0 hand-fixes | same stub |
| Maintenance on an ibis upgrade | rare manual edits | regenerate; new ibis names can break user schemas | regenerate; no breakage for users |
| Runtime overhead | one extra attribute hop | none | none |

## Recommendation (E13)

**Adopt the thin runtime subclass with the generated clean stub in getattr mode, spelled as T2 (`DataFrame[S]` + `df.c`).**

**Why not the wrapper (W).** T is strictly better on the owner's concern:
- Nothing is re-implemented.
- Users get the full ibis API.
- Static safety is equal or better on every row.
- The ongoing cost is a generator rather than a hand-written layer.

**Why T2 over T.** T's collision surface (84 names, growing with each ibis release) is a recurring hazard for users: `count`, `limit` and `cast` are all common column names. T2 removes it at the cost of `.c.` on each column access.

**Caveats:**
- The stub must rewrite ibis's return types to the clean mirror.
- Use `tc.as_table(x)` when handing a frame to ibis functions under pyright or ty.
- Upstreaming E1/E2 and the three annotation bugs would remove the patches and the raw-table misses.

**Not done:** T2 join views, editor autocomplete, and re-running E8's bug-injection matrix.

## Files

- `tools/gen_table_stub.py`: the stub generator.
- Packages:
  - `src/tacit_thin/`: T, including the generated `_ibis_api.pyi`.
  - `src/tacit_t2/`: T2.
  - `src/tacit_t2n/`: T2 without the clean stub (the control).
- Tests:
  - `tests/typecheck/`: t01–t12, run with `run_matrix.py --tag <mode>`.
  - `tests/typecheck_t2/`
  - `tests/test_runtime.py`
- `examples/`, including `examples/t2/tpch_q1_t2.py`.
- `probes/`
- `out/`: matrices for each mode, generator reports, example checks, overhead.
