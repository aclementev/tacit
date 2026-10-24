#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."
export E16_PG="postgresql://postgres:pw@127.0.0.1:55432/postgres" TZ=UTC
R="uv run --frozen python examples/run.py"
{ $R polars-eager polars-lazy duckdb duckdb-conn sqlframe-duckdb ibis-duckdb ibis-polars sqlframe-postgres ibis-postgres native-polars
  $R pyspark native-pyspark; $R pyspark-connect; } 2>&1 | tr '\r' '\n' | grep -E "^==|^   " > out/t2nw_examples.txt
./chk.sh examples/t2nw.py examples/native.py > out/t2nw_examples_typecheck.txt 2>&1
rm -rf spark-warehouse
