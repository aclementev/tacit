"""One exception type, a list of structured issues (pydantic-style `.issues`)."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal

IssueCode = Literal[
    "missing_column",  # declared column absent from the table / constructor call
    "extra_column",  # undeclared column (only where extras are forbidden)
    "dtype",  # column has an incompatible ibis dtype
    "coercion",  # parse could not convert values to the declared dtype
    "null",  # NULLs in a non-nullable column
    "constraint",  # a field constraint (ge, isin, pattern, ...) failed
    "unique",  # duplicate values in a unique column
    "wrong_frame",  # @step: argument/return is not an instance of the annotated Frame
    "not_a_reduction",  # aggregate(by=...): a non-key value is not a reduction
    "relation",  # expressions from several tables, or not derived from the base frame
]

SAMPLE_LIMIT = 5


@dataclass(frozen=True)
class Issue:
    code: IssueCode
    column: str | None = None
    expected: str | None = None
    actual: str | None = None
    count: int | None = None  # number of failing rows (data checks)
    samples: tuple[object, ...] = ()  # first failing values (data checks)
    detail: str | None = None

    def describe(self) -> str:
        where = f"{self.column}: " if self.column else ""
        parts: list[str] = []
        if self.code == "missing_column":
            parts.append("missing column" + (f" (expected {self.expected})" if self.expected else ""))
        elif self.code == "extra_column":
            parts.append("unexpected column" + (f" ({self.actual})" if self.actual else ""))
        elif self.code == "dtype":
            parts.append(f"expected dtype {self.expected}, got {self.actual}")
        elif self.code == "coercion":
            parts.append(f"cannot convert {self.actual} to {self.expected}")
        elif self.code == "null":
            parts.append("NULL in a non-nullable column (declare `Column[T | None]` to allow it)")
        elif self.code == "constraint":
            parts.append(f"constraint {self.expected} failed")
        elif self.code == "unique":
            parts.append("duplicate values in a unique column")
        else:
            parts.append(self.code.replace("_", " "))
            if self.expected:
                parts.append(f"expected {self.expected}")
            if self.actual:
                parts.append(f"got {self.actual}")
        if self.count is not None:
            parts.append(f"{self.count} row{'s' if self.count != 1 else ''}")
        if self.samples:
            parts.append(f"e.g. {list(self.samples)!r}")
        if self.detail:
            parts.append(self.detail)
        return where + "; ".join(parts)


@dataclass(eq=False)
class ValidationError(Exception):
    """Raised by parse / cast / construction / extend / join / @step.

    `schema` is the Frame class name, `context` says where it happened
    (`"Orders.parse"`, `"NetOrders(...)"`, `"step clean_orders(), argument 'orders'"`),
    `issues` is the full list (never just the first problem).
    """

    schema: str
    context: str
    issues: list[Issue] = field(default_factory=list)

    def __post_init__(self) -> None:
        super().__init__(self.message())

    def message(self) -> str:
        n = len(self.issues)
        head = f"{self.context}: {n} issue{'s' if n != 1 else ''} for {self.schema}"
        return head + "".join(f"\n  - {i.describe()}" for i in self.issues)

    def __str__(self) -> str:
        return self.message()

    def in_step(self, step: str, where: str | None = None) -> ValidationError:
        """Copy of this error whose context names the @step (and the argument)."""
        ctx = f"step {step}()" + (f", {where}" if where else "") + f": {self.context}"
        return replace(self, context=ctx)

    def codes(self) -> list[str]:
        return [i.code for i in self.issues]
