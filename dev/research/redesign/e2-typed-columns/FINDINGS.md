# E2 — Typed columns inside transformation code

> The E2 subagent (Opus) returned these findings as text, because subagents may not write report files. The main session saved them here.

This spike tested whether the schema can drive static typing *inside* contract bodies. It ran on pyright 1.1.414, mypy 2.4.0, ty 0.0.89 and pyrefly 1.4.0 (bonus), with ibis 12.0.0 on Python 3.13, and used no checker plugins. Every prototype also runs against duckdb.

**Reproduce:**
- Run `./check.sh probes/<name>.py`.
- It writes the raw output of each checker and of the runtime run to `out/<name>.{pyright,mypy,ty,pyrefly,runtime}.txt`.
- `summarize.py` merges those into a per-line table in `out/<name>.summary.txt`.
- mypy runs with `follow_untyped_imports = True` (see E1).
- The prototype lives in `proto/`: `frame.py` (~170 lines) plus three alias modules.

**Legend:** P = pyright, M = mypy, T = ty, R = pyrefly. `Y` = correct, `N` = missed (silently accepted), `FP` = false positive on valid code.

## TL;DR

The recommended design is **A4: the schema class is the typed frame**.

- **Wrapper, not subclass.** Each frame is a wrapper class, not a subclass of `ir.Table`.
- **Typed columns.** Columns are typed descriptors, declared through aliases such as `sepal_length: tacit.Float64`.
- **Facade type.** Accessing a column on an instance returns a **static-only facade that tacit owns**, layered over ibis's `*Value` classes.
- **Checked projection.** A `dataclass_transform` constructor acts as a checked projection.
- **Adding columns.** A "delta" class plus `extend()` adds new columns.

A4 was the only variant where **all four checkers got everything right**:
- typed column access;
- typos on the frame;
- wrong column methods;
- comparisons with literals;
- arithmetic and reductions;
- missing, unexpected or mistyped output columns.

Both examples run unchanged at runtime, and TPC-H Q1 produces byte-identical results.

Costs:
1. A breaking schema syntax: `tacit.Float64` instead of `float`.
2. Tacit has to maintain a small stub surface for ibis column methods.
3. Adding columns requires a delta class.
4. A few ibis annotation bugs remain. The facade hides most of them, but they should be fixed upstream.

## E. What ibis 12 types correctly on its own (`probes/e_ibis_types.py`)

In this table, x and y are `FloatingColumn` and s is a `StringColumn`.

| expression | P | M | T | R |
|---|---|---|---|---|
| `t.x`, `t.typo` (`Table.__getattr__`) | `Column`, typo N | `Any` | `Unknown` | `Unknown` |
| `x / y`, `x * 2` | `NumericValue` | same | `NumericValue & Unknown` | `NumericValue` |
| `1 - x` | `NumericValue` | same | **`int`** (wrong) | **`int`** (wrong) |
| `x > 5`, `s <= "1998-09-02"` | **FP** operator error | **FP** | `Unknown` | **`bool`** (wrong) |
| `x == 1.0`, `s == "a"` | **`bool`** (wrong) | `bool` | `Unknown` | `bool` |
| `x > y`, `(x>y) & (x<y)` | `BooleanValue` | same | `& Unknown` | same |
| `x.mean()`, `x.sum()` / `x.count()` | `NumericScalar` / `IntegerScalar` | same | same | same |
| `(x / y).mean()` | **FP** (no `.mean` on `NumericValue`) | FP | `Unknown` | FP |
| `s.upper()` / `s.length()` | `StringColumn` / `IntegerValue` | same | `& Unknown` | same |
| `s / x`, `s.mean()`, `x.upper()` (real bugs) | Y | Y | **N** | **N** |
| `t.mutate(one=1)` | FP (known Issue 2) | `Any` | FP | FP |
| `t.mutate/filter/select/join/group_by().agg` | `Table`/`GroupedTable` | **`Any`** | `Table` | `Table` |
| `ibis.cases(...)` | `Value` (no dtype) | same | same | same |
| `ibis._.x > 1` | `Deferred` | `Any` | `Unknown` | `Deferred` |

The spike found four new upstream issues. Each has a minimal repro, and each is a candidate for `dev/contributions/`.

