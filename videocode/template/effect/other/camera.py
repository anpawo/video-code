#!/usr/bin/env python3

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generator

from videocode.constants import *
from videocode.shader.ishader import Effect, IShader
from videocode.shader.vertexShader.position import position as _position
from videocode.shader.vertexShader.scale import scale as _scale
from videocode.template.effect.framing import framePosition
from videocode.utils.bezier import *

if TYPE_CHECKING:
    from videocode.input.input import Input


def punchIn(
    *,
    zoom: number = 1.18,
    start: sec = 0,
    duration: sec = 4.0,
    easing: easing = Easing.Out,
) -> Effect:
    """
    Slow continuous push toward the target — the montage rule that the camera
    is never completely still. Scale only: the framing does not move, so a
    `punchIn` composes with anything that owns `position`.

    `zoom < 1` pulls out instead.

    Not `zoomPunch`, which is the other half of this idea: that one snaps up
    and comes straight back with a Back overshoot — a beat. This one is a
    one-way push that STAYS where it arrives, and runs over seconds, not
    frames. Reach for `zoomPunch` on an accent, for `punchIn` under a whole
    shot.

        clip.apply(punchIn())
        clip.apply(punchIn(zoom=1.35, duration=6, easing=Easing.Linear))
    """

    def _apply(input: Input) -> Generator[IShader, Any, None]:
        src = v2(*input.meta.scale)
        for s, i in easing.rangeIdx(src, src * zoom, duration):
            yield _scale(*s).at(start=start + i * SINGLE_FRAME)

    return _apply


def reframe() -> Effect:
    """
    Snap to the default framing — position `(0, 0)`, scale `(1, 1)`, written
    as absolute values: an input that was placed or scaled before the moves
    does not get that placement back.

    `zoomTo`, `travelling`, `punchIn` and `snapZoom` (but the last) are
    STATEFUL: they leave the camera where they brought it. A reel chaining
    them must say so, or each move starts from the previous one's framing.
    Pose it just before the next move, with `at=`:

        clip.apply(zoomTo(x=0.4, y=0.2), at=5)
        clip.apply(reframe(), at=6)
    """

    def _apply(input: Input) -> Generator[IShader, Any, None]:
        yield _position(0, 0).at(start=0)
        yield _scale(1, 1).at(start=0)

    return _apply


def zoomTo(
    *,
    x: number = 0.5,
    y: number = 0.5,
    zoom: number = 2.0,
    start: sec = 0,
    duration: sec = 1.2,
    easing: easing = Easing.Out,
) -> Effect:
    """
    Push in on ONE point of the media and hold there — the shot that says
    "look at this".

    `x` and `y` are fractions of the input's own box, (0, 0) top-left and
    (1, 1) bottom-right, y downward. Nothing about the content is assumed:
    turning a domain coordinate into that fraction is the caller's job.

    Both axes of `position` and `scale` are claimed for the whole window, and
    the framing PERSISTS afterwards (position/scale are stateful). `zoom`
    multiplies the CURRENT scale, so `zoom=1` keeps the zoom it finds: undo
    it with the inverse, `zoomTo(x=0.5, y=0.5, zoom=1 / 2.4)` — the scale it
    had, centred on the frame — or with `reframe()`, or use `snapZoom`,
    which returns by itself.

        clip.apply(zoomTo(x=0.42, y=0.61, zoom=2.4))
    """

    def _apply(input: Input) -> Generator[IShader, Any, None]:
        srcScale = v2(*input.meta.scale)
        srcPos = v2(*input.meta.position)
        dstScale = srcScale * zoom
        dstPos = framePosition(input, x, y, zoom)
        moves = zip(
            easing.rangeIdx(srcScale, dstScale, duration),
            easing.rangeIdx(srcPos, dstPos, duration),
        )
        for (s, i), (p, _) in moves:
            yield _scale(*s).at(start=start + i * SINGLE_FRAME)
            yield _position(*p).at(start=start + i * SINGLE_FRAME)

    return _apply


def snapZoom(
    *,
    x: number = 0.5,
    y: number = 0.5,
    zoom: number = 2.2,
    hold: sec = 0.8,
    start: sec = 0,
    attack: sec = 0.1,
    release: sec = 0.3,
) -> Effect:
    """
    `zoomTo` with no ramp: jump onto the point in `attack` seconds, `hold`
    there, then fall back to the original framing over `release`. The
    reaction-video emphasis, and the only camera move here that leaves the
    input exactly as it found it.

    `zoomPunch` already does the up-and-back on `scale` alone. What it cannot
    do is aim: it grows the frame around its centre, while `snapZoom` also
    writes `position` so the zoom lands ON a point, and holds there. Give it
    no `x`/`y` and the centre is the point — then `zoomPunch` is the lighter
    call, and the better one.

        clip.apply(snapZoom(x=0.42, y=0.61))
        clip.apply(snapZoom(x=0.8, y=0.2, zoom=3, hold=1.2))
    """

    def _apply(input: Input) -> Generator[IShader, Any, None]:
        srcScale = v2(*input.meta.scale)
        srcPos = v2(*input.meta.position)
        dstScale = srcScale * zoom
        dstPos = framePosition(input, x, y, zoom)

        for (s, i), (p, _) in zip(
            Easing.Exponential.rangeIdx(srcScale, dstScale, attack),
            Easing.Exponential.rangeIdx(srcPos, dstPos, attack),
        ):
            yield _scale(*s).at(start=start + i * SINGLE_FRAME)
            yield _position(*p).at(start=start + i * SINGLE_FRAME)

        back = start + attack + hold
        for (s, i), (p, _) in zip(
            Easing.InOut.rangeIdx(dstScale, srcScale, release),
            Easing.InOut.rangeIdx(dstPos, srcPos, release),
        ):
            yield _scale(*s).at(start=back + i * SINGLE_FRAME)
            yield _position(*p).at(start=back + i * SINGLE_FRAME)

    return _apply


def travelling(
    *,
    fromX: number = 0.5,
    fromY: number = 0.5,
    toX: number = 0.5,
    toY: number = 0.5,
    zoom: number = 1.6,
    start: sec = 0,
    duration: sec = 3.0,
    easing: easing = Easing.InOut,
) -> Effect:
    """
    Glide the frame from one point of the media to another at a FIXED zoom —
    a dolly, not a push. The zoom is set once on the first frame, so the two
    moves stay readable as one move.

    Coordinates are fractions of the input's own box, as in `zoomTo`.

        clip.apply(travelling(fromX=0.2, fromY=0.8, toX=0.8, toY=0.2))
        clip.apply(travelling(fromX=0, toX=1, zoom=2.2, duration=5))
    """

    def _apply(input: Input) -> Generator[IShader, Any, None]:
        srcScale = v2(*input.meta.scale)
        yield _scale(*(srcScale * zoom)).at(start=start)
        a = framePosition(input, fromX, fromY, zoom)
        b = framePosition(input, toX, toY, zoom)
        for p, i in easing.rangeIdx(a, b, duration):
            yield _position(*p).at(start=start + i * SINGLE_FRAME)

    return _apply
