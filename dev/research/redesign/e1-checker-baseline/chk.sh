#!/bin/bash
# usage: chk.sh <variant> <files...>   (variants as in run_matrix.py)
cd "$(dirname "$0")"
v=$1; shift
case $v in
 pyright) uv run pyright -p pyrightconfig.json "$@" 2>&1 | sed -E 's#^\s*/[^ ]*e1-checker-baseline/##' | grep -vE "^$|^/" ;;
 pyright-repo) uv run pyright -p pyrightconfig_repo.json "$@" 2>&1 | sed -E 's#^\s*/[^ ]*e1-checker-baseline/##' | grep -vE "^$|^/" ;;
 mypy|mypy-tacit-typed|mypy-strict|mypy-follow|mypy-follow-strict|mypy-ignoremissing)
   cfg=mypy_${v#mypy-}.ini; [ $v = mypy-tacit-typed ] && cfg=mypy_tacittyped.ini; [ $v = mypy ] && cfg=mypy.ini
   uv run mypy --config-file $cfg --no-pretty --show-column-numbers --show-error-codes "$@" 2>&1 | grep -v "readthedocs" ;;
 ty) uv run ty check --config-file ty.toml --output-format concise --color never "$@" 2>&1 ;;
 pyrefly) uv run pyrefly check --config pyrefly.toml --output-format min-text "$@" 2>&1 ;;
esac
