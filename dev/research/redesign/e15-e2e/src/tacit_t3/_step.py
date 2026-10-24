"""Optional `@tacit.step`: runtime boundary checks + step names in errors.

Structure is already guaranteed by construction. `@step` adds, for `DataFrame[S]`
annotations (also `DataFrame[S] | None`, `tuple[...]`, `list[...]`, and TypeVars:
`def f[S: HasTs](df: DataFrame[S]) -> DataFrame[S]` checks the result keeps the
argument's schema):

* a schema check of arguments / return values (for untyped or `Any` callers);
* `validate=True`: the data checks (nulls, uniqueness, constraints; one query per frame);
* error contexts that name the step and argument; other exceptions raised inside the
  step get a note naming it.

Annotations are resolved lazily on the first call (`if TYPE_CHECKING:` imports work).
"""

from __future__ import annotations

import functools
import inspect
import types
from collections.abc import Callable
from typing import Any, TypeVar, Union, get_args, get_origin, get_type_hints, overload

from ._df import DataFrame, Schema, _plain
from ._errors import Issue, ValidationError
from ._validate import parse_table


def _mentions_frame(tp: Any) -> bool:
    if tp is DataFrame or get_origin(tp) is DataFrame:
        return True
    return any(_mentions_frame(a) for a in get_args(tp))


def _registry() -> dict[str, type[Schema]]:
    seen: dict[str, list[type[Schema]]] = {}
    todo: list[type[Schema]] = [Schema]
    while todo:
        for sub in todo.pop().__subclasses__():
            seen.setdefault(sub.__name__, []).append(sub)
            todo.append(sub)
    return {n: cs[0] for n, cs in seen.items() if len(set(cs)) == 1}


class _Checker:
    def __init__(self, fn: Callable[..., Any], validate: bool, name: str) -> None:
        self.fn, self.validate, self.name = fn, validate, name
        self.sig = inspect.signature(fn)
        self.hints: dict[str, Any] | None = None

    def resolve(self) -> dict[str, Any]:
        if self.hints is None:
            try:
                hints = get_type_hints(self.fn)
            except NameError:  # names imported under `if TYPE_CHECKING:` only
                hints = get_type_hints(self.fn, localns=_registry())
            self.hints = {k: v for k, v in hints.items() if _mentions_frame(v)}
        return self.hints

    def check(self, value: Any, tp: Any, where: str, tvars: dict[TypeVar, type[Schema]]) -> None:
        origin = get_origin(tp)
        if origin is DataFrame or tp is DataFrame:
            (s,) = get_args(tp) or (Schema,)
            if isinstance(s, TypeVar):
                if s in tvars:  # e.g. the return value of `def f[S: X](df: DataFrame[S]) -> DataFrame[S]`
                    self._instance(value, tvars[s], where)
                else:
                    self._instance(value, s.__bound__ or Schema, where)
                    tvars[s] = value._schema
            else:
                self._instance(value, s, where)
        elif origin is Union or origin is types.UnionType:
            args = get_args(tp)
            if value is None and type(None) in args:
                return
            errors: list[ValidationError] = []
            for a in (a for a in args if a is not type(None)):
                try:
                    return self.check(value, a, where, tvars)
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

    def _instance(self, value: Any, s: type[Schema], where: str) -> None:
        if not (isinstance(value, DataFrame) and issubclass(value._schema, s)):
            actual = f"DataFrame[{value._schema.__name__}]" if isinstance(value, DataFrame) else type(value).__name__
            if not isinstance(value, DataFrame):
                actual += f" (wrap it with {s.__name__}.parse(...) or {s.__name__}.conform(...))"
            issue = Issue("wrong_frame", expected=f"DataFrame[{s.__name__}]", actual=actual)
            raise ValidationError(s.__name__, f"step {self.name}(), {where}", [issue])
        if self.validate:
            try:
                parse_table(s.__name__, s.__tacit_fields__, _plain(value), extra="ignore", context="validate", coerce=False)
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
            tvars: dict[TypeVar, type[Schema]] = {}
            for pname, value in bound.arguments.items():
                if pname in hints:
                    checker.check(value, hints[pname], f"argument {pname!r}", tvars)
            try:
                result = f(*args, **kwargs)
            except ValidationError as e:
                if e.context.startswith("step "):
                    raise
                raise e.in_step(checker.name) from None
            except Exception as e:
                e.add_note(f"(in tacit step {checker.name}())")
                raise
            if "return" in hints:
                checker.check(result, hints["return"], "return value", tvars)
            return result

        return wrapper

    return deco(fn) if fn is not None else deco
