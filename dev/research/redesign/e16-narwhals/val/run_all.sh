#!/usr/bin/env bash
# Q4 validation runs (writes out/validation_*.json and out/validation_all.txt)
set -u
cd "$(dirname "$0")/.."
R="uv run --frozen python val/run_validation.py"
export TZ=UTC
{
for n in 1000000; do
  $R tacit $n polars duckdb ibis-duckdb
  PANDERA_USE_NARWHALS_BACKEND=True $R pandera $n polars ibis-duckdb
  $R pandera $n polars ibis-duckdb
done
$R tacit 1000000 pyspark
PANDERA_USE_NARWHALS_BACKEND=True $R pandera 1000000 pyspark
$R pandera 1000000 pyspark
} 2>&1 | grep -o '{"who".*' > out/validation_all.txt
rm -rf spark-warehouse
