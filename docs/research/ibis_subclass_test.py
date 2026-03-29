"""Experiment: Can ibis.Table be subclassed?

Tests:
1. Basic subclass creation
2. Instantiation from an existing Table's op() node
3. Whether Table methods return the subclass or plain Table
4. Whether __class_getitem__ exists or can be added
"""
import ibis
import ibis.expr.types as ir
import ibis.expr.operations as ops


# --- 1. Basic subclass ---
print("=" * 60)
print("1. Can we create a basic subclass of ibis.Table?")
print("=" * 60)

class MyTable(ir.Table):
    pass

print(f"  MyTable created: {MyTable}")
print(f"  MRO: {[c.__name__ for c in MyTable.__mro__]}")


# --- 2. Instantiate from existing Table's op node ---
print()
print("=" * 60)
print("2. Can we instantiate from an existing Table's op node?")
print("=" * 60)

con = ibis.duckdb.connect()
original = con.create_table("test", {"a": [1, 2, 3], "b": ["x", "y", "z"]})
print(f"  original type: {type(original)}")
print(f"  original op type: {type(original.op())}")

my_table = MyTable(original.op())
print(f"  my_table type: {type(my_table)}")
print(f"  isinstance(my_table, ir.Table): {isinstance(my_table, ir.Table)}")
print(f"  isinstance(my_table, MyTable): {isinstance(my_table, MyTable)}")
print(f"  my_table.columns: {my_table.columns}")

# Can we execute it?
try:
    result = my_table.execute()
    print(f"  execute() works: True")
    print(f"  result:\n{result}")
except Exception as e:
    print(f"  execute() error: {e}")


# --- 3. Do Table methods preserve the subclass? ---
print()
print("=" * 60)
print("3. Do Table methods preserve the subclass type?")
print("=" * 60)

mutated = my_table.mutate(c=my_table.a + 1)
print(f"  mutate() result type: {type(mutated)}")
print(f"  Is MyTable? {isinstance(mutated, MyTable)}")

filtered = my_table.filter(my_table.a > 1)
print(f"  filter() result type: {type(filtered)}")
print(f"  Is MyTable? {isinstance(filtered, MyTable)}")

selected = my_table.select("a")
print(f"  select() result type: {type(selected)}")
print(f"  Is MyTable? {isinstance(selected, MyTable)}")

ordered = my_table.order_by("a")
print(f"  order_by() result type: {type(ordered)}")
print(f"  Is MyTable? {isinstance(ordered, MyTable)}")

limited = my_table.head(2)
print(f"  head() result type: {type(limited)}")
print(f"  Is MyTable? {isinstance(limited, MyTable)}")


# --- 4. Does __class_getitem__ exist? ---
print()
print("=" * 60)
print("4. Does Table support generic parameters (Table[SomeType])?")
print("=" * 60)

print(f"  hasattr(ir.Table, '__class_getitem__'): {hasattr(ir.Table, '__class_getitem__')}")

# Python 3.12+ allows __class_getitem__ by default on all classes
try:
    result = ir.Table[int]
    print(f"  ir.Table[int] = {result}")
except Exception as e:
    print(f"  ir.Table[int] error: {type(e).__name__}: {e}")

try:
    result = MyTable[int]
    print(f"  MyTable[int] = {result}")
except Exception as e:
    print(f"  MyTable[int] error: {type(e).__name__}: {e}")


# --- 5. Can we add __class_getitem__ to our subclass? ---
print()
print("=" * 60)
print("5. Can we add __class_getitem__ to our subclass?")
print("=" * 60)

class SchemaType:
    """Dummy schema type for testing."""
    pass

class TypedTable(ir.Table):
    _schema_type = None

    def __class_getitem__(cls, schema_type):
        # Create a new class parameterized by the schema type
        ns = {"_schema_type": schema_type}
        new_cls = type(f"{cls.__name__}[{schema_type.__name__}]", (cls,), ns)
        return new_cls

try:
    Parameterized = TypedTable[SchemaType]
    print(f"  TypedTable[SchemaType] = {Parameterized}")
    print(f"  Parameterized._schema_type = {Parameterized._schema_type}")

    # Can we instantiate it?
    p_instance = Parameterized(original.op())
    print(f"  instance type: {type(p_instance)}")
    print(f"  isinstance(p_instance, ir.Table): {isinstance(p_instance, ir.Table)}")
    print(f"  isinstance(p_instance, TypedTable): {isinstance(p_instance, TypedTable)}")
    print(f"  _schema_type: {p_instance._schema_type}")

    # Does execute work?
    result = p_instance.execute()
    print(f"  execute() works: True")
except Exception as e:
    import traceback
    print(f"  Error: {type(e).__name__}: {e}")
    traceback.print_exc()


# --- 6. Alternative: __class_getitem__ that returns the same class ---
print()
print("=" * 60)
print("6. __class_getitem__ that stores type but returns same class")
print("=" * 60)

class DataFrame(ir.Table):
    """Tacit DataFrame - a typed wrapper around ibis.Table."""
    _schema_type = None

    def __class_getitem__(cls, schema_type):
        # Just return a typing construct, don't create real class
        # This is the standard Generic pattern
        import typing
        return typing._GenericAlias(cls, (schema_type,))

try:
    from typing import Generic, TypeVar
    AliasResult = DataFrame[SchemaType]
    print(f"  DataFrame[SchemaType] = {AliasResult}")
    print(f"  type = {type(AliasResult)}")
    # Can we instantiate it?
    try:
        instance = AliasResult(original.op())
        print(f"  Instantiation works: {type(instance)}")
    except Exception as e2:
        print(f"  Instantiation error: {type(e2).__name__}: {e2}")
except Exception as e:
    import traceback
    print(f"  Error: {type(e).__name__}: {e}")
    traceback.print_exc()
