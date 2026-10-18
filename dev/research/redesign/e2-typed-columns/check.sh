#!/usr/bin/env bash
# Usage: ./check.sh probes/foo.py [...]
# -> out/foo.{pyright,mypy,ty,pyrefly,runtime}.txt and out/foo.summary.txt
set -u
cd "$(dirname "$0")"
for f in "$@"; do
  b=$(basename "$f" .py)
  (cd .. && uv run --frozen pyright -p e2-typed-columns "e2-typed-columns/$f") > "out/$b.pyright.txt" 2>&1
  (cd .. && uv run --frozen mypy --config-file e2-typed-columns/mypy.ini "e2-typed-columns/$f") > "out/$b.mypy.txt" 2>&1
  (cd .. && uv run --frozen ty check --python .venv --extra-search-path e2-typed-columns --output-format concise "e2-typed-columns/$f") > "out/$b.ty.txt" 2>&1
  (cd .. && uv run --frozen pyrefly check --python-interpreter-path .venv/bin/python --search-path e2-typed-columns --output-format min-text "e2-typed-columns/$f") > "out/$b.pyrefly.txt" 2>&1
  (cd probes && PYTHONPATH=.. ../../.venv/bin/python "$(basename "$f")") > "out/$b.runtime.txt" 2>&1
  echo "$b: runtime_rc=$?"
  ../.venv/bin/python summarize.py "$f" > /dev/null
done
