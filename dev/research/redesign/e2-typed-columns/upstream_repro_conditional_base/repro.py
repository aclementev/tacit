"""ibis/expr/types/rich.py defines FixedTextJupyterMixin in try/except branches.
ty and pyrefly then treat it as an Unknown base for Column/Table: typos on any
ibis Column/Table are silently Unknown."""
from typing import reveal_type

try:
    from json import JSONDecoder as Base
except ImportError:
    class Mixin: ...
else:
    class Mixin(Base): ...

class Col(Mixin):
    def mean(self) -> float: return 0.0

def f(c: Col) -> None:
    reveal_type(c.mean())
    reveal_type(c.upperr())  # should be an error

# Fix shape: one unconditional definition visible to type checkers
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    class Mixin2: ...
else:
    try:
        from json import JSONDecoder as Mixin2
    except ImportError:
        class Mixin2: ...

class Col2(Mixin2):
    def mean(self) -> float: return 0.0

def g(c: Col2) -> None:
    reveal_type(c.upperr())  # error expected
