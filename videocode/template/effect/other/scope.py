#!/usr/bin/env python3

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generator

from videocode.constants import *
from videocode.shader.fragmentShader.crop import crop as _crop
from videocode.shader.ishader import Effect, IShader
from videocode.template.effect.ramp import HOLD_NONE, holdAfter as _hold
from videocode.utils.bezier import *

if TYPE_CHECKING:
    from videocode.input.input import Input


def _bars(ratio: number, start: sec, duration: sec, hold: sec, easing: easing, closing: bool) -> Effect:
    """`scope` when `closing`, `unscope` when not: one move, read from either end."""
    # Measured against the frame, as `letterbox` does: what fraction of the
    # height survives at `ratio`:1. Above 1 the ratio is narrower than the
    # frame, and it is the width that gives way — bars left and right.
    keep = (SCREEN_WIDTH / ratio) / SCREEN_HEIGHT if ratio > 0 else 1.0
    sides = ("top", "bottom") if keep <= 1 else ("left", "right")
    bar = (1.0 - (keep if keep <= 1 else 1 / keep)) / 2 * 100
    src, dst = (0.0, bar) if closing else (bar, 0.0)

    def _apply(_input: Input) -> Generator[IShader, Any, None]:
        for b, i in easing.rangeIdx(src, dst, duration):
            yield _crop(**dict.fromkeys(sides, b)).at(start=start + i * SINGLE_FRAME)
        yield from _hold(_crop(**dict.fromkeys(sides, dst)), start, duration, hold)

    return _apply


def scope(
    *,
    ratio: number = 2.39,
    start: sec = 0,
    duration: sec = 0.7,
    hold: sec = HOLD_NONE,
    easing: easing = Easing.Out,
) -> Effect:
    """
    Slide cinemascope bars in until the visible image is `ratio`:1 — the
    "this bit is the film" marker. `2.39` is anamorphic scope, `1.85` is
    flat widescreen, `1` is a square crop. The bars come from the top and
    bottom when `ratio` is wider than the frame, from the left and right when
    it is narrower — what `letterbox` does, animated.

    The bars are an animated `crop`, so they close in on the MEDIA, not on
    the frame — but their size is the percentage a frame-filling input
    needs. On an input of another shape (a portrait capture floating in a
    wide frame) the same percentage of ITS box is cut, and what stays
    visible is not `ratio`:1.

    The bars do NOT stay by themselves. A shader posed on a frame with the
    default one-frame duration stops applying on the next one, so the bars
    spring back open the instant the move ends: set `hold` to the number of
    seconds they should stay, which means "until whatever opens them again".
    A 0.2 s gap between a `scope` and its `unscope` was enough to show the
    full frame for six frames and then slam the bars back — a visible
    flicker. `hold` costs film length when it runs past everything else, so
    it is asked for rather than assumed — see `holdAfter`.

        clip.apply(scope())                        # the move alone
        clip.apply(scope(duration=0.6, hold=1.4))  # ... and it stays 1.4 s
        clip.apply(scope(ratio=1.85, duration=1))
    """
    return _bars(ratio, start, duration, hold, easing, closing=True)


def unscope(
    *,
    ratio: number = 2.39,
    start: sec = 0,
    duration: sec = 0.7,
    hold: sec = HOLD_NONE,
    easing: easing = Easing.Out,
) -> Effect:
    """Open the `scope(ratio=...)` bars back to the full frame, and keep it open for `hold` seconds — see `scope`."""
    return _bars(ratio, start, duration, hold, easing, closing=False)
