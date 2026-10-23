import functools
import ibis.expr.types as ir
from _typeshed import Incomplete
from ibis.backends import BaseBackend as BaseBackend
from ibis.common.grounds import Concrete as Concrete

class Example(Concrete):
    name: str
    help: str | None
    def fetch(self, *, table_name: str | None = None, backend: BaseBackend | None = None) -> ir.Table: ...

@functools.cache
def __dir__() -> list[str]: ...

class Zones(Concrete):
    name: str
    help: str | None
    def fetch(self, *, table_name: str | None = None, backend: BaseBackend | None = None) -> ir.Table: ...

zones: Incomplete

def __getattr__(name: str) -> Example: ...
