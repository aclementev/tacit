"""
Iris ML Pipeline

A realistic ML pipeline demonstrating tacit's core workflow:
schema definition, inheritance, typed transformations, and parsing.
"""
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


def engineer_features(df: tacit.DataFrame[Iris]) -> tacit.DataFrame[IrisFeatures]:
    result = df.mutate(
        sepal_ratio=df.sepal_length / df.sepal_width,
        petal_ratio=df.petal_length / df.petal_width,
        petal_area=df.petal_length * df.petal_width,
    )
    return IrisFeatures.cast(result)


def predict(df: tacit.DataFrame[IrisFeatures]) -> tacit.DataFrame[IrisPrediction]:
    result = df.mutate(
        predicted_species=ibis.cases(
            (df.petal_length < 2.5, "setosa"),
            (df.petal_length < 4.8, "versicolor"),
            else_="virginica",
        )
    )
    return IrisPrediction.cast(result)


def pipeline(path: str) -> tacit.DataFrame[IrisPrediction]:
    con = ibis.duckdb.connect()
    raw = con.read_csv(path)

    iris = Iris.parse(raw)
    features = engineer_features(iris)
    predictions = predict(features)
    return IrisPrediction.parse(predictions)
