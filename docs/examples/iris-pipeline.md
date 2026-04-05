# Iris Pipeline

An end-to-end pipeline that loads iris data from a CSV, engineers features,
and predicts species. Demonstrates schema inheritance, `parse()` at boundaries,
and `@contract` for typed transformations.

The full source is at
[`examples/iris_pipeline.py`](https://github.com/alvaroclemente/tacit/blob/main/examples/iris_pipeline.py).

## Schemas

The pipeline has three stages, each with its own schema. Inheritance adds
columns at each stage — no duplication:

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
    petal_ratio: float
    petal_area: float


class IrisPrediction(IrisFeatures):
    predicted_species: str
```

`Iris` has 5 columns. `IrisFeatures` adds 3 (8 total). `IrisPrediction` adds 1
(9 total). The chain mirrors the pipeline — each stage enriches the previous
one's output.

## Transformations

Two functions transform data between stages. `@contract` reads the type
annotations and calls `cast()` on inputs and outputs automatically:

```python
@tacit.contract
def engineer_features(df: tacit.DataFrame[Iris]) -> tacit.DataFrame[IrisFeatures]:
    return df.mutate(
        sepal_ratio=df.sepal_length / df.sepal_width,
        petal_ratio=df.petal_length / df.petal_width,
        petal_area=df.petal_length * df.petal_width,
    )


@tacit.contract
def predict(df: tacit.DataFrame[IrisFeatures]) -> tacit.DataFrame[IrisPrediction]:
    return df.mutate(
        predicted_species=ibis.cases(
            (df.petal_length < 2.5, "setosa"),
            (df.petal_length < 4.8, "versicolor"),
            else_="virginica",
        )
    )
```

Each function body is pure ibis — `.mutate()`, `.cases()`. The decorator
handles the schema verification so the function just does the transformation.

## Pipeline

The `pipeline()` function ties the stages together. `parse()` validates data
at the boundaries:

```python
def pipeline(path: str) -> tacit.DataFrame[IrisPrediction]:
    con = ibis.duckdb.connect()
    raw = con.read_csv(path)

    iris = Iris.parse(raw)
    features = engineer_features(iris)
    predictions = predict(features)
    return IrisPrediction.parse(predictions)
```

`Iris.parse(raw)` at the top coerces CSV string columns to the declared types
and validates the schema. `IrisPrediction.parse(predictions)` at the end is a
final check that the full pipeline produced the expected output.

Between those boundaries, `@contract` on each transformation does lightweight
structural checks via `cast()`.

## Running it

```bash
uv run python examples/iris_pipeline.py
```

The pipeline runs against DuckDB via ibis — read CSV, coerce types, compute
features, predict species, validate output. Schema safety at every stage.
