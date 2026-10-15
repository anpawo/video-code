#!/usr/bin/env python3

from __future__ import annotations

from videocode.shader.ishader import FragmentShader
from videocode.ty import number, ufloat


class spotlight(FragmentShader):
    """
    Dim the frame everywhere except a pool of light — the "look here" grade.

    Unlike `vignette`, which is measured against the input's own bounding
    box, this one is placed in **frame UV**: `(0, 0)` is the top-left of the
    frame and `(1, 1)` the bottom-right, whatever the mesh underneath. That
    is what makes it usable as a generic pointer — a caller says "light the
    spot 42% across and 61% down" without knowing how the media is framed.

    - `x`, `y`: centre of the pool, in frame UV (0-1, y downward).
    - `width`: full width of the pool, as a fraction of the frame width.
    - `height`: full height of the pool, as a fraction of the frame height.
    - `corner`: 0 = hard rectangle, 1 = fully rounded (stadium/ellipse).
    - `softness`: falloff width past the edge, in UV units.
    - `darkness`: how far down the outside is pushed (0 = no dimming,
      1 = black).

    Prefer the `spotlightOn` / `zoneFocus` templates over calling this
    directly: they animate the dimming in and out and take a round radius.

        video.apply(spotlight(x=0.42, y=0.61, width=0.2, height=0.34))
    """

    def __init__(
        self,
        x: number = 0.5,
        y: number = 0.5,
        width: ufloat = 0.3,
        height: ufloat = 0.3,
        corner: number = 1.0,
        softness: ufloat = 0.06,
        darkness: number = 0.7,
    ):
        # NOTE: the GLSL reads these ALPHABETICALLY by attribute name —
        # centerX, centerY, corner, darkness, halfHeight, halfWidth,
        # softness. Renaming any of them silently reshuffles p[].
        self.centerX = x
        self.centerY = y
        self.corner = corner
        self.darkness = darkness
        self.halfHeight = height / 2
        self.halfWidth = width / 2
        self.softness = softness
