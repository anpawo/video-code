#!/usr/bin/env python3

from __future__ import annotations

import math

from typing import TYPE_CHECKING, Any, Generator

from videocode.constants import *
from videocode.shader.ishader import Effect, IShader
from videocode.shader.vertexShader.position import position as _position
from videocode.shader.vertexShader.scale import scale as _scale
from videocode.template.effect.framing import framePosition
from videocode.utils.bezier import *

if TYPE_CHECKING:
    from videocode.input.input import Input


def impact(
    *,
    x: maybe[number] = None,
    y: maybe[number] = None,
    zoom: number = 1.16,
    amplitude: wnumber = 0.09,
    frequency: number = 20,
    start: sec = 0,
    duration: sec = 0.7,
) -> Effect:
    """
    The hit: a fast punch in, a damped rumble, and back. What `zoomPunch` and
    `shake` do separately — together, because on a capture they are one beat
    and two effects fighting over `position` would overwrite each other.

    Give `x`/`y` (fractions of the input's box, as in `zoomTo`) to punch
    TOWARD a point; leave them out to punch in place. Either way the input
    ends exactly where it started.

    The rumble is a decaying sine, not noise — deterministic, so a `Group`
    shakes rigidly and a visual golden stays reproducible.

        clip.apply(impact())
        clip.apply(impact(x=0.42, y=0.61, zoom=1.3, amplitude=0.15))
    """

    def _apply(input: Input) -> Generator[IShader, Any, None]:
        srcScale = v2(*input.meta.scale)
        srcPos = v2(*input.meta.position)
        peakScale = srcScale * zoom
        peakPos = framePosition(input, x, y, zoom) if x is not None and y is not None else srcPos

        up = max(duration * 0.22, SINGLE_FRAME * 2)
        down = max(duration - up, SINGLE_FRAME * 2)

        # The rumble is a decaying sine on `position`, which is what `shake`
        # already is — but `shake` cannot be composed in here: it writes
        # position as an offset from where the input STANDS, and the two
        # would fight over the one channel (last writer wins). `impact`'s
        # rumble has to ride on a base that is itself moving toward the
        # point, so the sine is folded into that base below rather than
        # posed separately. Same maths, different anchor.
        #
        # --- attack: snap up, rumbling ---
        n = max(int(up * FRAMERATE), 2)
        for s, i in Easing.Exponential.rangeIdx(srcScale, peakScale, up):
            t = i / (n - 1) if n > 1 else 1.0
            base = srcPos + (peakPos - srcPos) * t
            angle = 2 * math.pi * frequency * t * up
            yield _scale(*s).at(start=start + i * SINGLE_FRAME)
            yield _position(
                base.x + amplitude * math.sin(angle),
                base.y + amplitude * math.cos(angle) * 0.6,
            ).at(start=start + i * SINGLE_FRAME)

        # --- release: settle back with the rumble dying out ---
        m = max(int(down * FRAMERATE), 2)
        for s, i in Easing.Back.rangeIdx(peakScale, srcScale, down):
            t = i / (m - 1) if m > 1 else 1.0
            base = peakPos + (srcPos - peakPos) * t
            envelope = (1.0 - t) ** 2
            angle = 2 * math.pi * frequency * t * down
            yield _scale(*s).at(start=start + up + i * SINGLE_FRAME)
            yield _position(
                base.x + amplitude * math.sin(angle) * envelope,
                base.y + amplitude * math.cos(angle) * 0.6 * envelope,
            ).at(start=start + up + i * SINGLE_FRAME)

        # A decaying sine does not land on zero: pin the last frame back on
        # the exact starting framing, or the input keeps the residual offset
        # for the rest of the video.
        yield _position(*srcPos).at(start=start + duration)
        yield _scale(*srcScale).at(start=start + duration)

    return _apply
