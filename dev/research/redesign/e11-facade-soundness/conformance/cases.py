"""Conformance cases: every facade method/operator x value family x nullability x container.

A case is an expression template over:
  x   the receiver: Column[F] / Column[F | None] / Scalar[F] / Scalar[F | None]
  y   another Column[F] (non-null), yn a Column[F | None]
  {L} {L2}  literals of the receiver family
The full cross product is generated on purpose: wrong-family calls must be
rejected statically exactly when ibis rejects them at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass

FAMS = ["bool", "int", "float", "Decimal", "str", "datetime", "date", "time"]
LIT = {
    "bool": ("True", "False"),
    "int": ("2", "5"),
    "float": ("2.5", "7.5"),
    "Decimal": ('Decimal("2.5")', 'Decimal("7.5")'),
    "str": ('"a"', '"m"'),
    "datetime": ("datetime(2024, 1, 2, 3, 4, 5)", "datetime(2024, 6, 1)"),
    "date": ("date(2024, 1, 2)", "date(2024, 6, 1)"),
    "time": ("time(1, 2, 3)", "time(12, 0)"),
}

GENERIC = [
    # null handling / naming / ordering / windows
    "x.isnull()", "x.notnull()", 'x.name("r")', "x.asc()", "x.desc()", "x.over(group_by=y)",
    # reductions
    "x.count()", "x.nunique()", "x.min()", "x.max()", "x.first()", "x.value_counts()", "x.topk(2)",
    "x.sum()", "x.mean()", "x.std()", "x.var()", "x.median()",
    # numeric
    "x.ceil()", "x.floor()", "x.abs()", "x.clip(lower={L}, upper={L2})", "x.clip(lower=0.5)",
    "x.round()", "x.round(1)",
    # strings
    "x.length()", 'x.contains("a")', 'x.startswith("a")', 'x.endswith("a")', 'x.re_search("a")',
    "x.upper()", "x.lower()", "x.strip()", 'x.replace("a", "b")', "x.substr(0, 2)",
    'x.re_extract("(a)", 1)',
    # temporal
    "x.year()", "x.month()", "x.day()", "x.hour()", "x.date()", 'x.strftime("%Y")',
    "x.epoch_seconds()", 'x.truncate("D")', 'x.truncate("h")',
    # boolean
    "x.ifelse(1, 2)", 'x.ifelse("a", "b")', "x.any()", "x.all()",
    # cast / try_cast
    "x.cast(int)", "x.cast(float)", "x.cast(str)", "x.cast(Decimal)", "x.cast(bool)", "x.cast(date)",
    "x.cast(datetime)", 'x.cast("float64")', 'x.cast("int64")', 'x.cast("string")',
    'x.cast("timestamp")', 'x.cast("date")', 'x.cast("decimal(10, 2)")',
    "x.try_cast(int)", 'x.try_cast("float64")', "x.try_cast(str)",
    # null filling / membership / ranges
    "x.fill_null({L})", "x.fill_null(y)", "x.fill_null(0)", "x.fill_null(1.5)", 'x.fill_null("a")',
    "x.isin([{L}])", "x.notin([{L}])", "x.isin(y)", "x.between({L}, {L2})",
]
ARITH = ["+", "-", "*", "/", "//", "%"]
CMP = ["<", "<=", ">", ">=", "==", "!="]
BOOL = ["&", "|", "^"]


def templates() -> list[str]:
    out = list(GENERIC)
    for op in ARITH:
        out += [f"x {op} {{L}}", f"{{L}} {op} x", f"x {op} y", f"x {op} yn", f"x {op} x",
                f"x {op} 1", f"x {op} 1.5", f'x {op} "a"', f"x {op} None"]
    for op in CMP:
        out += [f"x {op} {{L}}", f"x {op} y", f"x {op} yn", f'x {op} "2024-01-01"', f"x {op} 1"]
    for op in BOOL:
        out += [f"x {op} True", f"x {op} y", f"x {op} yn"]
    out += ["~x", "-x"]
    return out


@dataclass(frozen=True)
class Case:
    id: str
    template: str
    fam: str
    nullable: bool
    container: str  # "Column" | "Scalar"

    @property
    def expr(self) -> str:
        l1, l2 = LIT[self.fam]
        return self.template.replace("{L}", l1).replace("{L2}", l2)

    @property
    def x_type(self) -> str:
        return f"{self.container}[{self.fam}{' | None' if self.nullable else ''}]"


def all_cases() -> list[Case]:
    out = []
    i = 0
    for tpl in templates():
        for container in ("Column", "Scalar"):
            for fam in FAMS:
                for nullable in (False, True):
                    i += 1
                    out.append(Case(f"c{i:05d}", tpl, fam, nullable, container))
    return out


if __name__ == "__main__":
    cs = all_cases()
    print(len(templates()), "templates,", len(cs), "cases")
