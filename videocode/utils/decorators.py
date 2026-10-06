#!/usr/bin/env python3

from __future__ import annotations

import functools
import time


from typing import TYPE_CHECKING, Callable, Concatenate, Generic, ParamSpec, TypeVar
from typing_extensions import Self
from videocode.constants import SINGLE_FRAME
from videocode.context import Context
from videocode.ty import *
from videocode.utils.funcutils import upperFirst
from videocode.utils.logger import *
from videocode.shader.vertexShader.hide import hide

if TYPE_CHECKING:
    from videocode.input.input import Input


_P = ParamSpec("_P")
_T = TypeVar("_T", bound="Input")


def inputCreation(f: Callable[Concatenate[_T, _P], None]) -> Callable[Concatenate[_T, _P], None]:
    """
    Automate the `Input` creation.
    """

    @functools.wraps(f)
    def wrapper(self: _T, *args: _P.args, **kwargs: _P.kwargs) -> None:
        # Input's init
        f(self, *args, **kwargs)

        if Context._noRegister:
            return

        # __dict__ order, not cppAttrs order: cppAttrs is a set, and iterating
        # it would reorder the creation args differently on every interpreter
        # start. A `prop` stores under `_name`, so a cppAttr that also has a
        # python-side hook (Polygon.open) is looked up under both spellings and
        # read through the descriptor.
        def cppKey(attr: str) -> str | None:
            if attr in self.cppAttrs:
                return attr
            public = attr[1:]
            return public if attr.startswith("_") and public in self.cppAttrs else None

        creationArgs = {}
        for attr in self.__dict__:
            key = cppKey(attr)
            if key is not None:
                creationArgs[key] = getattr(self, key)

        # Generate the stack creation
        Context.create(
            inputIndex=self.meta.index,
            inputType=self.cppName,
            inputArgs=creationArgs,
        )

        # A `shot()` open around this line collects what the line made, so a
        # `cut` can put the whole of it away later — and every shot around it
        # too, because a shot inside another is part of it.
        for open in Context.openShots:
            open.inputs.append(self)

        if Context._noHiding:
            return

        # If created mid-timeline (after a flush), hide until the current offset
        if Context.waitOffset > 0:
            before = len(Context.statements)
            self.apply(hide(), start=0, offset=0)
            # Bookkeeping, not a call on the person's line: listed as that line's
            # effect it had no name, started at 0, and "play from this line"
            # played the film from the top.
            for statement in Context.statements[before:]:
                statement["placement"] = True
            self._clockTo(Context.waitOffset).show()

    return wrapper


_CLASS_T = TypeVar("_CLASS_T")
_ATTR1_T = TypeVar("_ATTR1_T")
_ATTR2_T = TypeVar("_ATTR2_T")
_ATTR3_T = TypeVar("_ATTR3_T")
_ATTR4_T = TypeVar("_ATTR4_T")


class prop(Generic[_CLASS_T, _ATTR1_T, _ATTR2_T]):
    @overload
    def __init__(self, *, onSet: Callable[[Any], None]) -> None:
        """
        The default `onSet` is made for simple callbacks that do not need to know what value was assigned to the attribute.

        If you want an advanced callback reaction: use `attribute.setter`.
        """
        ...

    @overload
    def __init__(self) -> None: ...

    def __init__(self, *, onSet: Callable[[_CLASS_T], None] | None = None) -> None:
        self.onSet: Callable[[_CLASS_T, _ATTR1_T], None] | None = None if onSet is None else lambda s, _: onSet(s)
        self.onGet: Callable[[_CLASS_T, _ATTR1_T], _ATTR2_T] | None = None
        self.privateName: str = ""

    @overload
    def __call__(self, func: Callable[[], _ATTR3_T], /) -> prop[_CLASS_T, _ATTR3_T, _ATTR3_T]: ...  # stub
    @overload
    def __call__(self, func: Callable[[Any, _ATTR3_T], _ATTR4_T], /) -> prop[_CLASS_T, _ATTR3_T, _ATTR4_T]: ...  # onGet

    def __call__(self, func: Callable) -> Any:
        self.privateName = f"_{func.__name__}"
        isStub = func.__code__.co_argcount == 0
        if not isStub:
            self.onGet = func
        return self

    @overload
    def __get__(self: prop[_CLASS_T, _ATTR1_T, _ATTR2_T], instance: None, owner: type, /) -> prop[_CLASS_T, _ATTR1_T, _ATTR2_T]: ...
    @overload
    def __get__(self: prop[_CLASS_T, _ATTR1_T, _ATTR2_T], instance: Any, owner: type, /) -> _ATTR2_T: ...

    def __get__(self, instance, owner, /):
        attr = object.__getattribute__(instance, self.privateName)
        if self.onGet is not None:
            return self.onGet(instance, attr)
        return attr

    def __set__(self, instance: Any, value: _ATTR1_T, /) -> None:
        isInitialized = hasattr(instance, self.privateName)
        # Skip storage + onSet entirely when the value hasn't changed.
        # Avoids redundant geometry rebuilds (e.g. unchanged chars in textSetter).
        if isInitialized and self.onSet is not None:
            if object.__getattribute__(instance, self.privateName) == value:
                return
        object.__setattr__(instance, self.privateName, value)
        if isInitialized and self.onSet is not None:
            self.onSet(instance, value)

    def setter(self, onSet: Callable[[_CLASS_T, _ATTR1_T], None], /) -> Self:
        self.onSet = onSet
        return self


class propagate(prop[_CLASS_T, _ATTR1_T, _ATTR2_T]):
    """
    Like prop, but also broadcasts the new value down to all children on set.
    Pass `after=lambda self: ...` to run a callback on the parent after the broadcast.
    """

    def __init__(self, func: Callable[[], _CLASS_T] | None = None, /, *, after: Callable[[Any], None] | None = None):
        super().__init__()
        self._after = after
        if func is not None:
            self.__call__(func)

    def __call__(self, func: Callable[[], _CLASS_T]) -> Any:
        super().__call__(func)
        attr = func.__name__
        after = self._after

        def callback(instance, value):
            instance.broadcast(lambda self: self.broadcast(lambda self: setattr(self, attr, value)))
            if after is not None:
                after(instance)

        self.onSet = callback
        return self


if __name__ == "__main__":
    print(locals())
    # print(globals())
