"""
Iris ML Pipeline

A realistic ML pipeline demonstrating tacit's core workflow:
schema definition, inheritance, typed transformations, and parsing.
"""
import ibis
import tacit


# ──────────────────────────────────────────────
# Schemas — the contracts
# ──────────────────────────────────────────────

class Iris(tacit.Schema):
    """Base iris measurements."""
    sepal_length: float
    sepal_width: float
    petal_length: float
    petal_width: float
    species: str


class IrisFeatures(Iris):
    """Iris with engineered features. Inherits all Iris columns."""
    sepal_ratio: float
    petal_ratio: float
    petal_area: float


class IrisPrediction(IrisFeatures):
    """Final output: features + model prediction."""
    predicted_species: str


# ──────────────────────────────────────────────
# Transformations — typed functions
# ──────────────────────────────────────────────

def engineer_features(df: tacit.DataFrame[Iris]) -> tacit.DataFrame[IrisFeatures]:
    """Compute derived features from base measurements.

    df.sepal_length gives autocomplete + type safety because
    df is a schema-aware DataFrame.
    """
    return df.mutate(
        sepal_ratio=df.sepal_length / df.sepal_width,
        petal_ratio=df.petal_length / df.petal_width,
        petal_area=df.petal_length * df.petal_width,
    )


def predict(df: tacit.DataFrame[IrisFeatures]) -> tacit.DataFrame[IrisPrediction]:
    """Run model inference."""
    return df.mutate(
        predicted_species=ibis.case()
            .when(df.petal_length < 2.5, "setosa")
            .when(df.petal_length < 4.8, "versicolor")
            .else_("virginica")
            .end()
    )


# ──────────────────────────────────────────────
# Pipeline — wiring it together
# ──────────────────────────────────────────────

def pipeline(path: str) -> tacit.DataFrame[IrisPrediction]:
    con = ibis.duckdb.connect()
    raw = con.read_csv(path)

    # Boundary: parse external data (coerces types + validates)
    iris = Iris.parse(raw)

    # Internal steps: we trust our own code
    features = engineer_features(iris)
    predictions = predict(features)

    # Boundary: parse before exporting
    return IrisPrediction.parse(predictions)
