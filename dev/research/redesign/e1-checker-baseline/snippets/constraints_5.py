# Allows nulls, but non-null values must be positive
score: Annotated[float, Nullable(), Check.gt(0)]
