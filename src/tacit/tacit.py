from dataclasses import dataclass
from typing import Annotated, Any, Sequence, get_origin, get_type_hints

import pandera.polars as pa


# TODO(alvaro): Review this implementation
class Field:
    """A descriptor that represents a schema field, similar to dataclasses.field."""

    def __init__(self, default: Any = None, **metadata: dict[str, Any]):
        self.default = default
        self.metadata = metadata

    def __set_name__(self, owner: type, name: str) -> None:
        """Called when the descriptor is assigned to a class attribute."""
        self.name = name

    def __get__(self, obj: Any, objtype: type = None) -> Any:
        """Return the field name when accessed on the class, metadata when accessed on an instance."""
        if obj is None:
            # Class access: return the field name (for use in pl.col(), etc.)
            return self.name
        else:
            # Instance access: return the field metadata (could be customized)
            return {
                "name": self.name,
                "default": self.default,
                "metadata": self.metadata,
            }

    def __set__(self, obj: Any, value: Any) -> None:
        """Prevent setting field values directly."""
        raise AttributeError(f"Can't set field '{self.name}' directly")

    def __repr__(self) -> str:
        return f"Field(default={self.default!r}, metadata={self.metadata!r})"


@dataclass
class RawField:
    name: str
    typ: type
    extras: Any | None = None


class Schema:
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__()

        # Gather the fields
        cls._fields = {}

        for name, hint in get_type_hints(cls, include_extras=True).items():
            # Extract the typing metadata from Annotated
            if get_origin(hint) is Annotated:
                typ = hint.__origin__
                extras = hint
            else:
                typ = hint
                extras = None

            cls._fields[name] = RawField(
                name=name,
                typ=typ,
                extras=extras,
            )

        # At this point we can create a Pandera schema based on this information

    @classmethod
    def _get_fields(cls):
        return cls._fields


def build_pandera_schema[**P](
    fields: Sequence[RawField], **kwargs: P.kwargs
) -> pa.DataFrameSchema:
    return pa.DataFrameSchema(
        {field.name: pa.Column(field.typ) for field in fields}, **kwargs
    )
