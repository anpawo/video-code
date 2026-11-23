#!/usr/bin/env python3

from __future__ import annotations

from typing import TYPE_CHECKING, Generator, Any
from videocode.constants import *
from videocode.shader.ishader import IShader, Effect
from videocode.shader.vertexShader.opacity import opacity as _opacity

if TYPE_CHECKING:
    from videocode.input.input import Input


def blink(
    *,
    times: int = 3,
    start: sec = 0,
    duration: sec = 1.5,
) -> Effect:
    """
    Blink the target: its opacity snaps to 0 and back, `times` times over
    `duration` seconds, and it ends visible at the opacity it had before —
    a cursor, a warning, a "recording" dot.

        cursor.apply(blink())
        dot.apply(blink(times=5, duration=2))
    """

    def _apply(input: Input) -> Generator[IShader, Any, None]:
        on = input.meta.opacity
        per = duration / times
        for r in range(times):
            at = start + r * per
            yield _opacity(0).at(start=at)
            yield _opacity(on).at(start=at + max(per / 2, SINGLE_FRAME))

    return _apply
