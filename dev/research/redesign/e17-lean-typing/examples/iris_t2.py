"""Iris pipeline (examples/iris_pipeline.py) in the T2 spelling: DataFrame[S] + `df.c`."""

import ibis

import tacit_t2 as tc2
from tacit_t2 import Column, DataFrame


class Iris(tc2.Schema):
    sepal_length: Column[float]
    sepal_width: Column[float]
    petal_length: Column[float]
    petal_width: Column[float]
    species: Column[str]


class Ratios(tc2.Schema):
    sepal_ratio: Column[float]
    petal_ratio: Column[float]
    petal_area: Column[float]


class IrisFeatures(Iris, Ratios):
    pass


class Prediction(tc2.Schema):
    predicted_species: Column[str]


class IrisPrediction(IrisFeatures, Prediction):
    pass


def engineer_features(df: DataFrame[Iris]) -> DataFrame[IrisFeatures]:
    c = df.c
    return IrisFeatures.extend(
        df,
        Ratios.build(
            sepal_ratio=c.sepal_length / c.sepal_width,
            petal_ratio=c.petal_length / c.petal_width,
            petal_area=c.petal_length * c.petal_width,
        ),
    )


def predict(df: DataFrame[IrisFeatures]) -> DataFrame[IrisPrediction]:
    c = df.c
    species = tc2.cases(
        (c.petal_length < 2.5, "setosa"),
        (c.petal_length < 4.8, "versicolor"),
        else_="virginica",
    )
    return IrisPrediction.extend(df, Prediction.build(predicted_species=species))


def pipeline(path: str) -> DataFrame[IrisPrediction]:
    con = ibis.duckdb.connect()
    iris = Iris.parse(con.read_csv(path))
    return IrisPrediction.parse(predict(engineer_features(iris)))


if __name__ == "__main__":
    import sys

    print(pipeline(sys.argv[1]).to_pandas().predicted_species.value_counts())
