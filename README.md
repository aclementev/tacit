# Tacit

A library for building explicit Data Pipelines.

Main features:

* Define input and output contracts as schemas
* Run validation over the contracts
* Use the schemas in the pipeline implementation


```python
import polars as pl
import tacit

class Iris(tacit.Schema):
    sepal_length: float  # TODO(alvaro): Specify min / max values
    sepal_width: float
    petal_length: float
    petal_width: float

# FIXME(alvaro): Add schema composition (maybe using inheritance? is there a different way?)
class IrisPrediction(tacit.Schema):
    sepal_length: float
    sepal_width: float
    petal_length: float
    petal_width: float
    custom_feature: float
    species: Literal["setosa", "versicolor", "virginica"]

def process_data(df: Iris) -> IrisPrediction:
    model = load_model()
    df = df.with_columns((pl.col(Iris.sepal_length) ** 2 / pl.col(Iris.petal_width)).alias(IrisPrediction.custom_feature))
    df = df.with_columns(pl.Series(IrisPrediction.custom_feature, model.predict(df))
    return df


def pipeline():
    raw_df = load_iris()
    df, errors = Iris.validate(df, strict=True)
    if errors:
        print(errors.pretty())
        return

    # At this point, `df` is guaranteed to be a Iris instance
    res_df = process_data(df)
    return res_df
```
