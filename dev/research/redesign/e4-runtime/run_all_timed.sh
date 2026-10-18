#!/bin/sh
# Timed benchmarks, run sequentially (best on an otherwise idle box; the machine has 2 cores).
set -e
cd "$(dirname "$0")"
REPEAT=5 uv run python bench_parse.py 1000000 > raw_parse_1M.txt 2>&1
REPEAT=3 uv run python bench_parse.py 10000000 > raw_parse_10M.txt 2>&1
uv run python bench_decompose.py > raw_decompose.txt 2>&1
REPEAT=3 uv run python bench_coerce.py 1000000 2>&1 | cut -c1-420 > raw_coerce_1M.txt
REPEAT=2 uv run python bench_coerce.py 10000000 2>&1 | cut -c1-420 > raw_coerce_10M.txt
echo done > .timed_done
