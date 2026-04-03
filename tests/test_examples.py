import importlib.util
from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
IRIS_CSV = str(EXAMPLES_DIR / "data" / "iris.csv")

_spec = importlib.util.spec_from_file_location("iris_pipeline", EXAMPLES_DIR / "iris_pipeline.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

pipeline = _mod.pipeline
IrisPrediction = _mod.IrisPrediction


def test_iris_pipeline():
    result = pipeline(IRIS_CSV).execute()

    assert result.shape == (150, 9)
    assert set(result.columns) == set(IrisPrediction._get_fields())

    # Rule-based classifier uses petal_length thresholds, so all true setosa
    # (petal_length < 2.5) should be predicted correctly
    setosa = result[result["species"] == "setosa"]
    assert (setosa["predicted_species"] == "setosa").all()

    # Spot-check feature engineering
    row = result.iloc[0]
    assert row["sepal_ratio"] == pytest.approx(row["sepal_length"] / row["sepal_width"])
    assert row["petal_area"] == pytest.approx(row["petal_length"] * row["petal_width"])
