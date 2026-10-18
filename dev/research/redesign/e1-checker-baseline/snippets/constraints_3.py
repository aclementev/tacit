class UserProfile(Schema):
    age: Annotated[int, Check.ge(0), Check.lt(200)]
    email: Annotated[str, Check.str_contains("@"), Check.str_length(min_value=5)]
    score: Annotated[float, Check.gt(0), Check.lt(1000), Check.ne(42.0)]
