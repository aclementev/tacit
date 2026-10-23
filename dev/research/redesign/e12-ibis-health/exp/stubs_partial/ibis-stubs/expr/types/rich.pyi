import rich.panel
import rich.table
from ibis.expr import types as ir
from rich.console import RenderableType as RenderableType
from rich.jupyter import JupyterMixin

class FixedTextJupyterMixin: ...

def capture_rich_renderable(renderable: RenderableType) -> str: ...
def to_rich(expr: ir.Scalar | ir.Table | ir.Column, *, max_rows: int | None = None, max_columns: int | None = None, max_length: int | None = None, max_string: int | None = None, max_depth: int | None = None, console_width: int | float | None = None) -> rich.panel.Panel | rich.table.Table: ...
