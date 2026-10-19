"""@step with annotations only importable under TYPE_CHECKING (resolved lazily)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import tacit_next as tc

if TYPE_CHECKING:
    from test_runtime import Orders


@tc.step
def passthrough(o: Orders) -> Orders:
    return o
