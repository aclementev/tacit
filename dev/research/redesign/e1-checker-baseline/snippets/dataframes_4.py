from tacit.errors import CoercionError, ConstraintError, StructuralError

try:
    orders = Order.parse(raw)
except StructuralError:
    # Missing columns, extra columns, wrong dtypes in structural validation
    ...
except CoercionError:
    # Data couldn't be cast into the schema's target types
    ...
except ConstraintError:
    # Data has the right shape but violates checks/nullability
    ...
