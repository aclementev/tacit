from typing import reveal_type
import selfimp
def f(t: selfimp.Table) -> None:
    reveal_type(t)
    reveal_type(t.mutate())
