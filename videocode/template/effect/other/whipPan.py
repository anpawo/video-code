#!/usr/bin/env python3

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generator

from videocode.constants import *
from videocode.shader.fragmentShader.blur import blur as _blur
from videocode.shader.ishader import Effect, IShader
from videocode.shader.vertexShader.position import position as _position
from videocode.shader.vertexShader.scale import scale as _scale
from videocode.template.effect.framing import framePosition
from videocode.utils.bezier import *

if TYPE_CHECKING:
    from videocode.input.input import Input


def whipPan(
    *,
    toX: number = 0.5,
    toY: number = 0.5,
    zoom: number = 1.0,
    blur: unumber = 9,
    start: sec = 0,
    duration: sec = 0.4,
) -> Effect:
    """
    Whip pan: throw the frame across to another point of the media fast
    enough to smear, then stop dead on it. The transition that hides a cut
    inside the motion.

    Destination coordinates are fractions of the input's own box, as in
    `zoomTo`.

    APPROXIMATION, deliberately: a real whip pan smears ALONG the direction
    of travel, and videocode's `blur` is an isotropic gaussian — there is no
    directional blur shader in the repo. The smear here is a symmetric blur
    that peaks mid-throw and is gone on the last frame. At `duration <= 0.4s`
    it reads as a whip; slow it down and it reads as a blurry pan, because
    that is what it is. A true motion blur wants its own shader.

        clip.apply(whipPan(toX=0.85, toY=0.3))
        clip.apply(whipPan(toX=0.1, toY=0.5, zoom=1.4, blur=14))
    """

    def _apply(input: Input) -> Generator[IShader, Any, None]:
        srcScale = v2(*input.meta.scale)
        srcPos = v2(*input.meta.position)
        dstPos = framePosition(input, toX, toY, zoom)
        if zoom != 1:
            yield _scale(*(srcScale * zoom)).at(start=start)

        n = max(int(duration * FRAMERATE), 2)
        for p, i in Easing.InOut.rangeIdx(srcPos, dstPos, duration):
            t = i / (n - 1) if n > 1 else 1.0
            yield _position(*p).at(start=start + i * SINGLE_FRAME)
            # Triangle envelope: sharp at both ends, smeared in the middle.
            # `blur(0)` is a wasted full-screen pass, so skip the tails.
            amount = blur * (1.0 - abs(2.0 * t - 1.0))
            if amount >= 0.5:
                yield _blur(amount).at(start=start + i * SINGLE_FRAME)

    return _apply
