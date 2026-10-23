"""Run the original tacit 0.2 examples and the tacit-thin (E13) ports; compare results."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
sys.path[:0] = [str(REPO / "examples"), str(Path(__file__).resolve().parents[1] / "examples")]
import importlib

for mod, csv in [("iris_pipeline", "iris.csv"), ("tpch_q1", "lineitem.csv")]:
    old = importlib.import_module(mod)  # repo examples (tacit 0.2) come first on sys.path
    sys.modules.pop(mod)
    sys.path.pop(0)
    new = importlib.import_module(mod)
    sys.path.insert(0, str(REPO / "examples"))
    sys.modules.pop(mod)
    a = old.pipeline(str(REPO / "examples" / "data" / csv)).to_pandas()
    b = new.pipeline(str(REPO / "examples" / "data" / csv)).to_pandas()
    a = a.sort_values(list(a.columns)).reset_index(drop=True)
    b = b.sort_values(list(b.columns)).reset_index(drop=True)
    print(mod, "old", a.shape, "new", b.shape, "identical:", a.equals(b))
    if mod == "iris_pipeline":
        print("  predicted:", b.predicted_species.value_counts().to_dict())
    else:
        print(b.to_string())
