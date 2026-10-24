#!/usr/bin/env bash
# Q4 on PySpark. pandera.pyspark imports pandas.tseries.frequencies.DateOffset, gone in pandas 3 -> pandas<3 env.
set -u
cd "$(dirname "$0")/.."
export TZ=UTC
E=(uv run --no-project --python 3.13 --with pandera==0.34.1 --with pyspark==4.2.0 --with "pandas<3" --with polars==2.0.0 --with numpy --with narwhals==2.27.1 --with pyarrow --with duckdb==1.5.6 python val/run_validation.py)
{ "${E[@]}" tacit 1000000 pyspark; PANDERA_USE_NARWHALS_BACKEND=True "${E[@]}" pandera 1000000 pyspark; "${E[@]}" pandera 1000000 pyspark; } 2>&1 | tr '\r' '\n' | grep -o '{"who".*' > out/validation_spark.txt
rm -rf spark-warehouse
