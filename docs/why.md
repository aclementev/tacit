# Why tacit

<!-- TODO: flesh out with comparisons and philosophy -->

Data pipelines break silently. A column gets renamed upstream, a type changes
from int to string, a join produces unexpected nulls — and you find out three
stages downstream when something produces garbage results.

Tacit makes the shape of your data explicit and checkable:

- **At read time**: your editor autocompletes column names from the schema
- **At check time**: the type checker catches mismatches between pipeline stages
- **At run time**: parsing and validation ensure the actual data matches the
  contract

## Design principles

- **Strict by default.** Unexpected columns are an error, not silently ignored.
- **Parsing is the gateway.** `Schema.parse()` coerces types and validates in
  one call.
- **Library, not framework.** Use tacit with Dagster, Airflow, a script, a
  notebook — anything.
- **Ibis-native.** Transformations use ibis's expression API directly. Tacit
  handles contracts, ibis handles execution.
