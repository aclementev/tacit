#!/usr/bin/env bash
# Reproduce every E15 output (run from anywhere). Benchmarks at 1M rows need ~5 min.
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/.."
R="uv run --frozen"
$R python e15-e2e/tools/patch_facade.py                      # derived facade + E15 hand rules
$R python e15-e2e/tools/make_data.py                         # examples/sources/*.csv
PYTHONPATH=e15-e2e/src $R python e15-e2e/examples/e2e.py > e15-e2e/out/e2e_run.txt
$R python e15-e2e/examples/e2e_plain.py > e15-e2e/out/e2e_plain_run.txt
for f in e2e e2e_plain; do ./e15-e2e/chk.sh e15-e2e/examples/$f.py; done > e15-e2e/out/examples_check.txt 2>&1
$R pytest -q -p no:cacheprovider e15-e2e/tests/test_runtime.py
$R python e15-e2e/tests/typecheck/run_matrix.py > e15-e2e/out/typecheck_matrix.txt
./e15-e2e/tools/plant_bugs.sh > e15-e2e/out/e2e_bugs_check.txt
$R python e15-e2e/tools/session.py > e15-e2e/out/session.txt 2>&1
$R python e15-e2e/tools/plain_errors.py > e15-e2e/out/plain_errors.txt 2>&1
$R python e15-e2e/tools/typed_coverage.py e15-e2e/examples/e2e.py e15-e2e/examples/e2e_plain.py
for f in e2e e2e_plain; do $R pyright -p e15-e2e/pyrightconfig.strict.json e15-e2e/examples/$f.py; done > e15-e2e/out/strict_pyright.txt || true
$R mypy --config-file e15-e2e/mypy.ini --any-exprs-report e15-e2e/out/mypy_any e15-e2e/examples/e2e.py e15-e2e/examples/e2e_plain.py
$R python e15-e2e/tools/loc.py e15-e2e/examples/e2e.py e15-e2e/examples/e2e_plain.py > e15-e2e/out/loc.txt
$R python e15-e2e/tools/bench.py e15-e2e/examples/sources 9 2>/dev/null > e15-e2e/out/bench_small.txt
BIG="${TMPDIR:-/tmp}/e15_src_1m"
$R python e15-e2e/tools/make_data.py 1000000 "$BIG"
$R python e15-e2e/tools/bench.py "$BIG" 3 2>/dev/null > e15-e2e/out/bench_1m.txt
