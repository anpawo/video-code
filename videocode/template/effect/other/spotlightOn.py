#!/usr/bin/env python3

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generator

from videocode.constants import *
from videocode.shader.fragmentShader.spotlight import spotlight as _spotlight
from videocode.shader.ishader import Effect, IShader
from videocode.template.effect.ramp import dipAndReturn
from videocode.utils.bezier import *

if TYPE_CHECKING:
    from videocode.input.input import Input


def spotlightOn(
    *,
    x: number = 0.5,
    y: number = 0.5,
    radius: ufloat = 0.16,
    softness: ufloat = 0.09,
    darkness: number = 0.72,
    start: sec = 0,
    duration: sec = 2.0,
    fade: sec = 0.35,
) -> Effect:
    """
    Dim everything but a round pool of light around one spot, then let it go.
    The pointer that does not draw anything on the image.

    `x`/`y` are in **frame UV** (0-1, y downward) — where the spot is ON
    SCREEN, not where it is in the media. That is a different space from
    `zoomTo`'s media fractions, and on purpose: a spotlight is a lighting
    decision about the finished frame, so it stays put when the media moves
    under it. With the media untransformed the two spaces coincide.

    `radius` is a fraction of the frame HEIGHT, so the pool stays round
    whatever the aspect ratio.

        clip.apply(spotlightOn(x=0.42, y=0.61))
        clip.apply(spotlightOn(x=0.2, y=0.5, radius=0.3, darkness=0.9))
    """
    # Round in PIXELS, not in UV: a circle of equal UV radius is an ellipse
    # on a 16:9 frame. The conversion happens here, where the resolution is
    # known, so the GLSL never needs the aspect ratio.
    width = 2 * radius * SCREEN_HEIGHT / SCREEN_WIDTH
    height = 2 * radius

    def _apply(_input: Input) -> Generator[IShader, Any, None]:
        for d, t in dipAndReturn(peak=darkness, start=start, duration=duration, fade=fade):
            yield _spotlight(
                x=x, y=y, width=width, height=height,
                corner=1.0, softness=softness, darkness=d,
            ).at(start=t)

    return _apply


def zoneFocus(
    *,
    x: number = 0.5,
    y: number = 0.5,
    width: ufloat = 0.3,
    height: ufloat = 0.3,
    corner: number = 0.25,
    softness: ufloat = 0.03,
    darkness: number = 0.68,
    start: sec = 0,
    duration: sec = 2.0,
    fade: sec = 0.3,
) -> Effect:
    """
    `spotlightOn` for a rectangular area — a panel, a column of numbers, a
    board. Same shader, hard edges: `corner=0` is a plain rectangle, `1` a
    stadium.

    `width`/`height` are fractions of the frame's width and height; `x`/`y`
    the centre, in frame UV.

        clip.apply(zoneFocus(x=0.75, y=0.4, width=0.4, height=0.55))
    """

    def _apply(_input: Input) -> Generator[IShader, Any, None]:
        for d, t in dipAndReturn(peak=darkness, start=start, duration=duration, fade=fade):
            yield _spotlight(
                x=x, y=y, width=width, height=height,
                corner=corner, softness=softness, darkness=d,
            ).at(start=t)

    return _apply
