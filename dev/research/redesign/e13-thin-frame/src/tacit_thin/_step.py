"""Optional `@tc.step`: runtime boundary checks + step names in errors.

Structure is already guaranteed by construction (a function returning `NetOrders`
can only return something built by NetOrders(...)/extend/cast/parse). `@step` adds:

* nominal isinstance checks of arguments / return values against Frame annotations,
  including `F | None`, TypeVars bound to frames (`def f[F: HasTs](df: F) -> F`
  also checks the result is an instance of the *argument's* class), `tuple[A, B]`,
  `list[A]`; annotations it cannot enforce raise instead of being skipped;
* `validate=True`: data checks (parse) on every frame argument and on the result;
* error contexts that name the step and argument.

Annotations are resolved lazily on the first call, so `if TYPE_CHECKING:` imports
and forward references work.
"""

from __future__ import annotations

import functools
import inspect
import types
from collections.abc import Callable
from typing import Any, TypeVar, Union, get_args, get_origin, get_type_hints, overload

from ._errors import Issue, ValidationError
from ._frame import Frame, as_table
from ._validate import parse_table


def _mentions_frame(tp: Any) -> bool:
    if isinstance(tp, type):
        return issubclass(tp, Frame)
    if isinstance(tp, TypeVar):
        return _mentions_frame(tp.__bound__)
    return any(_mentions_frame(a) for a in get_args(tp))


def _frame_registry() -> dict[str, type[Frame]]:
    seen: dict[str, list[type[Frame]]] = {}
    todo: list[type[Frame]] = [Frame]
    while todo:
        c = todo.pop()
        for sub in c.__subclasses__():
            seen.setdefault(sub.__name__, []).append(sub)
            todo.append(sub)
    return {n: cs[0] for n, cs in seen.items() if len(set(cs)) == 1}


class _Checker:
    def __init__(self, fn: Callable[..., Any], validate: bool, name: str) -> None:
        self.fn = fn
        self.validate = validate
        self.name = name
        self.sig = inspect.signature(fn)
        self.hints: dict[str, Any] | None = None

    def resolve(self) -> dict[str, Any]:
        if self.hints is None:
            try:
                hints = get_type_hints(self.fn)
            except NameError:
                # Names imported only under `if TYPE_CHECKING:` never exist at runtime;
                # fall back to the registry of Frame classes (unambiguous class names only).
                hints = get_type_hints(self.fn, localns=_frame_registry())
            self.hints = {k: v for k, v in hints.items() if _mentions_frame(v)}
        return self.hints

    def check(self, value: Any, tp: Any, where: str, tvars: dict[TypeVar, type]) -> None:
        origin = get_origin(tp)
        if isinstance(tp, type) and issubclass(tp, Frame):
            self._instance(value, tp, where)
        elif isinstance(tp, TypeVar):
            bound = tp.__bound__
            if tp in tvars:  # e.g. the return value of `def f[F: X](df: F) -> F`
                self._instance(value, tvars[tp], where)
            else:
                if bound is not None:
                    self.check(value, bound, where, tvars)
                if isinstance(value, Frame):
                    tvars[tp] = type(value)
        elif origin is Union or origin is types.UnionType:
            args = get_args(tp)
            if value is None and type(None) in args:
                return
            frames = [a for a in args if a is not type(None)]
            errors: list[ValidationError] = []
            for a in frames:
                try:
                    self.check(value, a, where, tvars)
                    return
                except ValidationError as e:
                    errors.append(e)
            raise errors[0]
        elif origin in (tuple, list) and isinstance(value, origin):
            args = get_args(tp)
            if origin is tuple and not (len(args) == 2 and args[1] is Ellipsis):
                for i, (v, a) in enumerate(zip(value, args, strict=True)):
                    self.check(v, a, f"{where}[{i}]", tvars)
            else:
                for i, v in enumerate(value):
                    self.check(v, args[0], f"{where}[{i}]", tvars)
        else:
            raise TypeError(f"@step {self.name}: cannot enforce annotation {tp!r} on {where}")

    def _instance(self, value: Any, cls: type[Frame], where: str) -> None:
        if not isinstance(value, cls):
            actual = type(value).__name__
            hint = " (a raw ibis Table: wrap it with .parse()/.conform())" if not isinstance(value, Frame) else ""
            issue = Issue("wrong_frame", expected=cls.__name__, actual=actual + hint)
            raise ValidationError(cls.__name__, f"step {self.name}(), {where}", [issue])
        if self.validate:
            try:
                parse_table(cls.__name__, cls.__tacit_fields__, as_table(value), extra="ignore", context="validate", coerce=False)
            except ValidationError as e:
                raise e.in_step(self.name, where) from None


@overload
def step[**P, R](fn: Callable[P, R], /) -> Callable[P, R]: ...
@overload
def step[**P, R](*, validate: bool = False, name: str | None = None) -> Callable[[Callable[P, R]], Callable[P, R]]: ...
def step(fn: Any = None, /, *, validate: bool = False, name: str | None = None) -> Any:
    """Decorate a pipeline step. Signature-preserving (ParamSpec), so checkers see the original."""

    def deco(f: Callable[..., Any]) -> Callable[..., Any]:
        checker = _Checker(f, validate, name or f.__qualname__)

        @functools.wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            hints = checker.resolve()
            bound = checker.sig.bind(*args, **kwargs)
            tvars: dict[TypeVar, type] = {}
            for pname, value in bound.arguments.items():
                if pname in hints:
                    checker.check(value, hints[pname], f"argument {pname!r}", tvars)
            try:
                result = f(*args, **kwargs)
            except ValidationError as e:
                if e.context.startswith("step "):
                    raise
                raise e.in_step(checker.name) from None
            if "return" in hints:
                checker.check(result, hints["return"], "return value", tvars)
            return result

        return wrapper

    return deco(fn) if fn is not None else deco
