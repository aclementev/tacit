"""Sketch: examples/iris_pipeline.py in the recommended design (runs on duckdb)."""

from typing import reveal_type

import ibis

import proto.newtacit as tacit


class Iris(tacit.Frame):
    sepal_length: tacit.Float64
    sepal_width: tacit.Float64
    petal_length: tacit.Float64
    petal_width: tacit.Float64
    species: tacit.String


class Ratios(tacit.Frame):  # delta: only the new columns
    sepal_ratio: tacit.Float64
    petal_ratio: tacit.Float64
    petal_area: tacit.Float64


class IrisFeatures(Iris, Ratios):
    pass


class Prediction(tacit.Frame):
    predicted_species: tacit.String


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
    species = ibis.cases(
        (df.petal_length < 2.5, "setosa"),
        (df.petal_length < 4.8, "versicolor"),
        else_="virginica",
    )
    reveal_type(species)  # ibis: Value (no dtype info)
    return IrisPrediction.extend(df, Prediction(predicted_species=species))


def pipeline(path: str) -> IrisPrediction:
    raw = ibis.duckdb.connect().read_csv(path)
    iris = Iris.parse(raw)
    return predict(engineer_features(iris))


if __name__ == "__main__":
    out = pipeline("../../../../../examples/data/iris.csv")
    reveal_type(out)
    print(out.execute().groupby("predicted_species").size().to_dict())
