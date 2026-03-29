# ibis Research Logbook

Research diary for understanding ibis.Table internals and how tacit.DataFrame[S] can work with it.

---

## 2026-03-29: Feasibility Spike Results

### Can ibis.Table be subclassed?

**Yes.** Subclassing works cleanly:

```python
class DataFrame(ir.Table, typing.Generic[S]):
    __slots__ = ('_tacit_schema',)
```

Key findings:

1. **Subclass creation** works. MRO is `DataFrame -> Table -> Expr -> Immutable -> ...`
2. **Instantiation from existing Table** works: `DataFrame(existing_table.op())`
3. **`isinstance` checks pass**: `isinstance(df, ir.Table)` returns `True`
4. **Column access** works: `df.sepal_length` returns the ibis column expression
5. **`execute()`** works on the subclass
6. **`repr()`** works (shows the expression tree)
7. **`equals()`** works across types: `subclass.equals(plain_table)` is `True`
8. **Hash** works but differs from plain Table (different `type()`)

### Do ibis operations preserve the subclass type?

**No, and this is correct by design.** Every ibis Table method (`mutate`, `filter`,
`select`, etc.) returns a plain `ibis.Table`. This happens because `ops.Relation.to_expr()`
hardcodes `Table(self)`:

```python
# ibis/expr/operations/relations.py
def to_expr(self):
    from ibis.expr.types import Table
    return Table(self)
```

This aligns with DESIGN.md's intent: "the first ibis operation drops back to plain
ibis.Table." Re-entering typed-world requires explicit `parse()`, `cast()`, or
`@tacit.contract`.

### How many methods return Table?

- 35 methods have `Table` return annotations resolved via `get_type_hints`
- 52 methods mention `Table` in their raw return annotations (including `ir.Table`
  string refs and join methods)
- Notable: `group_by` returns `GroupedTable`, `window_by` returns `WindowedTable`

### Could we auto-rewrap?

Three approaches were tested for automatically re-wrapping method results:

1. **Manual method overrides** (`ibis_construction_test.py`) -- works but doesn't scale
2. **`__getattr__` interception** -- doesn't work because `Table.__getattr__` handles
   column access; our override would break `df.column_name`
3. **Dynamic method generation** (`ibis_metaclass_rewrap_test.py`) -- partially works
   but fragile; some methods error because intermediate `Table` objects created during
   the method lack `_schema_type`

**Verdict: auto-rewrap is not needed.** The design explicitly says operations should
drop to plain Table. Don't fight it.

### `__class_getitem__` for `DataFrame[S]`

`ir.Table` does NOT have `__class_getitem__`. Two approaches work:

1. **Custom `__class_getitem__`** returning `typing._GenericAlias(cls, (schema_type,))`
2. **`typing.Generic[S]` mixin**: `class DataFrame(ir.Table, Generic[S])`

Approach 2 is cleaner for type checkers. Both are compatible with `get_type_hints()`
on functions annotated with `DataFrame[MySchema]`.

### Immutable base class

`ir.Table` inherits from `Immutable`, which blocks `__setattr__`. Setting
`_tacit_schema` requires `object.__setattr__(df, '_tacit_schema', schema_type)`.
This works reliably. The slot must be declared in `__slots__`.

### `__reduce__` / pickling

`__reduce__` returns `(DataFrame, (op_node,))` which does NOT preserve `_tacit_schema`.
Would need override if serialization is needed (not a v0 concern).

### Wrapper approach (tested, rejected)

A composition-based wrapper (`DataFrameWrapper`) was tested. Downsides:

- `isinstance(wrapper, ir.Table)` returns `False` -- can't fix without hacks
- `__getattr__` delegation is fragile with column access
- Methods accepting Table args (e.g., `join`) won't accept the wrapper
- Type checkers don't know about Table methods on the wrapper
- Breaks any code that does `type(x)` checks
- ABC `register()` doesn't work (Table doesn't use ABCMeta)

**Verdict: subclass is clearly superior.** The wrapper only makes sense if subclassing
breaks on future ibis versions, which seems unlikely given how stable the Expr hierarchy is.

### Recommended implementation

```python
S = TypeVar('S')

class DataFrame(ir.Table, Generic[S]):
    __slots__ = ('_tacit_schema',)

    @classmethod
    def _from_table(cls, table: ir.Table, schema_type=None):
        df = cls(table.op())
        object.__setattr__(df, '_tacit_schema', schema_type)
        return df
```

This is the minimal viable `DataFrame[S]`. It:
- IS an ibis Table (subclass)
- Carries schema type as metadata
- Passes `isinstance(df, ir.Table)` checks
- Supports `DataFrame[MySchema]` type annotations
- Works with pandera validation
- Drops to plain Table on any ibis operation (correct by design)

## 2026-03-29: Static Typing Verification (pyright)

Ran pyright against `type_check_test.py`. Results confirm all three design goals:

### Goal 3: Can't forget parse()/cast()

```
# return raw ibis.Table where DataFrame[IrisFeatures] expected:
error: Type "Table" is not assignable to return type "DataFrame[IrisFeatures]"

# return DataFrame[Iris] where DataFrame[IrisFeatures] expected:
error: "DataFrame[Iris]" is not assignable to "DataFrame[IrisFeatures]"
  Type parameter "S@DataFrame" is invariant
```

The generic parameter `S` is **invariant** by default in Python's type system.
This means `DataFrame[Iris]` and `DataFrame[IrisFeatures]` are completely distinct
types — even though `IrisFeatures` inherits from `Iris`. This is exactly right:
the contract says "this data conforms to IrisFeatures", and Iris data doesn't.

### Goal 2: Transparent usage

`DataFrame[S]` is accepted wherever `ibis.Table` is expected — subclass relationship
works cleanly. No `unwrap()` needed.

### Goal 1: Type annotations carry schema info

`get_type_hints()` correctly extracts `DataFrame[Iris]` and `DataFrame[IrisFeatures]`
from function signatures, with `__origin__` = `DataFrame` and `__args__` = `(Iris,)`.
This is what `@tacit.contract` will use at runtime.

### Noise: ibis stubs incomplete

pyright flagged ibis-internal issues (Column division operator, mutate kwargs) that
are ibis type stub gaps, not related to our approach. These work at runtime.
