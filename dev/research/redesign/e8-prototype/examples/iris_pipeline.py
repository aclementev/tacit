"""
Iris ML Pipeline, ported to tacit-next (examples/iris_pipeline.py).

Schema definition, inheritance (delta classes), typed transformations, parsing.
"""

import ibis

import tacit_next as tc
from tacit_next import Column


class Iris(tc.Frame):
    sepal_length: Column[float]
    sepal_width: Column[float]
    petal_length: Column[float]
    petal_width: Column[float]
    species: Column[str]


class Ratios(tc.Frame):
    sepal_ratio: Column[float]
    petal_ratio: Column[float]
    petal_area: Column[float]


class IrisFeatures(Iris, Ratios):
    pass


class Prediction(tc.Frame):
    predicted_species: Column[str]


class IrisPrediction(IrisFeatures, Prediction):
    pass


def engineer_features(df: Iris) -> IrisFeatures:
    return IrisFeatures.extend(
        df,
        Ratios(
            sepal_ratio=df.sepal_length / df.sepal_width,
            petal_ratio=df.petal_length / df.petal_width,
            petal_area=df.petal_length * df.petal_width,
        ),
    )


def predict(df: IrisFeatures) -> IrisPrediction:
    species = tc.cases(
        (df.petal_length < 2.5, "setosa"),
        (df.petal_length < 4.8, "versicolor"),
        else_="virginica",
    )
    return IrisPrediction.extend(df, Prediction(predicted_species=species))


def pipeline(path: str) -> IrisPrediction:
    con = ibis.duckdb.connect()
    raw = con.read_csv(path)

    iris = Iris.parse(raw)
    features = engineer_features(iris)
    predictions = predict(features)
    return IrisPrediction.parse(predictions)
