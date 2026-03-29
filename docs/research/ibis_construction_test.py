"""Experiment: How are ibis Tables constructed?

Focus on:
1. How read_csv / create_table builds a Table
2. How mutate/filter/select build result Tables
3. Where exactly is Table() called — in ops.Relation.to_expr()
4. Can we intercept/override to_expr() to return our subclass?
5. What about a "re-wrap" pattern — method returns plain Table, we wrap it back
"""
import ibis
import ibis.expr.types as ir
import ibis.expr.operations as ops
import functools


# --- 1. How Tables are built internally ---
print("=" * 60)
print("1. Table construction: from backend operations")
print("=" * 60)

con = ibis.duckdb.connect()
t = con.create_table("test", {"a": [1, 2, 3], "b": ["x", "y", "z"]})
print(f"  create_table returns: {type(t)}")
print(f"  t.op() = {type(t.op())}")
print(f"  t.op().__class__.__name__ = {t.op().__class__.__name__}")

# How does mutate work internally?
m = t.mutate(c=t.a + 1)
print(f"\n  mutate result type: {type(m)}")
print(f"  mutate op type: {type(m.op())}")
print(f"  mutate op class: {m.op().__class__.__name__}")

# The chain: mutate -> ops.Project(self, values) -> Project.to_expr() -> Table(self)
# Project inherits from Relation, which has to_expr() -> Table(self)


# --- 2. Re-wrap pattern: wrap plain Table back into our type ---
print()
print("=" * 60)
print("2. Re-wrap pattern")
print("=" * 60)

class DataFrame(ir.Table):
    """A typed DataFrame wrapping ibis.Table."""
    _schema_type = None

    def __class_getitem__(cls, schema_type):
        """Support DataFrame[MySchema] syntax."""
        import typing
        return typing._GenericAlias(cls, (schema_type,))

    def _rewrap(self, table: ir.Table) -> "DataFrame":
        """Re-wrap a plain Table into a DataFrame, preserving schema type."""
        df = DataFrame(table.op())
        # We need to bypass Immutable.__setattr__
        object.__setattr__(df, '_schema_type', self._schema_type)
        return df

    def mutate(self, *args, **kwargs):
        result = super().mutate(*args, **kwargs)
        return self._rewrap(result)

    def filter(self, *args, **kwargs):
        result = super().filter(*args, **kwargs)
        return self._rewrap(result)

    def select(self, *args, **kwargs):
        result = super().select(*args, **kwargs)
        return self._rewrap(result)

    def order_by(self, *args, **kwargs):
        result = super().order_by(*args, **kwargs)
        return self._rewrap(result)

    def head(self, *args, **kwargs):
        result = super().head(*args, **kwargs)
        return self._rewrap(result)


# Test the re-wrap pattern
df = DataFrame(t.op())
object.__setattr__(df, '_schema_type', 'TestSchema')
print(f"  df type: {type(df)}")
print(f"  df._schema_type: {df._schema_type}")

m2 = df.mutate(c=df.a + 1)
print(f"  mutate type: {type(m2)}")
print(f"  mutate._schema_type: {m2._schema_type}")
print(f"  isinstance(m2, DataFrame): {isinstance(m2, DataFrame)}")

f2 = df.filter(df.a > 1)
print(f"  filter type: {type(f2)}")
print(f"  filter._schema_type: {f2._schema_type}")

s2 = df.select("a")
print(f"  select type: {type(s2)}")

o2 = df.order_by("a")
print(f"  order_by type: {type(o2)}")

h2 = df.head(2)
print(f"  head type: {type(h2)}")

# Can we chain?
chained = df.mutate(c=df.a + 1).filter(df.a > 1)
print(f"\n  Chained mutate+filter type: {type(chained)}")
print(f"  Chained._schema_type: {chained._schema_type}")

# Does execute still work?
result = chained.execute()
print(f"  Execute works: True")
print(f"  Result:\n{result}")


# --- 3. __getattr__-based auto-rewrap ---
print()
print("=" * 60)
print("3. __getattr__-based auto-rewrap (more maintainable)")
print("=" * 60)

TABLE_METHODS_RETURNING_TABLE = {
    'mutate', 'filter', 'select', 'order_by', 'head', 'limit',
    'drop', 'rename', 'relocate', 'distinct', 'dropna', 'fillna',
    'sample', 'unorder', 'group_by', 'aggregate', 'join',
    'inner_join', 'left_join', 'right_join', 'outer_join',
    'cross_join', 'anti_join', 'semi_join', 'union',
    'intersect', 'difference',
}


