#!/usr/bin/env bash
# E14: regenerate stubs, run the type-check matrices and the runtime tests (from anywhere).
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/.."
E=e14-column-refs
uv run --frozen python $E/tools/gen_ref_facade.py            # Column facade + Ref/RefScalar   (from tools/base)
uv run --frozen python $E/tools/gen_ref_stub.py              # owner-aware ibis Table mirror   (from tools/base)
for m in $E/examples/schemas.py $E/tests/typecheck/gen_schemas.py; do
  PYTHONPATH=$E/src uv run --frozen python $E/tools/tacit_gen.py "$m"   # `tacit gen`: Literal overloads
done
uv run --frozen python $E/tests/typecheck/run_matrix.py --tag all \
  $E/tests/typecheck/r0[0-3]_*.py $E/examples/b_*.py $E/examples/s_*.py
uv run --frozen pytest -q -p no:cacheprovider $E/tests/test_runtime.py
# optional: the same Ref rewrite over E11's derived facade (16k lines), then time the checkers
#   mkdir -p $E/out/derived_src && cp -r $E/src/* $E/out/derived_src/
#   uv run --frozen python $E/tools/gen_ref_facade.py --base e11-facade-soundness/derived/out_ibis/tacit_next/_column.pyi \
#       --out $E/out/derived_src/tacit_thin/_column.pyi
#   uv run --frozen python $E/tools/time_checkers.py out/derived_src examples/s_ref.py examples/s_attr.py tests/typecheck/r01_refs.py
# optional: overload-scale timing (N schemas x M columns):  python3 $E/probes/p5_perf_gen.py 100 30
