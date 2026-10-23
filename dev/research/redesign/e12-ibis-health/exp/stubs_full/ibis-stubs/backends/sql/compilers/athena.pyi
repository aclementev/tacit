from _typeshed import Incomplete
from ibis.backends.sql.compilers.trino import TrinoCompiler as TrinoCompiler
from ibis.backends.sql.datatypes import AthenaType as AthenaType
from sqlglot.dialects import Athena

class AthenaCompiler(TrinoCompiler):
    dialect = Athena
    type_mapper = AthenaType
    UNSUPPORTED_OPS: Incomplete
    def visit_Cast(self, op, *, arg, to): ...

compiler: Incomplete
