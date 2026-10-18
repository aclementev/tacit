import ibis.expr.types as ir
import ibis.common.bases as b
import ibis.expr.types.core as core
reveal_type(ir.Table)
reveal_type(ir.Expr)
reveal_type(core.Expr)
reveal_type(b.Immutable)
reveal_type(b.Concrete)
reveal_type(ibis_table := __import__("ibis").table)
