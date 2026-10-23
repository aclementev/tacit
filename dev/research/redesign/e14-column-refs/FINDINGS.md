# E14 — Functional column references: `Orders.amount`, `col("x")`, `df["x"]` vs `df.c.x`

> The E14 subagent (Opus) returned this report as text, and the main session saved it here.
> The main session re-checked the results:
> - 9 of 9 runtime tests pass.
> - The 161-case matrix totals are pyright 144, mypy 138, ty 140 and pyrefly 142.
>
> Versions: ibis 12.0.0, duckdb, pyright 1.1.414, mypy 2.4.0 (`follow_untyped_imports`), ty 0.0.89, pyrefly 1.4.0.
> `run_all.sh` regenerates everything.

## Short answer

- **A free `col("amount")` cannot be checked statically.** See §1 for why.
- **There is a typed equivalent of ibis's `_`: the schema class itself.**
  - `Orders.amount` is `Ref[Orders, float]` statically, and ibis `_["amount"]` at runtime.
  - The checker verifies the column name, the value type, nullability, and that the ref's owner schema matches the frame it is used on.
  - This works on pyright, ty and pyrefly. mypy has a bug with bare refs (§2.3).
  - It also fixes the unsound class-level access found in E8.
- **String keys can be typed only by generating code per schema.**
- **TypedDict** types `td["k"]` well, but Python offers no way to go from a schema class to its TypedDict. So it adds nothing beyond generated overloads.

## 1. Why `col("x")` can't be checked, and how TypedDict does it

**The core problem.** A free function's return type can depend only on its argument type, here `Literal["amount"]`, and not on the frame the result is later used with.
- Checking the name would need a `keyof S` operator.
- Knowing the value type would need the schema.
- Python's type system has no `keyof`, mapped types or conditional types.

**ibis's `_` has the same problem.** It is a `Deferred` whose `__getattr__` returns `Deferred`, so any attribute is accepted. In the bug matrix it catches 0–1 of 8 planted bugs.

**How TypedDict gets away with it.** All four checkers special-case `td["k"]` on a TypedDict type. The key must be a declared literal key, the result is that key's declared type, and mypy and ty add "did you mean" hints. This also works through a TypeVar bounded by a TypedDict.

It works only because the key-to-type table *is* the type. A schema class has no such table, so overloads are the only substitute.

## 2. Owner-typed class refs (`Ref[O, T]`)

### Mechanism

**The descriptor captures the owner.**
- `__get__(obj: None, owner: type[_O]) -> Ref[_O, T]` handles class access.
- `__get__(obj: SchemaBase, owner) -> Self` handles `df.c.x`.
- An inherited column gets the subclass as owner: `NetOrders.amount` is `Ref[NetOrders, float]`.

**Variance.** `Ref` is contravariant in O and covariant in T. So a parent-schema ref is accepted on a child frame, and `DataFrame[S_co]` methods accept `Ref[S_co, ...]`.

**The ref types are generated mechanically.** `tools/gen_ref_facade.py` (142 lines) rewrites the column facade:
- `Column[X]` becomes `Ref[O, X]`.
- `Scalar[X]` becomes `RefScalar[O, X]`.
- Operations on refs therefore keep T and nullability.
- Applied to E11's derived facade, the stub grows to 16,163 lines. Checker time is unchanged or slightly lower.

**Owner checks.**
- `Orders.amount + Customers.credit` is a static error on all four checkers.
- Combining a child ref with a parent ref works when the child ref comes first. With the derived facade, the parent-first order gives a false positive.

### The ibis stub needs widening

`tools/gen_ref_stub.py` (129 lines) is a post-pass over E13's stub.
- `TableAPI` becomes generic in `S_co`.
- 47 `Deferred` parameter sites also accept `Ref[S_co, Any]`.
- Join methods take `right: TableAPI[R]` with typed key pairs.
- `GroupedTable.agg` accepts scalars only, which catches non-reduced columns in every spelling.

Three incidental bugs in E13's stub were fixed along the way:
- **pyright:** a union that starts with `Selector` evaluates to Unknown, because Selector's metaclass defines `__or__`. Reordering the union fixes it.
- **pyrefly:** any argument is accepted for `ir.Column`, `ir.BooleanColumn` and `ir.Table`. Retyping those parameters to `*Value` fixes it.
- **`GroupedTable.agg`** was untyped.

### Runtime, and the mypy problem

**Runtime.** A ref is `ibis._[name]`, verified on duckdb with:
- `filter`, `order_by`, `mutate`, `select`, `group_by`/`agg`, `distinct(on=)`;
- window functions;
- `coalesce`, `greatest`;
- `build(src, ...)`, `extend`;
- self-joins.

**mypy bug.** mypy infers the descriptor's owner TypeVar from the expected type of the call the ref is passed to. For a ref passed bare as an argument, this causes:
- A false positive: a bare parent ref in a generic step, e.g. `df.order_by(HasTs.ts)`.
- A missed error: a bare child ref on a parent frame. The owner is silently coerced to the parent.

Refs that are part of a larger expression (`.desc()`, `> 0`, arithmetic) are fine. Workarounds: bind the ref to a local variable, or write `.asc()`. A mypy plugin might fix it; this was not tested.

## 3. String keys

**(a) `tacit gen`** (`tools/tacit_gen.py`, 116 lines) writes a `schemas.pyi` with `Literal` overloads per schema, for `df.c["amount"]` and `Orders.col("amount")`.
- It reads fields from the runtime classes, so inheritance works without extra effort.
- Results: 10/10 for `df.c["x"]` and 9/9 for `Orders.col(...)` on all four checkers.
- The error messages are poor. pyright points at the last overload's literal, mypy says "No overload variant", and pyrefly says "Cannot index".

