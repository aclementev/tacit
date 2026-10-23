#!/usr/bin/env bash
# Reproduce E11 (run from anywhere). Shared uv project stays untouched; other ibis versions use --no-project envs.
set -eu
H="$(cd "$(dirname "$0")" && pwd)"; R="$H/.."; cd "$R"
U="uv run --frozen"
MAIN="ibis-framework[duckdb] @ git+https://github.com/ibis-project/ibis@90656f775df94ce73ef8b28577800b5c2e3ef163"
# 1. coverage
$U python $H/introspect.py $H/versions/api_12.0.0.json
(cd $H && $U python coverage.py versions/api_12.0.0.json ../e8-prototype/src/tacit_next/_column.pyi out)
./e8-prototype/chk.sh $H/probes/p1_uncovered.py > $H/out/p1_uncovered.txt 2>&1 || true
# 2. conformance harness: runtime (ibis+duckdb) x static (4 checkers) -> classified mismatches
$U python $H/conformance/runtime.py $H/out/runtime_12.0.0.json
$U python $H/conformance/static.py e8-prototype/src $H/out/static_e8.json
(cd $H && for c in pyright mypy ty pyrefly; do $U python conformance/compare.py out/static_e8.json out/runtime_12.0.0.json out/conformance_e8_$c $c; done)
(cd $H && $U python sigcheck.py ../e8-prototype/src/tacit_next/_column.pyi > /dev/null)
# 3. derived generator (+ fallback variants) and the same harness on its output
for fb in ibis any none; do $U python $H/derived/make_pkg.py $H/derived/out_$fb --fallback $fb; done
$U python $H/conformance/static.py $H/derived/out_ibis $H/out/static_derived.json
(cd $H && for c in pyright mypy ty pyrefly; do $U python conformance/compare.py out/static_derived.json out/runtime_12.0.0.json out/conformance_derived_$c $c; done)
(cd $H && for s in ../e8-prototype/src derived/out_ibis derived/out_any derived/out_none; do $U python chk_src.py $s probes/p3_fallback.py; done > out/p3_fallback.txt)
$U python $H/e8matrix/run_matrix.py > /dev/null; TACIT_SRC=$H/derived/out_ibis $U python $H/e8matrix/run_matrix.py > /dev/null
# 4. version diff (API + behaviour) and regenerated stubs per version
uv run --no-project --python 3.13 --with "ibis-framework[duckdb]==10.*" --with "duckdb<1.3" python $H/introspect.py $H/versions/api_10.json
uv run --no-project --python 3.13 --with "ibis-framework[duckdb]==11.*" python $H/introspect.py $H/versions/api_11.json
uv run --no-project --python 3.13 --with "$MAIN" python $H/introspect.py $H/versions/api_main.json
(cd $H && $U python version_diff.py versions/api_10.json versions/api_11.json versions/api_12.0.0.json versions/api_main.json > /dev/null)
uv run --no-project --python 3.13 --with "ibis-framework[duckdb]==10.*" --with "duckdb<1.3" python $H/conformance/runtime.py $H/out/runtime_10.json
uv run --no-project --python 3.13 --with "ibis-framework[duckdb]==11.*" python $H/conformance/runtime.py $H/out/runtime_11.json
uv run --no-project --python 3.13 --with "$MAIN" python $H/conformance/runtime.py $H/out/runtime_main.json
(cd $H && { $U python runtime_diff.py out/runtime_10.json out/runtime_11.json; $U python runtime_diff.py out/runtime_11.json out/runtime_12.0.0.json; $U python runtime_diff.py out/runtime_12.0.0.json out/runtime_main.json; } > out/runtime_version_diff.txt)
# 5. runtime access
PYTHONPATH=e8-prototype/src $U python $H/probes/p4_runtime_access.py > $H/out/p4_runtime_access.txt
