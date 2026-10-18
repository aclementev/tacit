"""Derivation spec: the only thing users write. `python codegen.py cg_spec` turns
every module-level Derivation into a real class in cg_generated.py."""

from derive import drop, extend, pick, rename

from cg_models import Iris

IrisSepal = pick(Iris, "sepal_length", "sepal_width")
IrisNoSpecies = drop(Iris, "species")
IrisLabelled = rename(Iris, species="label")
IrisScored = extend(Iris, score=float)
