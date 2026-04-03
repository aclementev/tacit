from __future__ import annotations

from dataclasses import dataclass

import pandera.ibis as pa

Check = pa.Check


@dataclass(frozen=True)
class Nullable:
    allow: bool = True