**(b) Frame-level `df["x"]`.**
- Deriving it through a protocol fails on every checker (1/6), because protocol matching binds the first overload.
- What does work is self-typed overloads on the frame class. But those must be generated into tacit's own stub per project, at a cost of schemas × columns overloads.

Checker time at 100 schemas × 30 columns:

| Overloads placed on | pyright | mypy | ty | pyrefly |
|---|---|---|---|---|
| one frame class | 25 s | 66 s | 4.5 s | 5 s |
| each schema class | 7.5 s | 3.7 s | 0.6 s | 1.5 s |

**(c) TypedDict variants.**

| Variant | Result |
|---|---|
| The schema *is* a TypedDict | Typos, nullability and generics are checked on all four. But there are no classmethods and no refs, and matching is structural, so any look-alike TypedDict is accepted. |
| `class Orders(Schema[OrdersCols])` | Breaks on inheritance. |
| Linking through a protocol property | ty returns Unknown, and it still needs a mirror TypedDict for every schema. |
| Generic `**kw: Unpack[TD]` | Rejected by all four. |
| PEP 764 | Not supported. |
| PEP 728 `closed=True` | Breaks subtyping. |

## 4. Matrix

Cells read pyright / mypy / ty / pyrefly. `Y` means the error is caught (or there is no false positive); `N` means it is missed.

| Property | `df.c.x` | `Orders.x` refs | `df.c["x"]` (gen) | TypedDict schema | `_.x` |
|---|---|---|---|---|---|
| Typo | YYYY | YYYY | YYYY | YYYY | NNNN |
| Wrong method / value type | YYYY | YYYY | YYYY | YYYY | NNNN |
| Nullable into non-null | YYYY | YYYY | YYYY | YYYY | NNNN |
| Column taken from another frame | NNNN | **YYYY** | NNNN | NNNN | NNNN |
| Wrong-owner bare ref in a frame method | n/a | YNYY (mypy bug) | n/a | n/a | n/a |
| Join-key value types | YYYY | NNNN | YYYY | – | YNNN |
| Non-reduced column in agg | YYYY | YYYY | YYYY | – | NNNN |
| Forgot conform | YYYY | YYYY | YYYY | – | n/a |
| Owner checked in `build`/`extend` kwargs | n/a | NNNN (inexpressible) | n/a | – | – |
| Owner checked after `mutate`/`join` | n/a | NNNN | n/a | – | – |
| Class access sound (fixes E8 §6) | no | **YYYY** | – | – | – |
| Code generation needed | none | library-side only | `tacit gen` | mirror TypedDict | none |
| Bug matrix (8 planted bugs) | 7/8 on all four | 7/8 on all four | 7/8 on all four | – | 1/0/0/0 |
| False positives on examples | 0 | 0 | 0 | – | 0 |

The interop false positives are tacit's own and fixable: `Orders.amount + tr.lit(1.0)` and `tr.cases(...)` with refs need Ref overloads.

## 5. Ergonomics

The same three steps were written in each spelling: filter + derive, join + aggregate, and a generic `latest_per_key`. Counts are non-whitespace characters.

| | `df.c.x` | `Schema.x` | `df.c["x"]` | `_.x` |
|---|---|---|---|---|
| 3-step body | 431 | 453 | 461 | 314 |

The refs spelling looks like this:

```python
kept = orders.filter(RawOrder.status != "cancelled")
Order.extend(kept, NetAmount.build(kept, net_amount=RawOrder.amount - RawOrder.discount.fill_null(0)))
j = orders.join(customers, [(Order.customer_id, RawCustomer.customer_id)])   # key pair: (left, right)
df.filter(tr.row_number().over(group_by=Keyed.customer_id, order_by=Keyed.order_ts.desc()) == 0)
```

**Pitfalls, all verified at runtime:**
1. **A join predicate mixing owners is silently a cross join.** In `o.join(c, Orders.customer_id == Customers.customer_id)`, ibis resolves both sides of a Deferred predicate on the left table. The checkers reject this statically, because the predicate has two owners. Use key pairs instead.
2. **Self-joins work with key pairs**, but refs cannot reach collided `*_right` columns.
3. **Owner checks stop at intermediate tables.** At runtime refs resolve by name.
4. **`build` and `extend` need the source frame explicitly.** The owner is checked only at runtime.
5. **Refs don't mix with bound columns** (`Orders.x + o.c.y`). This is a policy choice; it works at runtime.

## Recommendation (E14)

- **Keep `df.c.x` as the primary spelling.**
  - Bound columns stay exact to their relation, which matters for joins, self-joins and `build`.
  - It is clean on mypy.
- **Add owner-typed schema refs (`Orders.amount`) as the typed `_`.** They are:
  - the only spelling that catches "column from the wrong frame";
  - the fix for the unsound class-level access found in E8;
  - the most natural spelling for generic steps and sort/group keys.
  - They need no user-side codegen. The cost is a generated Ref twin of the facade, which roughly doubles its size, plus a ~40-line stub post-pass.
- **Don't build** a free `col("x")`, TypedDict schemas, or frame-level `df["x"]`.
- **Offer `df.c["x"]` only if string keys are really wanted.** It needs `tacit gen`, and the errors are poor.
- **Worth probing next:** owner-typed bound columns (`df.c.amount: Col[Orders, float]`), which would give `.c` the wrong-frame check as well.
