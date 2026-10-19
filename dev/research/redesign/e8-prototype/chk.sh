#!/usr/bin/env bash
# Usage: ./chk.sh <file-or-dir> [...]   (run from anywhere)
# Prints each checker's diagnostics, with stock ibis 12 from the shared venv.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
R="$HERE/.."
for f in "$@"; do
  f="$(realpath "$f")"
  echo "### pyright"; (cd "$R" && uv run --frozen pyright -p "$HERE/pyrightconfig.json" "$f" 2>&1 | grep -E "error|warning|information" | grep -v "^[0-9]* error")
  echo "### mypy"; (cd "$R" && uv run --frozen mypy --config-file "$HERE/mypy.ini" "$f" 2>&1)
  echo "### ty"; (cd "$R" && uv run --frozen ty check --python .venv --extra-search-path "$HERE/src" --output-format concise "$f" 2>&1)
  echo "### pyrefly"; (cd "$R" && uv run --frozen pyrefly check --python-interpreter-path .venv/bin/python --config "$HERE/pyrefly.toml" --output-format min-text "$f" 2>&1)
done
