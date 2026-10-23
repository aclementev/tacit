from ibis.common.grounds import Singleton
from typing import Any as Any

__all__ = ['DataShape', 'Scalar', 'Columnar', 'Tabular', 'Any']

class DataShape(Singleton):
    ndim: int
    SCALAR: Scalar
    COLUMNAR: Columnar
    def is_scalar(self) -> bool: ...
    def is_columnar(self) -> bool: ...
    def is_tabular(self) -> bool: ...
    def __lt__(self, other: Any) -> bool: ...
    def __le__(self, other: Any) -> bool: ...
    def __eq__(self, other: Any) -> bool: ...
    def __hash__(self) -> int: ...

class Scalar(DataShape):
    ndim: int

class Columnar(DataShape):
    ndim: int

class Tabular(DataShape):
    ndim: int
