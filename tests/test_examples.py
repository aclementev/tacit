import importlib.util
from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
IRIS_CSV = str(EXAMPLES_DIR / "data" / "iris.csv")
LINEITEM_CSV = str(EXAMPLES_DIR / "data" / "lineitem.csv")


def _load_example(name: str):
    spec = importlib.util.spec_from_file_location(name, EXAMPLES_DIR / f"{name}.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_iris_pipeline():
    mod = _load_example("iris_pipeline")
    result = mod.pipeline(IRIS_CSV).execute()

    assert result.shape == (150, 9)
    assert set(result.columns) == set(mod.IrisPrediction._get_fields())

    # Rule-based classifier uses petal_length thresholds, so all true setosa
    # (petal_length < 2.5) should be predicted correctly
    setosa = result[result["species"] == "setosa"]
    assert (setosa["predicted_species"] == "setosa").all()

    row = result.iloc[0]
    assert row["sepal_ratio"] == pytest.approx(row["sepal_length"] / row["sepal_width"])
    assert row["petal_area"] == pytest.approx(row["petal_length"] * row["petal_width"])


def test_tpch_q1():
    mod = _load_example("tpch_q1")
    result = mod.pipeline(LINEITEM_CSV).execute()

    assert result.shape == (4, 10)
    assert set(result.columns) == set(mod.PricingSummary._get_fields())

    # Rows are ordered by (l_returnflag, l_linestatus), so first group is A/F
    af = result.iloc[0]
    assert af["l_returnflag"] == "A"
    assert af["l_linestatus"] == "F"
    assert af["count_order"] == 4
    assert af["sum_qty"] == pytest.approx(108.0)
