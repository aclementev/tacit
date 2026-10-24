#!/usr/bin/env bash
# Q1 capability matrix. Needs: java (17/21), and a local postgres for the *-postgres backends:
#   docker run -d --name e16-pg -e POSTGRES_PASSWORD=pw -p 127.0.0.1:55432:5432 docker.io/library/postgres:17
set -u
cd "$(dirname "$0")/.."
export E16_PG="postgresql://postgres:pw@127.0.0.1:55432/postgres" TZ=UTC
R="uv run --frozen python"
$R cap/run_examples.py polars-eager polars-lazy duckdb duckdb-conn sqlframe-duckdb ibis-duckdb ibis-polars sqlframe-postgres ibis-postgres > out/examples_local.txt 2>&1
$R cap/run_examples.py pyspark > out/examples_pyspark.txt 2>&1
$R cap/run_examples.py pyspark-connect > out/examples_pyspark_connect.txt 2>&1
$R cap/run_examples.py --ibis-native ibis-duckdb ibis-polars ibis-postgres > out/examples_ibis_native.txt 2>&1
$R cap/ops.py nw polars-eager polars-lazy duckdb duckdb-conn sqlframe-duckdb ibis-duckdb sqlframe-postgres ibis-postgres > out/ops_nw_local.txt 2>&1
$R cap/ops.py nw pyspark > out/ops_nw_pyspark.txt 2>&1
$R cap/ops.py nw pyspark-connect > out/ops_nw_pyspark_connect.txt 2>&1
$R cap/ops.py ibis ibis-duckdb ibis-polars ibis-postgres > out/ops_ibis_local.txt 2>&1
# ibis 12's pyspark backend requires pyspark<4.1: separate throwaway env
uv run --no-project --python 3.13 --with "ibis-framework[pyspark,duckdb]==12.0.0" --with "pyspark==4.0.1" --with "sqlglot==30.10.0" \
  --with "duckdb==1.5.6" --with narwhals==2.27.1 --with polars==2.0.0 --with pyarrow --with "pandas<3" python cap/ops.py ibis ibis-pyspark > out/ops_ibis_pyspark.txt 2>&1
TZ=UTC uv run --no-project --python 3.13 --with "ibis-framework[pyspark,duckdb]==12.0.0" --with "pyspark==4.0.1" --with "sqlglot==30.10.0" \
  --with "duckdb==1.5.6" --with narwhals==2.27.1 --with polars==2.0.0 --with pyarrow --with "pandas<3" python cap/run_examples.py --ibis-native ibis-pyspark > out/examples_ibis_pyspark.txt 2>&1
rm -rf spark-warehouse metastore_db derby.log
$R cap/summarize.py > /dev/null
echo done
