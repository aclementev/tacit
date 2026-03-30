from __future__ import annotations

from typing import ClassVar, get_origin, get_type_hints

import ibis


class Schema:
    """Base class for tacit schema definitions.

    Subclass and declare columns as annotated class attributes:

        class Iris(Schema):
            sepal_length: float
            species: str
    """

    _fields: ClassVar[dict[str, type]]

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        cls._fields = {
            name: typ
            for name, typ in get_type_hints(cls).items()
            if get_origin(typ) is not ClassVar
        }

    @classmethod
    def _get_fields(cls) -> dict[str, type]:
        return cls._fields

    @classmethod
    def _ibis_schema(cls) -> ibis.Schema:
        return ibis.schema(cls._get_fields())
