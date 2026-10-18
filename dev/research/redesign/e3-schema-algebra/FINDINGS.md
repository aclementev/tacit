# E3 — Schema algebra across pyright, mypy, ty (and pyrefly)

> The E3 subagent (Opus) returned this as text, because subagents may not write report files. The main session saved it here.

**Question:** what can tacit type statically today for generic steps, derived schemas and joins?

**Versions:** pyright 1.1.414, mypy 2.4.0, ty 0.0.89, pyrefly 1.4.0 (bonus column), ibis 12.0.0, Python 3.13.

**Reproduce:**
- `uv run python matrix.py [--stock] <file>.py`. Raw outputs are `raw/*.{stock,patched}.txt`; full tables are `raw/MATRIX.{baseline,patched,stock}.md`.
- `uv run pytest test_runtime.py` (8 tests pass).
- `tx.py` is a standalone prototype of tacit's `Schema`/`DataFrame` with the changes listed in its docstring.

**Legend:**
- `R` = rejected by the checker.
- `A` = accepted.
- `W` = accepted, but with a wrong inferred type.
- `*` = the checker's result is **incorrect** (a false positive or false negative).
- `exp` = the correct result.

## 0. Before anything else: only pyright enforces tacit's types today

| baseline.py (tacit 0.2.0) | exp | pyright | mypy | ty | pyrefly |
|---|---|---|---|---|---|
| `return t` (ir.Table as DataFrame[Orders]) | R | R | A* | A* | A* |
| DataFrame[Customers] as DataFrame[Orders] | R | R | A* | R | R |
| DataFrame[Orders] as int | R | R | A* | A* | A* |
| ... the same three, with patched ibis | R | R | R | R | R |

There are two root causes. Both are upstream bugs, and each fix is about one line (see `ibis-typing.patch`):

1. **ty and pyrefly: unknown base class.** `ibis/expr/types/rich.py` defines `FixedTextJupyterMixin` in both the `try` and the `except` branch. The base becomes a union, which these checkers treat as an Unknown base. As a result, `ir.Table` and `DataFrame[S]` are assignable to anything.
2. **mypy: `Table` is `Any`.** `relations.py` re-imports `Table` under `TYPE_CHECKING` inside the module that defines it, so mypy treats `ir.Table` as `Any`.

Separately, neither ibis nor tacit ships `py.typed`. Without `follow_untyped_imports = True`, mypy treats all of tacit as `Any`. That part is tacit's own issue: add `src/tacit/py.typed`.

On stock ibis, all of the `Into[...]` techniques below (B2, J1) are wrongly accepted (A*) on mypy, ty and pyrefly. **Everything below was run against `_patched/ibis`**, which is ibis plus the two fixes.

Two more notes:
- Per CLAUDE.md rule 2, `dev/contributions/ibis-*-unknown-base` should be filed.
- `df.<anything>` is an `ir.Column` (or Unknown) on every checker. ibis's `__getattr__` never checks names.

## 1. Structural "at least these columns" generics: (i) works today

```python
class SchemaLike(Protocol):            # tx.py: DataFrame[S: SchemaLike], not S: Schema
    __tacit_schema__: ClassVar[bool]
class HasIdP(SchemaLike, Protocol):    # structural requirement
    id: int
class HasIdAndTsP(HasIdP, HasEventTsP, Protocol): pass   # "intersection" of requirements
def dedupe_p[S: HasIdP](df: DataFrame[S]) -> DataFrame[S]:
    return df.distinct(on="id")        # DataFrame overrides distinct/filter/order_by/limit/head/cache
```