- **E1. mypy: `ir.Table` resolves to `Any`.**
  - ibis ships no `py.typed`, so mypy needs `follow_untyped_imports`.
  - Even with that flag, `relations.py` does `if TYPE_CHECKING: from ibis.expr.types import Table` and then defines `class Table`. mypy reports `no-redef` and the class becomes `Any`.
  - Result: every Table method is `Any` under mypy.
  - Repro: `upstream_repro_mypy_table_any/`. Fix: drop the self-import.
  - **Tacit also ships no `py.typed`.** That one is our issue, and we must fix it for mypy users.
- **E2. ty and pyrefly: every ibis `Column` and `Table` has an Unknown base.**
  - `FixedTextJupyterMixin` (`ibis/expr/types/rich.py`) is defined in both branches of a `try/except ImportError`, and ty and pyrefly treat the union as an Unknown base.
  - Any attribute or argument check on a column then passes silently, for example:
    - `x.upper()` on a float column is accepted;
    - a `StringColumn` is accepted where a `NumericValue` is expected;
    - `1 - x` is inferred as `int`.
  - Repro: `upstream_repro_conditional_base/`. It includes a fixed shape (a single definition under `if TYPE_CHECKING:`) that works in all four checkers.
  - The `*Value` classes are not affected.
- **E3. Comparison operators are typed too narrowly.**
  - `Value.__gt__/__lt__/__ge__/__le__(other: Value)` reject Python literals.
  - `__eq__/__ne__(other: Value)` make `col == "a"` fall back to `bool`.
  - Fix: accept literals, and type `__eq__` as taking `object`.
- **E4. Arithmetic and helpers lose type information.**
  - `NumericValue.__truediv__` and friends return `NumericValue`, which drops column-ness, so `(a / b).mean()` is rejected.
  - `Value.isin(Iterable[Value])` rejects `["setosa"]` (P, M, T).
  - `ibis.cases` returns an untyped `Value`.

## A. Column declaration variants

`probes/_a_template.py` generates the `a_ann`, `a_desc` and `a_facade` probes. All three variants share one runtime, `proto/frame.py`. `Frame.__init_subclass__` reads the ibis dtype from the `Annotated` metadata and installs a `Col` descriptor for each field. Accessing a column on an instance returns `self._table[name]`; accessing it on the class returns `ibis._[name]`, which is a `Deferred`.

```python
# A3 (aliases_ann.py): static type IS the ibis column type, dtype rides in Annotated
Float64 = Annotated[ir.FloatingColumn, dt.float64]
# A1 (aliases_desc.py): typed descriptor; Get = instance-access type, Set = constructor param type
class Col[G, S]:
    @overload
    def __get__(self, obj: None, owner: type) -> Deferred: ...
    @overload
    def __get__(self, obj: Frame, owner: type) -> G: ...
    def __set__(self, obj: Frame, value: S) -> None: ...   # read by dataclass_transform
Float64 = Annotated[Col[ir.FloatingColumn, ir.NumericValue], dt.float64]
# A4 (aliases_facade.py): A1 with Get = a static-only facade over ibis *Value classes
if TYPE_CHECKING:
    class NumCol(ir.NumericValue):              # clean MRO (no Unknown base, see E2)
        def __truediv__(self, other: NumLike) -> NumCol: ...
        def __gt__(self, other: NumLike) -> BoolCol: ...   # literals OK (E3)
        def mean(self) -> ir.FloatingScalar: ...           # column reductions survive arithmetic
else:
    NumCol = ir.NumericColumn                   # runtime: no wrapper, real ibis exprs
Float64 = Annotated[Col[NumCol, ir.NumericValue], dt.float64]
# user code, identical for all three:
class Iris(Frame):
    sepal_length: Float64
    species: String
```

**Key enabling result** (`probes/c_dt_isolated.py`):
- **Descriptors work through `dataclass_transform`.** With annotation-only declarations, all four checkers apply the descriptor's overloaded `__get__`, and all four take the synthesized `__init__` parameter types from `__set__`.
- **A base-class `__init__(**kw)` does not shadow the synthesized one.**
- **`Frame`'s own attributes are not fields.** Attributes declared on the decorated `Frame` class itself, such as `_table`, are not treated as fields.

