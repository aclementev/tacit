#!/usr/bin/env bash
# Rebuild everything and run every configuration (from anywhere). ~10 min, mostly mypy on patched ibis.
set -eu
HERE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HERE/.."
uv run --frozen python e17-lean-typing/tools/gen_cols_stub.py
uv run --frozen python e17-lean-typing/tools/gen_table_stub.py --facade mirror --out e17-lean-typing/overlays/l2/tacit_thin/_ibis_api.pyi
uv run --frozen python e17-lean-typing/tools/gen_table_stub.py --facade none --out e17-lean-typing/overlays/l1/tacit_thin/_ibis_api.pyi
uv run --frozen python e17-lean-typing/tools/make_layers.py
uv run --frozen python e17-lean-typing/tools/make_bugs.py
FILES="e17-lean-typing/cases/t2_cases.py e17-lean-typing/cases/t_columns.py e17-lean-typing/examples/*.py e17-lean-typing/bugs/b_*.py"
for L in l1 l2 l3; do
  for S in "" --nostub; do
    for P in "" --patched; do
      uv run --frozen python e17-lean-typing/tools/run_matrix.py --layer $L $S $P $FILES | grep -E "^\[|TOTAL"
    done
  done
done
PYTHONPATH=e17-lean-typing/layers/l2 uv run --frozen python e17-lean-typing/tools/run_bugs.py
uv run --frozen python e17-lean-typing/tools/summarize.py
