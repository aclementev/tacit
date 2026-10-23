#!/bin/sh
# Second timing pass (box is shared; report min across passes) + fixed overhead at 1k rows + import cost.
cd "$(dirname "$0")"
REPEAT=20 uv run --frozen python bench_tuned.py 1000 > raw_tuned_1k.txt 2>&1
TAG=_pass2 REPEAT=5 uv run --frozen python bench_tuned.py 1000000 > raw_tuned_1M_pass2.txt 2>&1
TAG=_pass2 REPEAT=3 uv run --frozen python bench_tuned.py 10000000 > raw_tuned_10M_pass2.txt 2>&1
uv run --frozen python bench_import.py > raw_import.txt 2>&1
echo done > .bench2_done
