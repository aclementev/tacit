"""RUNTIME side of the bug matrix: what does tacit catch, and WHEN? (layer-independent: only .pyi differ)

    PYTHONPATH=e17-lean-typing/layers/l2 uv run --frozen python e17-lean-typing/tools/run_bugs.py

For examples/ecommerce_t2.py (control) and every bugs/b_*.py:
  A. BUILD   -- run_steps() on UNBOUND ibis tables (ibis.table(schema): no backend, so zero
               queries by construction). Errors here are raised while building expressions /
               by tacit's construction check (names + dtype families, metadata only).
  B. VALIDATE -- real duckdb data: parse inputs, run_steps() (queries counted: expected 0), then
               validate each output with `Schema.parse` (null checks + constraints: queries).
  C. EXECUTE -- execute the outputs (to_pandas); a bug that survives is silently wrong data.
Writes out/runtime_bugs.txt.
"""

from __future__ import annotations

import importlib.util
import traceback
from pathlib import Path

import ibis
from ibis.backends.duckdb import Backend

HERE = Path(__file__).resolve().parents[1]
QUERIES = {"n": 0}
for name in ("_to_duckdb_relation", "to_pyarrow_batches"):
    orig = getattr(Backend, name)

    def counted(self, *a, __orig=orig, **k):  # type: ignore[no-untyped-def]
        QUERIES["n"] += 1
        return __orig(self, *a, **k)

    setattr(Backend, name, counted)


def load(path: Path):  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def short(e: BaseException) -> str:
    msg = " ".join(str(e).split())
    return f"{type(e).__name__}: {msg[:150]}"


def unbound(schema_cls):  # type: ignore[no-untyped-def]
    from tacit_thin._fields import FieldSpec  # noqa: F401  (layer runtime)

    fields = schema_cls.__tacit_fields__
    t = ibis.table({f.name: f.physical().copy(nullable=f.nullable) for f in fields.values()}, name=schema_cls.__name__)
    return schema_cls.conform(t)


def run(path: Path) -> str:
    mod = load(path)
    try:
        mod.run_steps(unbound(mod.RawOrder), unbound(mod.RawCustomer))
    except Exception as e:  # noqa: BLE001
        return f"A BUILD (0 queries)     {short(e)}"
    con = ibis.duckdb.connect()
    customers = mod.RawCustomer.parse(con.read_csv(mod.E6 / "customers.csv"))
    orders = mod.RawOrder.parse(con.read_csv(mod.E6 / "orders.csv"))
    q0 = QUERIES["n"]
    cleaned, stats, latest, summary = mod.run_steps(orders, customers)
    built_q = QUERIES["n"] - q0
    try:
        mod.Order.parse(cleaned)
        mod.CountryMonthStats.parse(stats)
        mod.StatusSummary.parse(summary)
    except Exception as e:  # noqa: BLE001
        return f"B VALIDATE ({built_q} q at build, {QUERIES['n'] - q0} q total) {short(e)}"
    try:
        for t in (cleaned, stats, latest, summary):
            t.to_pandas()
    except Exception as e:  # noqa: BLE001
        return f"C EXECUTE               {short(e)}"
    return f"not caught (steps ran {built_q} queries; outputs pass validation)"


def main() -> None:
    lines = []
    for p in [HERE / "examples" / "ecommerce_t2.py", *sorted((HERE / "bugs").glob("b_*.py"))]:
        try:
            r = run(p)
        except Exception:  # noqa: BLE001
            r = "HARNESS ERROR " + traceback.format_exc(limit=2).replace("\n", " | ")
        lines.append(f"{p.stem:30} {r}")
        print(lines[-1])
    (HERE / "out" / "runtime_bugs.txt").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
