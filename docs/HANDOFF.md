# Handoff: Feasibility Spike

Next step is determining how `tacit.DataFrame[S]` works at runtime. This
document captures context from the design session that isn't in DESIGN.md
or the README but matters for implementation.

## The core question

Can `tacit.DataFrame[S]` be a subclass of `ibis.expr.types.Table`?

If yes: users get the full ibis API for free, no proxying needed.
If no: fall back to a thin wrapper with `__getattr__` delegation.

Either way, the user-facing API (`Schema.parse()`, `Schema.cast()`,
`@tacit.contract`) stays the same. This spike determines internals only.

## What to investigate

### ibis.Table construction

`ibis.expr.types.Table` is an expression node in a lazy computation graph,
not a data container. It's constructed by ibis internals (backends, expression
builders), not by user code. Key questions:

- What does `Table.__init__` actually take? Is it just an ibis `ops.Node`?
- Can we construct a subclass instance from an existing Table? (e.g.,
  `DataFrame.__init__(existing_table._arg)` or similar)
- Does ibis use `__class__` checks or `type()` checks that would break
  with subclasses?
- Does `Table.__repr__`, `Table._repr_html_` (notebook display) work on
  subclasses?

### Method return types

Every ibis Table method (`.mutate()`, `.filter()`, `.select()`, `.join()`,
etc.) returns a new `Table` instance. This is expected and acceptable — we
WANT the first operation to drop back to plain `ibis.Table`. The schema is
"consumed" and must be re-established via `parse()` or `cast()`.

But verify: do these methods hardcode `Table(...)` in their return, or do
they go through a factory that might respect subclasses? (Probably the
former, which is fine.)

### Generic parameter `[S]`

`DataFrame[S]` needs `__class_getitem__` to be parameterizable. `ibis.Table`
may already have this (many ibis types do). If not, our subclass adds it.
The `S` parameter is for static analysis only — at runtime it's stored as
metadata (e.g., `self._tacit_schema = S`).

### Alternative: `__init_subclass__` on Table

If direct subclassing is messy, another pattern: don't subclass at all.
Instead, `DataFrame[S]` is a distinct class that wraps a Table and
delegates via `__getattr__`. Trade-offs:

- Pro: clean separation, no dependency on ibis internals
- Con: `isinstance(df, ibis.Table)` returns False, which may break
  pandera's ibis backend (it likely checks `isinstance` to detect the
  backend)
- Con: need to maintain delegation as ibis API evolves

### pandera's ibis backend

pandera detects ibis Tables and routes to its ibis validation backend. Key
questions:

- Does pandera check `isinstance(obj, ibis.Table)`? If so, a subclass
  works but a wrapper doesn't (without `__instancecheck__` tricks).
- What does `pandera.DataFrameModel.validate(ibis_table)` actually return?
  The same Table object? A new one? This affects how `parse()` wraps the
  result.
- Can we pass pandera a schema we constructed programmatically (from our
  `Schema` class fields) rather than requiring a `DataFrameModel` subclass?
  This would let us own the schema definition and use pandera purely as the
  validation engine.

### Type checker behavior

The whole point of `DataFrame[S]` being a distinct type is that the type
checker enforces contracts. Verify with pyright:

- Does `def f() -> DataFrame[Iris]: return ibis_table` produce a type error?
  (It should, if DataFrame is not a type alias for Table.)
- Does `df: DataFrame[Iris] = Iris.parse(table)` work?
- Does `df.sepal_length` autocomplete in the editor? (Probably not without
  a plugin, but worth checking what pyright infers from `__getattr__`.)

## Key files to read

In ibis source (installed in `.venv/`):

- `ibis/expr/types/relations.py` — the `Table` class definition
- `ibis/expr/types/core.py` — base `Expr` class that `Table` inherits from
- `ibis/backends/duckdb/__init__.py` — how `read_csv()` constructs a Table
- `ibis/expr/operations/relations.py` — the `ops.Node` types that Table wraps

In pandera source (installed in `.venv/`):

- `pandera/api/ibis/` — the ibis backend (if it exists as a directory)
- `pandera/backends/ibis/` — validation implementation for ibis
- Search for `isinstance.*Table` to find how pandera detects ibis objects

## Current state of the codebase

- `src/tacit/tacit.py` — old scaffold, uses `pandera.polars`. Needs full rewrite.
- `pyproject.toml` — lists `polars` and `pandera` as deps. Needs `polars` replaced
  with `ibis-framework[duckdb]`.
- `examples/iris_pipeline.py`, `examples/tpch_q1.py` — target API, not runnable yet.
- `examples/iris.py`, `examples/iris_doc.py` — old scratch files using polars. Can
  be deleted.

## Decision from design session

If subclassing doesn't work cleanly, don't force it. The wrapper approach is
fine — the user-facing API is identical. The only difference is whether
`isinstance(df, ibis.Table)` returns True, which matters mainly for pandera
integration. If the wrapper breaks pandera, subclassing becomes a harder
requirement.

The worst outcome is a brittle subclass that breaks on ibis version upgrades.
Prefer a clean wrapper over a fragile subclass.
