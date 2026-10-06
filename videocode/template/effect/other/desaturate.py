#!/usr/bin/env python3

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generator

from videocode.constants import *
from videocode.shader.fragmentShader.grayscale import grayscale as _grayscale
from videocode.shader.ishader import Effect, IShader
from videocode.template.effect.ramp import dipAndReturn
from videocode.utils.bezier import *

if TYPE_CHECKING:
    from videocode.input.input import Input


def desaturate(
    *,
    amount: number = 1.0,
    start: sec = 0,
    duration: sec = 2.0,
    fade: sec = 0.4,
) -> Effect:
    """
    Drain the colour out and let it come back — the "this is a memory" /
    "this one hurt" grade. `amount=1` goes fully black and white.

    Set `fade` to half of `duration` (or more) for a straight dip with no
    hold.

        clip.apply(desaturate())
        clip.apply(desaturate(amount=0.6, duration=3, fade=1))
    """

    def _apply(_input: Input) -> Generator[IShader, Any, None]:
        for v, t in dipAndReturn(peak=amount, start=start, duration=duration, fade=fade):
            # Below 1 % the grey grade cannot be told from the image: no
            # point posing a shader for nothing.
            if v > 0.01:
                yield _grayscale(v).at(start=t)

    return _apply
