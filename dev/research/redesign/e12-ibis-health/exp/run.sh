#!/usr/bin/env bash
# usage: run.sh <label> <stubroot-or-none> <file>
R=/home/dev/code/tacit-f3529d373e83e544/pipeline-type-safety-redesign-a60149/dev/research/redesign
E=$R/e12-ibis-health/exp; S8=$R/e8-prototype/src
label=$1; stub=$2; f=$3
cd $R
echo "##### $label"
if [ "$stub" = none ]; then EXTRA=""; MP="$S8"; PR_EXTRA="[\"$S8\"]"; else EXTRA="$stub"; MP="$S8:$stub"; PR_EXTRA="[\"$S8\",\"$stub\"]"; fi
cat > $E/pyrightconfig.tmp.json <<J
{"pythonVersion":"3.13","venvPath":"$R","venv":".venv","extraPaths":$PR_EXTRA,"typeCheckingMode":"standard","reportMissingModuleSource":false}
J
echo "-- pyright"; uv run --frozen pyright -p $E/pyrightconfig.tmp.json $f 2>&1 | grep -E "error|warning" | grep -v "^[0-9]* error" | sed "s#$E/##"
cat > $E/mypy.tmp.ini <<J
[mypy]
python_version = 3.13
follow_untyped_imports = True
check_untyped_defs = True
mypy_path = $MP
cache_dir = $E/.mypy_cache_$label
[mypy-tacit_next.*]
ignore_errors = True
J
echo "-- mypy"; uv run --frozen mypy --config-file $E/mypy.tmp.ini $f 2>&1 | sed "s#$E/##"
SP="--extra-search-path $S8"; [ "$stub" != none ] && SP="$SP --extra-search-path $stub"
echo "-- ty"; uv run --frozen ty check --python .venv $SP --output-format concise $f 2>&1 | sed "s#$E/##"
SPR="[\"$S8\"]"; [ "$stub" != none ] && SPR="[\"$S8\",\"$stub\"]"
cat > $E/pyrefly.tmp.toml <<J
python-version = "3.13"
search-path = $SPR
J
echo "-- pyrefly"; uv run --frozen pyrefly check --python-interpreter-path .venv/bin/python --config $E/pyrefly.tmp.toml --output-format min-text $f 2>&1 | sed "s#$E/##"
