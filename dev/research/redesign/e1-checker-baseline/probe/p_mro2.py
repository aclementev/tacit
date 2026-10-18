from typing import reveal_type
from ibis.common.bases import Immutable, Abstract
from ibis.common.typing import Coercible
from ibis.expr.types.core import Expr
from ibis.expr.types.rich import FixedTextJupyterMixin
import ibis.expr.types as ir
reveal_type(Abstract)
reveal_type(Immutable)
reveal_type(Coercible)
reveal_type(Expr)
reveal_type(FixedTextJupyterMixin)

class P1(Abstract): ...
class P2(Immutable): ...
class P3(Coercible): ...
class P4(Expr): ...
class P5(FixedTextJupyterMixin): ...
class P6(ir.Table): ...
def a(x: str) -> P1: return x
def b(x: str) -> P2: return x
def c(x: str) -> P3: return x
def d(x: str) -> P4: return x
def e(x: str) -> P5: return x
def f(x: str) -> P6: return x
def g(x: str) -> ir.Table: return x
