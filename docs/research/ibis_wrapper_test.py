"""Experiment: Wrapper (composition) approach for tacit.DataFrame

If subclassing proves too fragile, can we use a wrapper that delegates to
an inner ibis.Table via __getattr__?
"""
import ibis
import ibis.expr.types as ir
from typing import TypeVar, Generic


S = TypeVar("S")


class DataFrameWrapper(Generic[S]):
    """A wrapper around ibis.Table that carries schema type info."""

    def __init__(self, table: ir.Table, schema_type=None):
        object.__setattr__(self, '_table', table)
        object.__setattr__(self, '_schema_type', schema_type)

    def __getattr__(self, name):
        result = getattr(self._table, name)
        # If the result is a Table, re-wrap it
        if isinstance(result, ir.Table):
            return DataFrameWrapper(result, self._schema_type)
        # If it's a callable that might return a Table, wrap the return
        if callable(result):
            def wrapper(*args, **kwargs):
                ret = result(*args, **kwargs)
                if isinstance(ret, ir.Table):
                    return DataFrameWrapper(ret, self._schema_type)
                return ret
            return wrapper
        return result

    def __repr__(self):
        schema_str = f"[{self._schema_type.__name__}]" if self._schema_type else ""
        return f"DataFrame{schema_str}:\n{repr(self._table)}"

    # --- Check isinstance compatibility ---


print("=" * 60)
print("1. Wrapper basic tests")
print("=" * 60)

con = ibis.duckdb.connect()
t = con.create_table("test", {"a": [1, 2, 3], "b": ["x", "y", "z"]})

class MySchema:
    pass

w = DataFrameWrapper(t, schema_type=MySchema)
print(f"  type(w): {type(w)}")
print(f"  isinstance(w, ir.Table): {isinstance(w, ir.Table)}")
print(f"  columns: {w.columns}")

# Chaining
result = w.mutate(c=w._table.a + 1).filter(w._table.a > 1)
print(f"  Chained type: {type(result)}")
print(f"  Chained._schema_type: {result._schema_type}")

# Problem: w.a returns a wrapped column accessor? Let's see
print()
print("=" * 60)
print("2. Column access via wrapper")
print("=" * 60)

col = w.a
print(f"  w.a type: {type(col)}")
# This might be a Column wrapped in the wrapper's __getattr__
# Since Column is not a Table, it should pass through

# Can we do w.mutate(c=w.a + 1)?
try:
    r = w.mutate(c=w.a + 1)
    print(f"  w.mutate(c=w.a + 1) works: {type(r)}")
    print(f"  Result: {r._table.execute()}")
except Exception as e:
    print(f"  Error: {type(e).__name__}: {e}")

# Execute
print()
print("=" * 60)
print("3. Execute from wrapper")
print("=" * 60)

try:
    result = w.execute()
    print("  execute() works: True")
    print(f"  type: {type(result)}")
    print(f"  result:\n{result}")
except Exception as e:
    print(f"  execute() error: {type(e).__name__}: {e}")


# --- isinstance check ---
print()
print("=" * 60)
print("4. Can we make isinstance(wrapper, ir.Table) work?")
print("=" * 60)

# Option A: metaclass with __instancecheck__
class DataFrameMeta(type):
    def __instancecheck__(cls, instance):
        if isinstance(instance, DataFrameWrapper):
            return True
        return super().__instancecheck__(instance)


# This would only work for our own class, not ir.Table
# We'd need to modify ir.Table's metaclass or use ABC.register

# Option B: register with ABC
try:
    # ir.Table uses AbstractMeta not ABCMeta, so register won't work
    # But let's check
    ir.Table.register(DataFrameWrapper)
    print(f"  After register: isinstance(w, ir.Table) = {isinstance(w, ir.Table)}")
except Exception as e:
    print(f"  register error: {type(e).__name__}: {e}")


print()
print("=" * 60)
print("5. Summary: Wrapper downsides")
print("=" * 60)
print("""
  - isinstance(wrapper, ir.Table) returns False (can't fix without hacks)
  - __getattr__ delegation is fragile with column access
  - Methods that accept Table args (e.g., join) won't accept the wrapper
  - Need to handle all dunder methods explicitly
  - Type checkers won't know about Table methods on the wrapper
  - Breaks any code that does type(x) checks
""")
