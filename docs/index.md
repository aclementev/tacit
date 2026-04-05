# tacit

*We called it tacit because data contracts shouldn't be.*

Pydantic-style schemas for data pipelines, built on [ibis](https://ibis-project.org/).

Define your data contracts once. Get type-safe transformations with editor
support, structural and runtime validation, across any ibis-supported backend
(DuckDB, Spark, BigQuery, Polars, Postgres, and
[many more](https://ibis-project.org/backends/)).

## Install

=== "uv"

    ```bash
    uv add tacit
    ```

=== "pip"

    ```bash
    pip install tacit
    ```

## Quick example

```python
import ibis
import tacit


class Iris(tacit.Schema):
    sepal_length: float
    sepal_width: float
    petal_length: float
    petal_width: float
    species: str


class IrisFeatures(Iris):
    sepal_ratio: float
    petal_area: float


@tacit.contract
def engineer_features(df: tacit.DataFrame[Iris]) -> tacit.DataFrame[IrisFeatures]:
    return df.mutate(
        sepal_ratio=df.sepal_length / df.sepal_width,
        petal_area=df.petal_length * df.petal_width,
    )


table = ibis.duckdb.connect().read_csv("iris.csv")
iris = Iris.parse(table)
features = engineer_features(iris)
```