| t1_structural.py | exp | pyright | mypy | ty | pyrefly |
|---|---|---|---|---|---|
| N: dedupe[S: HasId] (mixin) on Orders(HasId), returns DataFrame[Orders] | A | A | A | A | A |
| N: on Payments, which has `id` but not the mixin | R | R | R | R | R |
| P: dedupe_p(Payments), no mixin needed, returns DataFrame[Payments] | A | A | A | A | A |
| P: on Products (no `id`) / BadId (`id: str`) | R | R | R | R | R |
| P: needs_both[S: HasIdAndTsP] on a schema without `event_ts` | R | R | R | R | R |
| body: df.distinct/filter/order_by returned as DataFrame[S] | A | A | A | A | A |
| body: df.mutate(...) returned as DataFrame[S] | R | R | R | R | R |
| body: df.retag(df.mutate(...)) (checked at runtime) | A | A | A | A | A |
| body: df.tacit_schema.cast(...) (type[S], nominal bound) | A | A | A | A | A |
| body: typo `df.idd` | R | A* | A* | A* | A* |
| body: typo `df.tacit_schema.idd` | R | R | R | R | R |
| conforms(df, HasIdP): a Protocol passed as type[P] | A | A | R* (type-abstract) | A | A |
| tacit 0.2: tacit.DataFrame[S: HasIdP] | R (bound is Schema) | R | R | R | R |
| tacit 0.2: `return df.distinct()` as DataFrame[S] | R (methods return Table) | R | R | R | R |

**What tacit needs to change.** Generic steps where the schema goes in and comes out unchanged work on every checker, once tacit makes two changes:
1. Bind `DataFrame`'s TypeVar to a `SchemaLike` Protocol instead of the `Schema` class.
2. Override the ibis methods that keep the schema (`filter`, `distinct`, `order_by`, `limit`, `head`, `cache`) to return `DataFrame[S]`. These overrides pass every checker's override check.

Also add `retag()`, for "same columns, new values".

**Prefer Protocols over mixins.**
- Nominal mixins work too, but every schema author has to opt in.
- Protocols match any schema with the right column names and types, including schemas owned by other teams.

**Protocol caveat: variance.**
- Mutable protocol attributes are invariant, so `amount: int` does not satisfy `amount: float`.
- A `@property` member gives covariance, and every checker accepts it.
- `ReadOnly` on protocol members (PEP 767) is still a Draft, and every checker rejects it.

**There is no typed column access in the step body.** `type[S].id` is name-checked, but statically it is `int`, and at runtime it doesn't exist, because a bare annotation creates no class attribute. Real column access needs the `Column[T]` descriptors from E2.

**Runtime gap.** Applying `@tacit.contract` to a generic function raises `TypeError` at decoration time. It should instead:
- enforce the TypeVar's bound (a subset check);
- require that the output S equals the input S.

## 2. Additive generics (S becomes S + {score: float})

