"""Generate p5_perf_frame.py (all schemas' keys as self-typed overloads on ONE frame class) and
p5_perf_schema.py (each schema carries its own overloads, accessed through df.c). N schemas x M columns."""
import sys
from pathlib import Path

N, M = int(sys.argv[1]), int(sys.argv[2])
H = Path(__file__).parent
head = ["# ruff: noqa", "from typing import Generic, Literal, TypeVar, overload, reveal_type", 'S_co = TypeVar("S_co", covariant=True)',
        "class Col[T]: ..."]
frame = head + [f"class S{i}: ..." for i in range(N)] + ["class DF(Generic[S_co]):"]
for i in range(N):
    for j in range(M):
        frame += ["    @overload", f'    def __getitem__(self: "DF[S{i}]", key: Literal["c{i}_{j}"], /) -> Col[int]: ...']
frame += ["    def __getitem__(self, key: str) -> object: ..."]
frame += [f"def use(d{i}: DF[S{i}]) -> None:\n    d{i}['c{i}_{M - 1}']\n    d{i}['c{i}_0']" for i in range(N)]
(H / "p5_perf_frame.py").write_text("\n".join(frame) + "\n")
schema = head + ["class DF(Generic[S_co]):", "    @property", "    def c(self) -> S_co: ..."]
for i in range(N):
    schema += [f"class S{i}:"]
    for j in range(M):
        schema += ["    @overload", f'    def __getitem__(self, key: Literal["c{i}_{j}"], /) -> Col[int]: ...']
    schema += ["    def __getitem__(self, key: str) -> object: ..."]
schema += [f"def use(d{i}: DF[S{i}]) -> None:\n    d{i}.c['c{i}_{M - 1}']\n    d{i}.c['c{i}_0']" for i in range(N)]
(H / "p5_perf_schema.py").write_text("\n".join(schema) + "\n")
