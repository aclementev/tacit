import ibis.expr.operations as ops
from _typeshed import Incomplete
from collections.abc import Callable
from ibis.common.graph import Graph as Graph

def get_type(node): ...
def get_label(node): ...

DEFAULT_NODE_ATTRS: Incomplete
DEFAULT_EDGE_ATTRS: Incomplete
NodeAttributeGetter = Callable[[ops.Node], dict[str, str] | None]
EdgeAttributeGetter = Callable[[ops.Node, ops.Node], dict[str, str] | None]

def to_graph(expr, node_attr=None, node_attr_getter: NodeAttributeGetter | None = None, edge_attr=None, edge_attr_getter: EdgeAttributeGetter | None = None, label_edges: bool = False): ...
def draw(graph, path=None, format: str = 'png', verbose: bool = False): ...