| t2_additive.py | exp | pyright | mypy | ty | pyrefly |
|---|---|---|---|---|---|
| A: `-> DataFrame[WithScore[S]]`, result passed to dedupe_p | A | R* | R* | R* | R* |
| B1: `add[S, O: Scored](df: DataFrame[S], out: type[O])` with out=ScoredCustomers for an Orders input | R | A* | A* | A* | A* |
| **B2**: `add[O: Scored](df: Into[O], out: type[O])` with out=ScoredOrders, returns DataFrame[ScoredOrders] | A | A | A | A | A |
| B2: out=ScoredCustomers for an Orders input | R | R | R | R | R |
| B2: out=Orders (no Scored), or has `score` but not the mixin | R | R | R | R | R |
| B2: result passed to dedupe_p and to needs_score | A | A | A | A | A |
| B2m: method `o.extend_to(ScoredOrders)`, inferred type | DataFrame[ScoredOrders] | W* DataFrame[Orders] | W* | ok | ok |
| **B2c**: classmethod `ScoredOrders.from_mutate(o, score=...)` | A | A | A | A | A |
| B2c: `ScoredCustomers.from_mutate(o)` | R | R | R | R | R |
| B2g: generic caller [S: HasIdP] calls add_score_b2(df, ScoredOrders) | R (can't name S+Scored) | R | R | R | R |
| C: Ext[S, E](DataFrame[S]), through dedupe_p or a second extension | keep E | lost* | lost* | lost* | lost* |
| D: Frame[*Parts], add_audit(add_score(o)) returns Frame[Orders, Scored, Audited] | A | A | A | A | A |
| D: consumer Frame[*P, Scored] when Scored is not last | A | R* | R* | R* | R* |

```python
class Into[S](Protocol):               # contravariant: DataFrame[A] is an Into[O] iff O <: A
    def __tacit_type_is_invariant__(self, x: S, /) -> object: ...
    def to_table(self) -> ir.Table: ...
class Schema:
    @classmethod
    def from_mutate(cls, df: Into[Self], /, **exprs: ir.Value | Deferred) -> DataFrame[Self]: ...
class ScoredOrders(Orders, Scored): pass                    # caller names S & Scored
scored = ScoredOrders.from_mutate(orders, score=model(orders))
def add_score[O: Scored](df: Into[O], out: type[O]) -> DataFrame[O]: ...   # reusable generic step
```

**B2 and B2c work on all four checkers.**
- They emulate the bound `O: (S & Scored)`. The caller names the output schema using multiple inheritance, and a single contravariant TypeVar checks `O <: S`.
- At runtime, `issubclass(out, <df's schema>)` and a strict cast check the rest.
- The classmethod form (B2c) is the most robust. Its receiver fixes the output type, so the checker has no TypeVar to solve.
- The bound-method form (B2m) infers the wrong type in pyright and mypy, because they bind `self` first.

**What remains blocked on the language (iv):**
- A generic caller cannot name `S + Scored` (B2g), so additive steps compose only at concrete call sites.
- A wrapper (A), Ext (C) or variadic Frame (D) can carry the extension, but each loses either the base columns or independence from ordering.
- TypeVar bounds cannot mention other TypeVars, and Python has no intersection types.

## 3. Derived schemas (pick / drop / rename / extend)

| t3_derived.py, t3d, t3e | exp | pyright | mypy | ty | pyrefly |
|---|---|---|---|---|---|
| (a) `class IrisFeatures(Iris)` (extend); bottom-up `Iris2(Sepal, Petal)` (pick) | as declared | ok | ok | ok | ok |
| (b1) `class X(Iris.pick(...))`, a dynamic base | A | A | R | A (warns) | R |
| (b1) same, with `pick -> type[Self]`: dropped column still visible | R | A* | A* | A* | A* |
| (b1) same, with `pick -> type[Schema]`: petal lookup | R | R | A* | A* | A* |
| (b1) `X = Iris.pick(...)`, then `DataFrame[X]` | A | R | R | R | A (as Iris)* |
| (b2) `class SepalV(VerifiedSchema, derive=pick(Iris, ...))` with columns written out | A | A | A | A | A |
| (b2) declared columns miss or drift from the derivation | import error | runtime | runtime | runtime | runtime |
| (c) codegen output: pick/rename/extend semantics, Cols TypedDict | as spec | ok | ok | ok | ok |
| (d) plugin: `IrisSepal = Iris.pick("a","b")`, then needs_petal | R | A* | **R** | A* | R |
| (d) plugin: `Iris.pick("typo")` | R | A* | **R** | A* | A* |
| (d) plugin: `to_scored(i, Iris.extend(score=float))` | A | R* | **A** | R* | R* |

**(a) Subclassing.** Class (i).
- Covers extend.
- Covers pick, if you build schemas bottom-up from mixins.
- Cannot drop or rename an inherited column.

**(b1) A runtime helper used as a base class.** Unsound or rejected on every checker. Don't ship it.

**(b2) Write the columns out and verify them at import** (`derive.VerifiedSchema`). Class (i).
- Exact on every checker.
- The duplication is checked: `__init_subclass__` compares the declared columns against `pick/drop/rename/extend(Base)` and raises on drift. This is tested.
- Cheap, but a 40-column pick still means copying 40 lines.

**(c) Codegen** (`codegen.py`: `cg_spec.py` produces `cg_generated.py`). Class (iii).
- Works on every checker, because it emits ordinary classes.
- `extend` emits `class IrisScored(Iris)`, so the B2 pattern works on the result.
- `pick`, `drop` and `rename` emit fresh Schema subclasses with `__tacit_derived_from__ = pick(Iris, ...)`, so the runtime can re-attach Annotated checks.
- Also emits `<Name>Cols` TypedDicts (see 3e).
- `--check` diffs against the committed file and exits 1 when it is stale (tested). That is the CI gate.
- Cost: a build step, and generated files to review.

**(d) mypy plugin** (`mypy_tacit_plugin.py`, about 150 lines, `get_dynamic_class_hook`). Class (iii).
- Works in mypy: name errors at the definition, exact columns, and `extend` produces a subtype.
- Handles only module-level `X = Base.op(<literals>)`.
- pyright does not support plugins, by maintainer decision.
- ty does not plan a plugin system (astral-sh/ty#2551).
- So it covers at most one of the three target checkers. Not worth it as the primary path.

### 3e. The TypedDict angle, and PEP status (late 2026)

| t3b_typeddict.py, t3c_pep_probes.py | exp | pyright | mypy | ty | pyrefly |
|---|---|---|---|---|---|
| `build_orders(t, **cols: Unpack[OrdersCols])`: missing / typo / wrong expression type | R | R | R | R | R |
| same, extra column | R | R | R | A* | R |
| `def f[TD: TypedDict](..., **kw: Unpack[TD])` (generic) | A | R | R | R | R |
| `class OrdersTD(Schema, TypedDict)` | A | R | R | R | R |
| PEP 728 `closed=True` / `extra_items=` (typing_extensions) | A | A/A | A/R* | A/A | A/A |
| PEP 764 inline `TypedDict[{"score": float}]` | A | R (A with enableExperimentalFeatures) | R | R | R |
| PEP 767 ReadOnly on a Protocol attribute | A | R | R | R | R |

**What `Unpack[TD]` gives.**
- Typed, complete select/mutate builders for concrete schemas (`Orders.build(t, id=..., amount=...)`).
- On every checker, these catch missing columns, typos and the wrong kind of ibis expression.
- One gap: ty misses extra keys.

**Limits.**
- Schemas cannot be TypedDicts, because a TypedDict allows no other bases.
- `Unpack` of a TypeVar is illegal, so the TypedDict has to be generated (codegen) or written by hand.
- TypedDicts have no Pick or Omit, only extension by inheritance.

**PEP status (peps.python.org/topic/typing, checked 2026-10-19):**
- Final: 692, 705, 728 (3.15) and 747 TypeForm (3.15).
- 747 lets a function accept a type expression. It does not compute new types, so it doesn't unblock pick, drop or `S + X`.
- Draft: 764 (inline TypedDict; pyright supports it behind an experimental flag) and 767 (ReadOnly attributes).
- Draft: 827 "Type Manipulation", for 3.16.
  - It adds Members/Attrs/NewProtocol/NewTypedDict/UpdateClass, conditional types and type comprehensions, and includes `Pick[T, Keys]` as an example.
  - Its only prototype is a mypy fork.
  - It is exactly what tacit's long-term vision needs, but it is years away, and three checkers would have to agree on it.
- Draft: 849 (groundwork for 827).
- Intersections: no PEP yet. A draft is being discussed on discuss.python.org, and no checker implements them.

## 4. Joins

| t4_joins.py | exp | pyright | mypy | ty | pyrefly |
|---|---|---|---|---|---|
| free function `join[O](l: Into[O], r: Into[O], out: type[O])`, valid call | A | A | R* ("cannot infer") | A | A |
| same, out not a subclass of the right input / wrong right input | R | R | R | R | A* |
| **`OrdersWithCustomer.from_join(o, c, "customer_id")`** returns DataFrame[OrdersWithCustomer] | A | A | A | A | A |
| same, OrdersOnly.from_join (same columns, not a subclass of Customers) / wrong right input | R | R | R | R | R |
| output schema inherits a column with conflicting types (customer_id int vs str) | R | R | R | A* | R |
| `join2[A, B] -> Joined[A, B]` tag type: right columns reach generic steps | A | R* | R* | R* | R* |

**The best achievable join is an explicit output schema `class AB(A, B)` plus the classmethod `AB.from_join(a, b, on)`.**
- Checked statically: `AB <: A` and `AB <: B`, through `Into[Self]`.
- Checked at runtime: `issubclass` plus a strict cast.
- Class (i) on all four checkers.
- Columns that collide, such as `name_right`, are declared on `AB`.

**Avoid the free-function form.** It trips mypy's solver, which cannot handle two contravariant bounds plus a lower bound. pyrefly accepts wrong outputs with it.

**Other options:**
- An inferred join output (`A & B`) is class (iv). It needs intersection types or mapped types.
- Codegen can emit `AB` from a `join(A, B, on=...)` spec entry. Class (iii).

## Classification

| Technique | Class |
|---|---|
| Generic steps that keep the schema (filter/distinct/order_by/... return DataFrame[S]) | (i) all checkers (needs a tacit change plus the ibis fix) |
| Structural requirements via schema Protocols, including combined Protocols | (i) |
| Nominal mixin requirements | (i), but every schema must opt in |
| `conforms(df, Proto)`, passing a Protocol as type[P] | (ii): mypy rejects it (type-abstract) |
| Additive steps where the caller names the output: `Out.from_mutate(df, ...)` / `f[O: X](df: Into[O], out)` | (i) |
| Same, as a bound method `df.extend_to(Out)` | (ii): pyright and mypy infer the wrong type |
| Additive steps with a computed output (`S + {score}`), or generic-of-generic composition | (iv) |
| Extend by subclassing; pick via bottom-up mixins | (i) |
| Pick/drop/rename with columns written out and verified at import (VerifiedSchema) | (i) |
| Pick/drop/rename/extend without restating columns | (iii): codegen (all checkers) / mypy plugin (mypy only) |
| `class X(Iris.pick(...))` / `X = Iris.pick(...)` used as a type | (iv): rejected or unsound |
| Typed `**Unpack[Cols]` builders for concrete schemas | (i), except ty misses extra keys |
| Generic `Unpack[TD]`, Schema-as-TypedDict, Pick/Omit on TypedDict | (iv) |
| Join with an explicit `AB(A, B).from_join(a, b)` | (i) |
| Join with an inferred output | (iv) (PEP 827 / intersections, not before 3.16+) |
| Typed, name-checked `df.col` access | (iv) through ibis's `__getattr__`; needs Column[T] descriptors (see E2) |

## Recommended layered strategy

1. **Fix the foundations first.** Until this is done, only pyright users get any safety.
   - Ship `py.typed`.
   - Upstream the two ibis fixes (`ibis-typing.patch`) and document them in `dev/contributions/`.
   - Run `tests/typechecking/` under pyright, mypy, ty and pyrefly.
2. **Layer 1: generic steps that keep the schema.**
   - Bind `DataFrame` to a `SchemaLike` Protocol.
   - Override the ibis methods that keep the schema, and add `retag()`.
   - Document "requirement Protocols" as the way to write reusable steps.
   - Teach `@contract` to enforce TypeVar bounds, output S equal to input S, and Protocol annotations.
3. **Layer 2: steps that change the schema, with a named output.**
   - Provide `Out.from_mutate(df, **exprs)` and `Out.from_join(a, b, on)`.
   - These use `Into[Self]` for the static check, and an issubclass check plus a strict cast at runtime.
   - For reusable additive steps, use `def step[O: Mixin](df: Into[O], out: type[O])`. The caller declares `class ScoredOrders(Orders, Scored): pass`, one line instead of 40.
4. **Layer 3: derivations without restating columns.**
   - `VerifiedSchema(derive=...)` as the option that needs no tooling.
   - `tacit gen` plus `tacit gen --check` in CI as the option that scales.
   - A mypy plugin, if ever, is optional sugar on top.
5. **Don't ship** statically opaque runtime helpers as typed APIs. Keep `Iris.pick()` runtime-only.
6. **Track** PEP 827 and an intersections PEP. If they land, the generated classes can become type aliases.

Sources:
- [PEP index, typing topic](https://peps.python.org/topic/typing/)
- [PEP 827](https://peps.python.org/pep-0827/), [PEP 849](https://peps.python.org/pep-0849/), [PEP 747](https://peps.python.org/pep-0747/), [PEP 764](https://peps.python.org/pep-0764/)
- [astral-sh/ty#2551](https://github.com/astral-sh/ty/issues/2551)
- [pyright mypy-comparison.md](https://github.com/microsoft/pyright/blob/main/docs/mypy-comparison.md)
- [Pulse check on Intersections draft work](https://discuss.python.org/t/pulse-check-on-intersections-draft-work/109087)

> Note: `_patched/ibis` is gitignored, because it is a 51MB copy of ibis. To regenerate it, copy `.venv/lib/python3.13/site-packages/ibis` into `_patched/` and then apply `ibis-typing.patch` with `patch -p1 -d _patched`.