| property | A3 Annotated | A1 descriptor | **A4 facade** |
|---|---|---|---|
| `iris.sepal_length` type | `FloatingColumn` (Y in all 4) | `FloatingColumn` (Y in all 4) | `NumCol` (Y in all 4) |
| `Iris.sepal_length` (class access) | static `FloatingColumn`, runtime `Deferred` (a lie) | `Deferred` (all 4) | `Deferred` (all 4) |
| typo: `iris.sepal_lenght` / `Iris.sepal_lenght` | Y in all 4 | Y in all 4 | Y in all 4 |
| `species.mean()`, `sepal_length.upper()` | P, M Y; T, R **N** (E2) | P, M Y; T, R N | **Y in all 4** |
| `sepal_length > 5.0` | P, M **FP**; T Unknown; R `bool` | same | **`BoolCol`, all 4** |
| `species == "setosa"` | `bool` (wrong) | same | **`BoolCol`, all 4** |
| `(a / b).mean()` | P, M, R FP | same | **`FloatingScalar`, all 4** |
| filter via class access, `Iris.x > 5.0` | P, M, R FP | OK (Deferred) | OK |

## B. Wrapper vs subclass

Evidence comes from `probes/b_access.py` and the B2/B4 rows of the A probes.

| design | typo `frame.sepal_lenght` | ibis API reachable statically |
|---|---|---|
| B1: subclass `ir.Table` with declared columns (today's shape) | **N in all 4** | yes, the full Table |
| B3: wrapper with `def __getattr__(...) -> Any` delegating | **N in all 4** (`Any`) | yes, but everything is `Any` |
| B3b: wrapper with `__getattr__` only under `if not TYPE_CHECKING` | Y in all 4 | no: `.mutate` is an error in all 4 |
| **B2: wrapper with `.t -> ir.Table`** | Y in all 4 | yes, via `.t` (P/T/R: `Table`; M: `Any`, see E1) |
| **B4: typed delegated subset** | Y in all 4 | `filter/order_by/limit -> Self` (all 4 reveal `Iris`); `mutate -> ir.Table`; `group_by -> GroupedTable` |

**Typo detection requires a wrapper.**
- Any `__getattr__` that checkers can see kills typo detection.
- Subclassing `ir.Table` brings ibis's `__getattr__` along with it.
- Wrapping is therefore the only design that keeps typo detection.

**Ergonomics come from combining B2 and B4.**
- Operations that keep the schema return `Self`.
- Anything that changes the schema goes through `.t` and comes back through a constructor or a `cast`.
- Typos made after `.t` fall back to plain ibis behavior.

**Runtime cost:** one extra attribute hop, with no proxying of expressions.

**Name collision risk:** columns cannot be named `t`, `filter`, `parse` and so on. To manage this:
- keep the method set tiny;
- raise in `__init_subclass__` when a column name collides;
- offer `frame.t["count"]` as the fallback.

## C. Typed construction of an output schema

**The constructor as a projection.** These results come from the `a_*` probes. At runtime, `Frame.__init__` selects the given expressions over their single parent relation and then runs a strict structural check.

| `IrisFeatures(...)` call | A3 | A1 | **A4** | runtime (all variants) |
|---|---|---|---|---|
| missing `petal_area` | Y in all 4 | Y in all 4 | Y in all 4 | `missing=['petal_area']` |
| unexpected `bogus=` | Y in all 4 | Y in all 4 | Y in all 4 | `extra=['bogus']` |
| `sepal_ratio=iris.species.upper()` | P, M Y; T, R N | P, M Y; T, R N | **Y in all 4** | `wrong={'sepal_ratio': ...}` |
| `species=iris.petal_width` | P, M Y; T, R N | P, M Y; T, R N | **Y in all 4** | wrong dtype |
| valid arithmetic `a / b` into a float column | **FP in P, M** | OK | OK | OK |

A3 is unusable for construction because its parameter type equals its access type. A1 and A4 work because the descriptor has a separate `Set` type (`NumericValue` / `StringValue` / `IntegerValue`).

**Implicit GROUP BY** (`rec_tpch.py`):
- If any constructor argument is a reduction, the column-shaped arguments become the group keys.
- TPC-H Q1 becomes a fully checked `PricingSummary(l_returnflag=li.l_returnflag, ..., sum_qty=li.l_quantity.sum(), ...)`.
- It produces zero errors in all four checkers and the same result as `examples/tpch_q1.py`.

**Carrying parent columns over without retyping them** (`probes/c_extend.py`):

- **What works in all four checkers: a delta class.**
  - `class Ratios(Frame)` declares only the new columns, and `class IrisFeatures(Iris, Ratios): pass`.
  - The call is `IrisFeatures.extend(iris, Ratios(sepal_ratio=..., petal_area=...))`.
  - The delta's constructor checks the call: a missing new column and a str-into-float argument are each flagged by all four.
  - `extend` itself is only typed `(base: Frame, *parts: Frame) -> Self`.
  - A delta that doesn't match the target is caught at runtime. For example, `extend(iris, Iris.cast(...))` raises `missing=['petal_area','sepal_ratio']`. The check is metadata-only and runs before execution.
- **What cannot be expressed:** `IrisFeatures.extend(iris, sepal_ratio=...)` with only the new columns required.
  - Dataclass-style inheritance always makes parent fields required.
  - "Has a default" is fixed by the class that declares the field, so giving `Iris` fields defaults would also weaken `Iris(...)`.
  - `**kw: Unpack[TD]` needs a concrete, hand-written TypedDict per class, because PEP 692 forbids a TypeVar there.
  - A ParamSpec copied from `cls.__init__` brings all the fields back.
  - Typing `**iris.columns()` as a Mapping silences the missing-argument check for every field.
- **Cosmetic:** field order follows `get_type_hints`, so delta fields come first. A real implementation should order fields by their declaring base.

## D. Subtyping

Evidence comes from `probes/d_subtyping.py` and `probes/d_protocol_assigned.py`.

- **Shape 1: inheritance** (`IrisFeatures(Iris)`).
  - All four checkers accept `IrisFeatures` where `Iris` is expected. That is covariant, "has at least these columns" semantics, whereas today's `DataFrame[S]` is invariant.
  - This conflicts with strict runtime checking. In the probe, `takes_iris(features)` type-checks, but `Iris.cast(features.t)` raises `extra=['sepal_ratio']`.
  - To stay consistent, input boundaries should check "at least these columns" and then **project to the declared columns**. Strict extra-column checks belong on outputs and on `parse`.
- **Shape 2: siblings over an abstract column set.**
  - The classes are `IrisCols(Frame)`, `Iris2(IrisCols)` and `Features2(IrisCols)`.
  - All four checkers reject `Features2` where `Iris2` is expected, and accept it where `IrisCols` is expected. This restores invariance where you want it.
- **Generic code.**
  - `def f[F: Frame](df: F, ...) -> F` with `df.filter(...)` keeps the concrete type in all four checkers.
  - A structural `Protocol` with `@property sepal_length -> NumCol` works in M, T and R. **pyright rejects it**, because it skips the descriptor's `__get__` when matching protocols. That is worth a pyright issue.
  - A protocol declared with the alias itself fails in all four.
  - So column protocols are not portable yet.

## Summary matrix

This compares today's `DataFrame[S]` with the recommended combination: A4, plus B2/B4, plus the delta class from C.

| property | today `DataFrame[S]` (P/M/T/R) | A4 (P/M/T/R) |
|---|---|---|
| column access typed | `Column`/`Any`/`Unknown`/`Unknown` | Y/Y/Y/Y |
| typo on a frame column | N/N/N/N | Y/Y/Y/Y |
| wrong column method | N/N/N/N | Y/Y/Y/Y |
| literal compare, arithmetic, reductions | FP (`reportOperatorIssue` disabled) | Y/Y/Y/Y |
| output missing / extra column | N (runtime only) | Y/Y/Y/Y |
| output wrong expression category (str vs num) | N | Y/Y/Y/Y |
| int vs float column | N | N (both `NumCol`; caught at runtime) |
| `ibis.cases(...)` into a `String` column | n/a | **FP in all 4** (`Value`) |
| `t.order_by(frame.col)` | OK | **FP in P, T** (`Frame.order_by` accepts it) |
| `.isin(["a"])` | FP in P, M, T (ibis) | same |
| plain mypy (`ignore_missing_imports`) | everything `Any` | frame typos and missing/extra columns still Y; column types `Any` |

## Recommendation

Adopt A4:

1. **Schema syntax.** `class X(tacit.Frame)` declares columns with aliases such as `tacit.Float64` and `tacit.String`. Each alias is `Annotated[Col[Facade, SetType], dtype]`.
2. **Wrapper.** A wrapper exposing `.t` (B2), plus a tiny typed subset (B4) in which `filter`, `order_by`, `limit` and `distinct` return `Self`.
3. **Constructors.** `dataclass_transform` constructors act as projections, with implicit GROUP BY for reductions.
4. **Adding columns.** `extend(base, Delta(...))`.
5. **Subtyping.** A nominal subclass means "has at least these columns", with projection on inputs. The sibling shape is documented as the way to get invariance.

**Effect on `@contract`.** Structural guarantees now come from construction itself. A function that returns `IrisFeatures` can only return a value that passed the structural check. `@contract` therefore shrinks to an opt-in for `validate=True` data checks.

**Trade-offs:**
- **Breaking syntax.**
  - Schema annotations become tacit aliases rather than `float` or `str`, because the static type has to be the expression type.
  - Nesting constraints as `Annotated[tacit.Float64, Check.ge(0)]` should work, since Annotated flattens, but this was **not tested**.
- **The facade is surface that tacit owns.**
  - Every ibis column method that users want typed exactly must be declared on `NumCol`, `StrCol` and so on. Anything else falls back to ibis's own `*Value` annotations, which are clean.
  - Missing column-only methods (`nunique`, `topk`, `value_counts`, ...) show up as false positives until they are added.
  - The facade is not statically an `ir.Column`, so ibis APIs typed to accept only `Column` reject it (for example `Table.order_by`). Declaring the facade under `ir.Column` would bring back the E2 Unknown base.
- **Adding columns needs a delta class**, or a full constructor that restates every carried column.
- **mypy users** need `follow_untyped_imports`, and tacit must ship `py.typed`. Until E1 is fixed upstream, `.t` is `Any` under mypy.
- **Upstream fixes.** Send E1–E4 to ibis in parallel. As fixes land, A1 can replace the facade.

## Sketches

These are runnable as `probes/rec_iris.py` and `probes/rec_tpch.py`. Both produce zero diagnostics in all four checkers, except where noted.

```python
class Iris(tacit.Frame):
    sepal_length: tacit.Float64
    sepal_width: tacit.Float64
    petal_length: tacit.Float64
    petal_width: tacit.Float64
    species: tacit.String

class Ratios(tacit.Frame):                      # delta: only the new columns
    sepal_ratio: tacit.Float64
    petal_ratio: tacit.Float64
    petal_area: tacit.Float64

class IrisFeatures(Iris, Ratios): pass
class Prediction(tacit.Frame):
    predicted_species: tacit.String
class IrisPrediction(IrisFeatures, Prediction): pass

def engineer_features(df: Iris) -> IrisFeatures:
    return IrisFeatures.extend(df, Ratios(
        sepal_ratio=df.sepal_length / df.sepal_width,
        petal_ratio=df.petal_length / df.petal_width,
        petal_area=df.petal_length * df.petal_width,
    ))

def predict(df: IrisFeatures) -> IrisPrediction:
    species = ibis.cases((df.petal_length < 2.5, "setosa"),
                         (df.petal_length < 4.8, "versicolor"), else_="virginica")
    # FP in all 4: ibis.cases -> Value (needs a typed tacit.cases or an upstream overload)
    return IrisPrediction.extend(df, Prediction(predicted_species=species))
```

```python
def filter_shipped(li: LineItem) -> LineItem:
    return li.filter(li.l_shipdate <= "1998-09-02")       # -> Self, no cast

def pricing_summary_report(li: LineItem) -> PricingSummary:
    disc_price = li.l_extendedprice * (1 - li.l_discount)  # NumCol in all 4
    return PricingSummary(                                 # keys + reductions => GROUP BY
        l_returnflag=li.l_returnflag,
        l_linestatus=li.l_linestatus,
        sum_qty=li.l_quantity.sum(),
        sum_base_price=li.l_extendedprice.sum(),
        sum_disc_price=disc_price.sum(),
        sum_charge=(disc_price * (1 + li.l_tax)).sum(),
        avg_qty=li.l_quantity.mean(),
        avg_price=li.l_extendedprice.mean(),
        avg_disc=li.l_discount.mean(),
        count_order=li.l_orderkey.count(),
    ).order_by(PricingSummary.l_returnflag, PricingSummary.l_linestatus)
```

At runtime, the iris prediction counts are `{'setosa': 50, 'versicolor': 45, 'virginica': 55}`, and the Q1 table is identical to the one from `examples/tpch_q1.py`.

## Not covered / open

- pandera validation inside `parse`, nullability, and constraints written in the new alias syntax.
- Joins: building a `Frame` from two relations needs a constructor that accepts expressions from multiple parents.
- Splitting the facade into int and float types, and covering temporal, array and struct columns.
- How autocomplete feels in an editor. Only checker output was measured.
