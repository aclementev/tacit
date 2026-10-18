# 0 < score < 1 (exclusive on both ends)
score: Annotated[float, Check.in_range(0, 1, include_min=False, include_max=False)]
