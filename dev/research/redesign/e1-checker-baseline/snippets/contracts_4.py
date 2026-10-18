from tacit.errors import ValidationError, ValidationPhase

try:
    result = transform(df)
except ValidationError as exc:
    if exc.phase is ValidationPhase.CONTRACT_INPUT:
        ...
    elif exc.phase is ValidationPhase.CONTRACT_OUTPUT:
        ...
