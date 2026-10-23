#!/bin/sh
# Q3 timed runs (sequential). Box is shared with other experiments: configs are interleaved per dataset.
cd "$(dirname "$0")"
REPEAT=5 uv run --frozen python bench_tuned.py 1000000 > raw_tuned_1M.txt 2>&1
REPEAT=3 uv run --frozen python bench_tuned.py 10000000 > raw_tuned_10M.txt 2>&1
REPEAT=3 uv run --frozen python bench_tuned.py csv 1000000 > raw_tuned_csv_1M.txt 2>&1
PANDERA_USE_NARWHALS_BACKEND=True REPEAT=3 uv run --frozen --with narwhals python bench_tuned.py 1000000 > raw_tuned_narwhals_1M.txt 2>&1
echo done > .bench_done
