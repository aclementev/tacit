#!/bin/bash
# usage: reveal.sh <file> ; prints reveal_type output + errors for each checker variant
cd "$(dirname "$0")"
f=$1
for v in pyright mypy mypy-ignoremissing mypy-follow ty pyrefly; do
  echo "##### $v"
  case $v in
   pyright) uv run pyright -p pyrightconfig.json $f 2>&1 | sed -E 's#^\s*/[^ ]*e1-checker-baseline/##' | grep -vE "^[0-9]+ error|^$|^/" ;;
   mypy) uv run mypy --config-file mypy.ini --no-pretty --show-column-numbers --show-error-codes $f 2>&1 | grep -v "import-untyped\|readthedocs" ;;
   mypy-ignoremissing) uv run mypy --config-file mypy_ignoremissing.ini --no-pretty --show-column-numbers --show-error-codes $f 2>&1 ;;
   mypy-follow) uv run mypy --config-file mypy_follow.ini --no-pretty --show-column-numbers --show-error-codes $f 2>&1 ;;
   ty) uv run ty check --config-file ty.toml --output-format concise --color never $f 2>&1 ;;
   pyrefly) uv run pyrefly check --config pyrefly.toml --output-format min-text $f 2>&1 | grep -vE "^ INFO [0-9]+ error" ;;
  esac
done
