#!/usr/bin/env python3

from __future__ import annotations

import time


from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Generic, Self, cast, overload
from typing_extensions import TypeVar
from videocode.constants import DEBUG, SINGLE_FRAME
from videocode.ty import frame, maybe

if TYPE_CHECKING:
    from videocode.ty import sec
    from videocode.input.input import Input


class AttributeNameReference:
    """
    Prevent Attribute Name Missmatch
    """

    def __init__(self): ...

    def __getattribute__(self, name: str) -> str:
        return name


_MAYBE_T_VAL = TypeVar("_MAYBE_T_VAL")
_MAYBE_T_RET = TypeVar("_MAYBE_T_RET")


class Maybe(Generic[_MAYBE_T_VAL]):
    """
    Prevent `None` checks.

    Like `Value or Default` but only truthy if `value is None`.

    Examples:
    ---
    >>> Maybe(value) | defaultValue
    >>> Maybe(value).map(func).get()
    >>> Maybe(value).map(func).orElse(defaultValue)
    """

    def __init__(self, value: _MAYBE_T_VAL | None) -> None:
        self.value = value

    @overload
    def __or__(self, default: _MAYBE_T_VAL) -> _MAYBE_T_VAL: ...
    @overload
    def __or__(self, default: None) -> None: ...
    def __or__(self, default: _MAYBE_T_VAL | None) -> _MAYBE_T_VAL | None:
        if self.value is None:
            return default
        return self.value

    def map(self, func: Callable[[_MAYBE_T_VAL], _MAYBE_T_RET]) -> Maybe[_MAYBE_T_RET]:
        if self.value is None:
            return Maybe(None)
        return Maybe(func(self.value))

    def get(self) -> _MAYBE_T_VAL | None:
        return self.value

    def orElse(self, default: _MAYBE_T_VAL) -> _MAYBE_T_VAL:
        return self | default


_AT_T = TypeVar("_AT_T", default=Any)


class _Over:
    """
    Runtime proxy returned by Input.over(). Pyright sees over() as returning
    Self, so attribute assignment is type-checked against the real Input subclass
    and gets full IDE autocomplete — no string references needed.

        rect.over(duration=0.6).fillColor = RED_B
    """

    __slots__ = ("_input", "_easing", "_start", "_duration", "_offset")

    def __init__(self, input: Input, *, easing: Any, start: float, duration: float, offset: Any) -> None:
        object.__setattr__(self, "_input", input)
        object.__setattr__(self, "_easing", easing)
        object.__setattr__(self, "_start", start)
        object.__setattr__(self, "_duration", duration)
        object.__setattr__(self, "_offset", offset)

    #: The verb that means what the assignment meant. `over()` animates a
    #: VALUE, and half of what an author reaches for — opacity, position,
    #: scale, rotation — is a verb on `Input`, not a field. Assigning to one
    #: used to die thirty frames deep in the easing with
    #: `unsupported operand type(s) for -: 'int' and 'method'`, which names
    #: neither the attribute nor the way to do it.
    _VERBS = {
        "opacity": "fadeTo(dst=…), or fadeIn() / fadeOut()",
        "position": "moveTo(x=…, y=…)",
        "scale": "scaleTo(…)",
        "rotation": "rotateTo(…)",
        "align": "alignTo(x=…, y=…)",
        "zIndex": "zIndex(…)",
    }

    def __setattr__(self, name: str, value: Any) -> None:
        inp: Input = object.__getattribute__(self, "_input")

        if callable(getattr(inp, name, None)):
            raise TypeError(
                f"{type(inp).__name__}.{name} is a verb, not a value — over() cannot "
                f"assign to it. Write {_Over._VERBS.get(name, name + '(…)')} instead."
            )

        inp.ease(
            name,
            value,
            easing=object.__getattribute__(self, "_easing"),
            start=object.__getattribute__(self, "_start"),
            duration=object.__getattribute__(self, "_duration"),
            offset=object.__getattribute__(self, "_offset"),
        )


class At(Generic[_AT_T]):
    def __new__(cls, *args, **kwargs) -> _AT_T:
        return cast(_AT_T, super().__new__(cls))

    def __init__(self, start: sec, duration: sec = SINGLE_FRAME, offset: maybe[frame] = None) -> None:
        self.value: _AT_T = cast(_AT_T, None)
        self.start = start
        self.duration = duration
        self.offset = offset

    def __rmatmul__(self, value: _AT_T) -> _AT_T:
        """
        Clean way to use `At`.

        `value @ At(start, duration, offset)`
        """
        self.value = value
        return cast(_AT_T, self)

    def __or__(self, value: _AT_T) -> _AT_T:
        """
        Second way to use `At` if `__matmul__` is defined on the type of `value`.

        `At(start, duration, offset) | value`
        """
        self.value = value
        return cast(_AT_T, self)

    def unpack(self) -> tuple[_AT_T, sec, sec, maybe[frame]]:
        return self.value, self.start, self.duration, self.offset

