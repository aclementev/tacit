"""Dump ibis's public column-expression API per dtype family to JSON.

Usage: python introspect.py OUT.json
Version-independent (works on ibis 10, 11, 12, main): used for coverage (task 1)
and for the version diff (task 4).
"""

from __future__ import annotations

import inspect
import json
import sys

import ibis
import ibis.expr.types as ir

FAMILIES = [
    "Integer", "Floating", "Decimal", "String", "Boolean", "Timestamp", "Date", "Time",
    "Interval", "Array", "Struct", "Map", "JSON", "Binary", "UUID", "INET", "MACADDR",
]
GENERIC = ["Value", "Column", "Scalar", "NumericValue", "NumericColumn", "NumericScalar",
           "TemporalValue", "TemporalColumn", "TemporalScalar"]

# Operators users write (dunders worth typing). Others (__repr__, __hash__...) ignored.
OPERATORS = {
    "__add__", "__radd__", "__sub__", "__rsub__", "__mul__", "__rmul__", "__truediv__",
    "__rtruediv__", "__floordiv__", "__rfloordiv__", "__mod__", "__rmod__", "__pow__",
    "__rpow__", "__neg__", "__pos__", "__abs__", "__invert__", "__and__", "__rand__", "__or__",
    "__ror__", "__xor__", "__rxor__", "__lt__", "__le__", "__gt__", "__ge__", "__eq__", "__ne__",
    "__lshift__", "__rshift__", "__rlshift__", "__rrshift__", "__getitem__", "__contains__",
    "__getattr__", "__len__", "__iter__", "__bool__",
}


def sig(fn: object) -> str | None:
    try:
        return str(inspect.signature(fn))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def members(cls: type) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    for name in dir(cls):
        if name.startswith("_") and name not in OPERATORS:
            continue
        owner = next((c for c in cls.__mro__ if name in c.__dict__), None)
        if owner is None or owner is object:
            continue
        raw = owner.__dict__[name]
        kind = "property" if isinstance(raw, property) else (
            "method" if callable(raw) or isinstance(raw, (staticmethod, classmethod)) else "attr")
        fn = raw.fget if isinstance(raw, property) else getattr(cls, name, raw)
        out[name] = {
            "owner": f"{owner.__module__}.{owner.__qualname__}",
            "kind": kind,
            "sig": sig(fn) if kind != "attr" else None,
            "deprecated": bool(getattr(fn, "__deprecated__", None)) or "deprecated" in (inspect.getdoc(fn) or "")[:400].lower(),
        }
    return out


def main(path: str) -> None:
    classes: dict[str, dict[str, object]] = {}
    for fam in FAMILIES:
        for suffix in ("Value", "Column", "Scalar"):
            name = f"{fam}{suffix}"
            cls = getattr(ir, name, None)
            if cls is not None:
                classes[name] = {"mro": [c.__name__ for c in cls.__mro__], "members": members(cls)}
    for name in GENERIC:
        cls = getattr(ir, name, None)
        if cls is not None:
            classes[name] = {"mro": [c.__name__ for c in cls.__mro__], "members": members(cls)}
    json.dump({"ibis": ibis.__version__, "classes": classes}, open(path, "w"), indent=1, sort_keys=True)
    print(f"ibis {ibis.__version__}: {len(classes)} classes -> {path}")


if __name__ == "__main__":
    main(sys.argv[1])
