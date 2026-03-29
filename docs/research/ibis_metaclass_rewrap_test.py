"""Experiment: Clean metaclass/decorator approach for auto-rewrapping.

The goal: a DataFrame subclass of ir.Table where ALL Table-returning methods
automatically return DataFrame instead of Table, without manually overriding
each one.
"""
import ibis
import ibis.expr.types as ir
import ibis.expr.operations as ops
import inspect
import functools
from typing import TypeVar, get_type_hints


# --- Strategy: Use __init_subclass__ to auto-wrap methods ---

def _find_table_returning_methods():
    """Find all Table methods that return Table."""
    methods = []
    for name in dir(ir.Table):
        if name.startswith('_'):
            continue
        attr = getattr(ir.Table, name, None)
        if not callable(attr) or not isinstance(attr, type(ir.Table.mutate)):
            continue
        try:
            hints = get_type_hints(attr)
        except Exception:
            continue
        ret = hints.get('return')
        if ret is ir.Table or (isinstance(ret, type) and issubclass(ret, ir.Table)):
            methods.append(name)
        elif isinstance(ret, str) and ret == 'Table':
            methods.append(name)
    return methods


TABLE_RETURNING = _find_table_returning_methods()
print(f"Found {len(TABLE_RETURNING)} Table-returning methods")


class DataFrameBase(ir.Table):
    """
    Subclass of ibis.Table that auto-rewraps Table-returning methods.

    The key trick: we override each method at class-creation time with a
    version that calls super(), then wraps the result back into our type.
    """
    __slots__ = ("_schema_type",)

    def __init__(self, arg, schema_type=None):
        super().__init__(arg)
        object.__setattr__(self, '_schema_type', schema_type)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Auto-wrap all Table-returning methods for each subclass
        _auto_wrap_methods(cls)

    def _rewrap(self, table):
        """Re-wrap a plain Table result back into this DataFrame type."""
        if isinstance(table, type(self)):
            return table
        return type(self)(table.op(), schema_type=self._schema_type)

    @classmethod
    def __class_getitem__(cls, schema_type):
        """Support DataFrame[MySchema] syntax for type annotations."""
        import typing
        return typing._GenericAlias(cls, (schema_type,))

    @classmethod
    def from_table(cls, table: ir.Table, schema_type=None):
        """Create a DataFrame from an existing ibis Table."""
        return cls(table.op(), schema_type=schema_type)


def _auto_wrap_methods(cls):
    """Add re-wrapping overrides for all Table-returning methods."""
    for method_name in TABLE_RETURNING:
        if method_name in cls.__dict__:
            # Don't override explicitly defined methods
            continue
        original = getattr(ir.Table, method_name)

        @functools.wraps(original)
        def make_wrapper(name):
            def wrapper(self, *args, **kwargs):
                result = getattr(ir.Table, name)(self, *args, **kwargs)
                if isinstance(result, ir.Table) and not isinstance(result, type(self)):
                    return self._rewrap(result)
                return result
            return wrapper

        setattr(cls, method_name, make_wrapper(method_name))


# Apply auto-wrapping to DataFrameBase itself
_auto_wrap_methods(DataFrameBase)


# --- Test it ---
print()
print("=" * 60)
print("1. Basic functionality")
print("=" * 60)

con = ibis.duckdb.connect()
t = con.create_table("test", {"a": [1, 2, 3], "b": ["x", "y", "z"]})

df = DataFrameBase.from_table(t, schema_type="TestSchema")
print(f"  type: {type(df)}")
print(f"  isinstance(df, ir.Table): {isinstance(df, ir.Table)}")
print(f"  schema_type: {df._schema_type}")

# Test all common operations
print()
print("=" * 60)
print("2. Method type preservation")
print("=" * 60)

