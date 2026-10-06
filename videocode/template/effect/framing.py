#!/usr/bin/env python3

from __future__ import annotations

#
# Shared geometry for the camera-move templates (punchIn, travelling,
# zoomTo, snapZoom, impact, whipPan).
#
# There is no camera in videocode: a "camera move" is the media moving and
# scaling under a fixed frame. Every one of those templates therefore needs
# the same two answers, and they are easy to get subtly wrong, so they live
# here once.
#
#   1. How big is this input's own box, in world units?
#   2. Where must the input sit so that a given point of it lands dead
#      centre of the frame, at a given zoom?
#
# `containSize` is the third question, asked BEFORE any camera move: how big
# must the media be to fit the frame at all.
#
# Coordinates are FRACTIONS of the input's own box — (0, 0) top-left,
# (1, 1) bottom-right, y downward, like every image editor. That keeps the
# templates media-agnostic: "zoom on 0.42 / 0.61" means the same thing for a
# 1322x1526 screen capture and for a 4K drone shot. Turning a domain
# coordinate (a chess square, a face, a UI button) into that fraction is the
# CALLER's job, and deliberately so — videocode knows nothing about chess.
#

from typing import TYPE_CHECKING

from videocode.constants import WORLD_HEIGHT, WORLD_WIDTH
from videocode.ty import number, v2

if TYPE_CHECKING:
    from videocode.input.input import Input


def mediaBox(input: Input) -> v2[number, number]:
    """
    The input's UNSCALED size in world units — what one "fraction of the
    media" is worth before `meta.scale` is applied.

    Three sources, in order of trust: the bounding box of the vertices (any
    `Polygon`, `Video` and `Image` included), then an explicit
    `width`/`height`, then the world box itself — the sane fallback for a
    full-frame element such as an `AdjustmentLayer`, which has no geometry
    of its own but covers exactly the frame.

    The vertices come first because a shape's `width` is what is DRAWN,
    already times `meta.scale`: read from it, `framePosition` counted the
    scale twice on any shape not at scale 1.
    """
    vertices = getattr(input, "vertices", None)
    if vertices:
        xs = [p[0] for p in vertices]
        ys = [p[1] for p in vertices]
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        if w > 0 and h > 0:
            return v2(float(w), float(h))

    width = getattr(input, "width", None)
    height = getattr(input, "height", None)
    if width and height:
        return v2(float(width), float(height))

    return v2(float(WORLD_WIDTH), float(WORLD_HEIGHT))


def framePosition(input: Input, x: number, y: number, zoom: number) -> v2[number, number]:
    """
    The world position the input must take for its point `(x, y)` — a
    fraction of its own box — to sit at the centre of the frame once scaled
    by `zoom` relative to its CURRENT scale.

    The maths is one line, but the sign of y is where this goes wrong: world
    y points up, media fractions point down.
    """
    box = mediaBox(input)
    scale = v2(*input.meta.scale)
    # Offset of the target point from the input's centre, at the final scale.
    offsetX = (x - 0.5) * box.x * scale.x * zoom
    offsetY = (0.5 - y) * box.y * scale.y * zoom
    # Put the centre of the frame on that point: centre + offset == 0.
    return v2(-offsetX, -offsetY)


def containSize(sourceWidth: number, sourceHeight: number) -> v2[number, number]:
    """
    The world size at which a source of `sourceWidth` x `sourceHeight` FITS
    the frame — "contain": never stretched, never cropped.

    What the media does not cover stays transparent, so put a filled
    rectangle at a lower `zIndex` behind it if you want bars rather than a
    hole. Pass the result as `width=` / `height=` of a `Video` or `Image`;
    the camera moves then read it back through `mediaBox`.
    """
    factor = min(WORLD_WIDTH / sourceWidth, WORLD_HEIGHT / sourceHeight)
    return v2(sourceWidth * factor, sourceHeight * factor)
