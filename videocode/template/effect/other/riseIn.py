#!/usr/bin/env python3

from __future__ import annotations

from typing import TYPE_CHECKING, Generator, Any
from videocode.constants import *
from videocode.shader.ishader import IShader, Effect
from videocode.shader.vertexShader.opacity import opacity as _opacity
from videocode.shader.vertexShader.position import position as _position
from videocode.utils.bezier import *

if TYPE_CHECKING:
    from videocode.input.input import Input


def riseIn(
    *,
    distance: wnumber = 0.5,
    start: sec = 0,
    duration: sec = 0.6,
    easing: easing = Easing.Out,
) -> Effect:
    """
    Fade the target in while it rises `distance` world units into place — the
    common title entrance.

    The current position is the DESTINATION: the effect starts `distance`
    below it at opacity 0 and ends on it at full opacity. Only the y axis is
    claimed (`position(None, y)`), so a move in x over the same frames still
    applies.

        title.apply(riseIn())
        title.apply(riseIn(distance=1, duration=0.8))
    """

    def _apply(input: Input) -> Generator[IShader, Any, None]:
        dst = input.meta.position.y
        for y, i in easing.rangeIdx(dst - distance, dst, duration):
            yield _position(None, y).at(start=start + i * SINGLE_FRAME)
        for o, i in easing.rangeIdx(0.0, 255.0, duration):
            yield _opacity(o).at(start=start + i * SINGLE_FRAME)

    return _apply
