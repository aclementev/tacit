age: Annotated[int, Check.ge(0, error="age must be non-negative")]
