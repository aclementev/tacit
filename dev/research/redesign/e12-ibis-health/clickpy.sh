#!/bin/bash
# monthly PyPI downloads from ClickPy public ClickHouse (pypi.pypi_downloads_per_day)
for p in ibis-framework polars duckdb narwhals pandera sqlglot; do
  echo "== $p"
  curl -s -m 60 --user play: "https://sql-clickhouse.clickhouse.com/?default_format=TSV" --data-binary "SELECT toStartOfMonth(date) m, sum(count) FROM pypi.pypi_downloads_per_day WHERE project='$p' AND date>='2024-01-01' GROUP BY m ORDER BY m"
done
