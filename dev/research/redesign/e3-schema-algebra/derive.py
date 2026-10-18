"""Runtime schema derivations (pick/drop/rename/extend) for the e3 experiments.

Two flavours:
- `pick(Iris, ...)` etc. return a `Derivation` spec (pure data; used by codegen
  and by `VerifiedSchema`).
- `Derivation.build()` creates the class at runtime (statically opaque).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, get_type_hints

from tx import Schema


def fields(schema: type) -> dict[str, Any]:
    return {
        k: v
        for k, v in get_type_hints(schema, include_extras=True).items()
        if not k.startswith("_") and getattr(v, "__origin__", None) is not ClassVar
    }


@dataclass(frozen=True)
class Derivation:
    base: type[Schema]
    op: str
    names: tuple[str, ...] = ()
    renames: tuple[tuple[str, str], ...] = ()
    extra: tuple[tuple[str, Any], ...] = field(default=())

    def columns(self) -> dict[str, Any]:
        src = fields(self.base)
        if self.op == "pick":
            unknown = set(self.names) - set(src)
            if unknown:
                raise KeyError(f"{self.base.__name__} has no columns {sorted(unknown)}")
            return {n: src[n] for n in self.names}
        if self.op == "drop":
            return {n: t for n, t in src.items() if n not in self.names}
        if self.op == "rename":
            m = dict(self.renames)
            return {m.get(n, n): t for n, t in src.items()}
        if self.op == "extend":
            return {**src, **dict(self.extra)}
        raise ValueError(self.op)

    def build(self, name: str) -> type[Schema]:
        return type(name, (Schema,), {"__annotations__": self.columns(), "__module__": self.base.__module__})


def pick(base: type[Schema], *names: str) -> Derivation:
    return Derivation(base, "pick", names=names)


def drop(base: type[Schema], *names: str) -> Derivation:
    return Derivation(base, "drop", names=names)


def rename(base: type[Schema], **mapping: str) -> Derivation:
    return Derivation(base, "rename", renames=tuple(mapping.items()))


def extend(base: type[Schema], **cols: Any) -> Derivation:
    return Derivation(base, "extend", extra=tuple(cols.items()))


class VerifiedSchema(Schema):
    """(b2) Fields are written out (so every checker sees them) AND verified
    against a derivation at class-creation time, so drift is an import error."""

    def __init_subclass__(cls, derive: Derivation | None = None, **kw: object) -> None:
        super().__init_subclass__(**kw)
        if derive is not None:
            declared, expected = fields(cls), derive.columns()
            if declared != expected:
                raise TypeError(
                    f"{cls.__name__} does not match {derive.op}({derive.base.__name__}): "
                    f"declared={declared} expected={expected}"
                )