class DataFrame2(ir.Table):
    """Auto-rewrapping DataFrame."""
    __slots__ = ("_schema_type_val",)

    def __init__(self, arg, schema_type=None):
        super().__init__(arg)
        object.__setattr__(self, '_schema_type_val', schema_type)

    @classmethod
    def __class_getitem__(cls, schema_type):
        import typing
        return typing._GenericAlias(cls, (schema_type,))

    def _rewrap(self, table):
        return DataFrame2(table.op(), schema_type=self._schema_type_val)

    pass
    # NOTE: __getattr__ approach won't work because Table uses __getattr__
    # itself for column access (table.column_name). Overriding __getattr__
    # would break column access.


# Actually, since Table methods are defined on the class, __getattr__ won't be
# called for them. We need a different approach.

# Let's test that __getattr__ ISN'T called for existing methods:
df2 = DataFrame2(t.op(), schema_type="TestSchema")
print(f"  df2 type: {type(df2)}")
print(f"  df2._schema_type_val: {df2._schema_type_val}")

# mutate is a method on Table, so __getattr__ won't intercept it
m3 = df2.mutate(c=df2.a + 1)
print(f"  mutate result type: {type(m3)}")
print(f"  Is DataFrame2? {isinstance(m3, DataFrame2)}")
# ^ This will be False because mutate calls ops.Project(...).to_expr() which returns Table


# --- 4. Can we use __init_subclass__ to auto-wrap? ---
print()
print("=" * 60)
print("4. Counting how many Table methods return Table")
print("=" * 60)

import inspect
table_methods = []
for name, method in inspect.getmembers(ir.Table, predicate=inspect.isfunction):
    if name.startswith('_'):
        continue
    sig = inspect.signature(method)
    ret = sig.return_annotation
    if ret is ir.Table or (isinstance(ret, str) and ret == 'Table'):
        table_methods.append(name)

print(f"  Methods with Table return annotation: {len(table_methods)}")
for m in sorted(table_methods):
    print(f"    - {m}")


# --- 5. Metaclass/decorator approach to auto-wrap all Table-returning methods ---
print()
print("=" * 60)
print("5. Decorator approach to auto-rewrap")
print("=" * 60)


def _make_rewrapper(method_name):
    """Create a wrapper that calls super and re-wraps the result."""
    def wrapper(self, *args, **kwargs):
        result = getattr(ir.Table, method_name)(self, *args, **kwargs)
        if isinstance(result, ir.Table) and not isinstance(result, DataFrame3):
            return DataFrame3(result.op(), schema_type=self._schema_type_val)
        return result
    wrapper.__name__ = method_name
    wrapper.__qualname__ = f"DataFrame3.{method_name}"
    return wrapper


class DataFrame3(ir.Table):
    """Auto-rewrapping DataFrame using generated method overrides."""
    __slots__ = ("_schema_type_val",)

    def __init__(self, arg, schema_type=None):
        super().__init__(arg)
        object.__setattr__(self, '_schema_type_val', schema_type)

    @classmethod
    def __class_getitem__(cls, schema_type):
        import typing
        return typing._GenericAlias(cls, (schema_type,))


# Dynamically add wrappers for all Table-returning methods
for method_name in table_methods:
    setattr(DataFrame3, method_name, _make_rewrapper(method_name))


df3 = DataFrame3(t.op(), schema_type="TestSchema")
print(f"  df3 type: {type(df3)}")
print(f"  df3._schema_type_val: {df3._schema_type_val}")

m4 = df3.mutate(c=df3.a + 1)
print(f"  mutate type: {type(m4)}")
print(f"  Is DataFrame3? {isinstance(m4, DataFrame3)}")
print(f"  schema preserved? {m4._schema_type_val}")

f4 = df3.filter(df3.a > 1)
print(f"  filter type: {type(f4)}")
print(f"  Is DataFrame3? {isinstance(f4, DataFrame3)}")

# Chain
chained3 = df3.mutate(c=df3.a + 1).filter(df3.a > 1).select("a", "c")
print(f"  Chained type: {type(chained3)}")
print(f"  Chained schema: {chained3._schema_type_val}")

# Execute
result3 = chained3.execute()
print(f"  Execute works: True")
print(f"  Result:\n{result3}")


# --- 6. How many methods need wrapping? ---
print()
print("=" * 60)
print("6. Methods that actually return Table (runtime check)")
print("=" * 60)

# Let's also check methods not in annotations but that return tables
all_table_like_methods = set()
for name in dir(ir.Table):
    if name.startswith('_'):
        continue
    attr = getattr(ir.Table, name, None)
    if callable(attr) and hasattr(attr, '__annotations__'):
        ret = attr.__annotations__.get('return', None)
        if ret is not None and 'Table' in str(ret):
            all_table_like_methods.add(name)

print(f"  All methods mentioning Table in return: {len(all_table_like_methods)}")
for m in sorted(all_table_like_methods):
    print(f"    - {m}")
