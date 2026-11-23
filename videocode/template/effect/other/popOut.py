#!/usr/bin/env python3

from __future__ import annotations

from typing import TYPE_CHECKING, Generator, Any
from videocode.constants import *
from videocode.shader.ishader import IShader, Effect
from videocode.shader.vertexShader.hide import hide as _hide
from videocode.shader.vertexShader.scale import scale as _scale
from videocode.utils.bezier import *

if TYPE_CHECKING:
    from videocode.input.input import Input


def popOut(
    *,
    start: sec = 0,
    duration: sec = 0.5,
    easing: easing = Easing.Back,
) -> Effect:
    """
    Pop the target out — `popIn` played backwards: it grows a little past its
    current size (~10% with `Easing.Back`), then shrinks to 0, and stays
    hidden afterwards (`hide()` is emitted at `start + duration`).

    - `easing`: the entrance curve to reverse; `Easing.Elastic` wobbles before
      it collapses.

        rect.apply(popOut())
        title.apply(popOut(duration=0.4))
    """

    def _apply(input: Input) -> Generator[IShader, Any, None]:
        size = v2(*input.meta.scale)
        # The entrance curve 0 -> size, read backwards: the overshoot it ends
        # on becomes the anticipation the exit starts with.
        frames = [s for s, _ in easing.rangeIdx(size * 0, size, duration)]
        for i, s in enumerate(reversed(frames)):
            yield _scale(*s).at(start=start + i * SINGLE_FRAME)
        yield _hide().at(start=start + duration)

    return _apply
