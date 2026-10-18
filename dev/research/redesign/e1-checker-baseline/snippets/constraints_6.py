def is_even(x: int) -> bool:
    return x % 2 == 0

class MySchema(Schema):
    count: Annotated[int, Check(is_even, element_wise=True)]
