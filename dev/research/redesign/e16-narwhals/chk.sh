#!/usr/bin/env bash
# Usage: ./chk.sh <file> ...   Runs the four checkers (versions pinned in pyproject) on the files.
set -u
cd "$(dirname "$0")"
for f in "$@"; do
  echo "### pyright"; uv run --frozen pyright -p pyrightconfig.json "$f" 2>&1 | grep -E " - (error|warning|information)" | sed 's#.*/##'
  echo "### mypy"; uv run --frozen mypy --config-file mypy.ini --no-pretty --show-error-codes "$f" 2>&1 | grep -v "^Success\|^Found" | sed 's#.*/##'
  echo "### ty"; uv run --frozen ty check --config-file ty.toml --output-format concise --color never "$f" 2>&1 | grep -E "error|warning|info" | grep -v "^Found\|All checks" | sed 's#.*/##'
  echo "### pyrefly"; uv run --frozen pyrefly check --config pyrefly.toml --output-format min-text "$f" 2>&1 | grep -E "^(ERROR|INFO|WARN)" | sed 's#[^ ]*/##'
done
