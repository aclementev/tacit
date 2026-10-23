import functools
from ibis.common.graph import Node
from public import public

__all__ = ['pretty']

class Rendered(str): ...

@public
def pretty(node: Node, scope: dict[str, Node] | None = None) -> str: ...