tests = [
    ("mutate", lambda d: d.mutate(c=d.a + 1)),
    ("filter", lambda d: d.filter(d.a > 1)),
    ("select", lambda d: d.select("a")),
    ("order_by", lambda d: d.order_by("a")),
    ("head", lambda d: d.head(2)),
    ("drop", lambda d: d.drop("b")),
    ("distinct", lambda d: d.distinct()),
    ("limit", lambda d: d.limit(2)),
    ("rename", lambda d: d.rename(aa="a")),
]

all_pass = True
for name, fn in tests:
    try:
        result = fn(df)
        is_df = isinstance(result, DataFrameBase)
        has_schema = result._schema_type == "TestSchema"
        status = "PASS" if (is_df and has_schema) else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f"  {name:15s}: {status} (type={type(result).__name__}, schema={result._schema_type})")
    except Exception as e:
        all_pass = False
        print(f"  {name:15s}: ERROR ({type(e).__name__}: {e})")

print(f"\n  All pass: {all_pass}")


# --- 3. Chaining ---
print()
print("=" * 60)
print("3. Complex chaining")
print("=" * 60)

chain = (
    df
    .mutate(c=df.a * 2)
    .filter(df.a > 1)
    .select("a", "c")
    .order_by("a")
    .head(5)
)
print(f"  Chain result type: {type(chain).__name__}")
print(f"  Chain schema: {chain._schema_type}")
print(f"  Chain isinstance(ir.Table): {isinstance(chain, ir.Table)}")
result = chain.execute()
print(f"  Chain executed:\n{result}")


# --- 4. join test ---
print()
print("=" * 60)
print("4. Join test")
print("=" * 60)

t2 = con.create_table("test2", {"a": [1, 2, 3], "c": [10, 20, 30]})
df2 = DataFrameBase.from_table(t2, schema_type="Schema2")

try:
    joined = df.join(df2, "a")
    print(f"  join type: {type(joined).__name__}")
    print(f"  join isinstance(DataFrameBase): {isinstance(joined, DataFrameBase)}")
    # Note: join might return a Join expr, which is a Table subclass
    print(f"  join isinstance(ir.Table): {isinstance(joined, ir.Table)}")
    r = joined.execute()
    print(f"  join executed:\n{r}")
except Exception as e:
    import traceback
    print(f"  join error: {type(e).__name__}: {e}")
    traceback.print_exc()


# --- 5. __class_getitem__ for type annotations ---
print()
print("=" * 60)
print("5. Generic parameter support")
print("=" * 60)

class MySchema:
    a: int
    b: str

alias = DataFrameBase[MySchema]
print(f"  DataFrameBase[MySchema] = {alias}")
print(f"  type = {type(alias)}")

# Can we instantiate from the alias?
try:
    instance = alias(t.op(), schema_type=MySchema)
    print(f"  Instantiation from alias: {type(instance)}")
    print(f"  Schema type: {instance._schema_type}")
except Exception as e:
    print(f"  Instantiation error: {type(e).__name__}: {e}")


# --- 6. __reduce__ / pickling ---
print()
print("=" * 60)
print("6. Serialization (__reduce__)")
print("=" * 60)

print(f"  df.__reduce__() = {df.__reduce__()}")
# The parent __reduce__ returns (self.__class__, (self._arg,))
# This doesn't preserve _schema_type. We'd need to override.


# --- 7. Additional slot on Immutable ---
print()
print("=" * 60)
print("7. Immutable + extra slots")
print("=" * 60)

# The Immutable base class blocks __setattr__. We use object.__setattr__.
# But __slots__ needs to be declared properly.
print(f"  DataFrameBase.__slots__ = {DataFrameBase.__slots__}")
print(f"  ir.Table.__slots__ = {ir.Table.__slots__}")
print(f"  Expr.__slots__ = {ir.Table.__mro__[2].__slots__}")  # Expr
print(f"  Immutable.__slots__ = {ir.Table.__mro__[3].__slots__}")  # Immutable

# Does the slot actually work?
print(f"  df._schema_type = {df._schema_type}")
# Can we set it via object.__setattr__?
object.__setattr__(df, '_schema_type', 'NewSchema')
print(f"  After object.__setattr__: {df._schema_type}")
