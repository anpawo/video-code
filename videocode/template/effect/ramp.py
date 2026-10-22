#!/usr/bin/env python3

from __future__ import annotations

from typing import Any, Generator

from videocode.constants import *
from videocode.shader.ishader import IShader
from videocode.utils.bezier import *


def dipAndReturn(
    *,
    peak: number,
    start: sec = 0,
    duration: sec = 2.0,
    fade: sec = 0.4,
    rise: easing = Easing.Out,
    fall: easing = Easing.In,
) -> Generator[tuple[float, sec], Any, None]:
    """
    The three-phase ramp a "grade" effect follows: climb from 0 to `peak` over
    `fade`, HOLD there, then come back down to 0 over `fade`. Yields
    `(value, time)` pairs, one per frame, `time` being an offset in seconds to
    hand to `IShader.at(start=...)`.

    Why one pair PER FRAME through the hold, and not a single pair for the
    whole plateau: a fragment shader posed on a frame only applies to that
    frame. Emitting the plateau once left `duration - 2 * fade` seconds with
    no emission at all, and the effect vanished between its entrance and its
    exit — a 2 s `spotlightOn` was visible for 0.35 s, dark for 1.3 s, then
    visible again. Costs one shader per frame, which is what every other
    animated template already pays.

    `fade` is clamped to half of `duration`, so `fade >= duration / 2` gives a
    straight dip with no plateau.

    The three phases are laid out in FRAMES, one emission per frame, counted
    end to end — never by anchoring a phase to its time in seconds. Seconds
    are the wrong ruler here: `apply()` lands a shader on `round(start *
    FRAMERATE)`, and a `fade` that is not a whole number of frames puts the
    hold half a frame off the grid, where round-half-to-even sends
    consecutive emissions to 10, 12, 12, 14, 14... — two shaders on one
    frame and NOTHING on the next. `spotlightOn`'s default `fade=0.35` is
    exactly that case at 30 fps (10.5 frames), and it strobed one frame in
    two.

        for v, t in dipAndReturn(peak=0.8, duration=2.0, fade=0.35):
            yield vignette(v).at(start=t)
    """
    f = min(fade, duration / 2)

    # The count `rangeIdx` will actually emit — read it from the same formula
    # rather than deriving a second one that could disagree.
    edge = max(1, int(f * FRAMERATE))
    hold = max(0, round(duration * FRAMERATE) - 2 * edge)

    at = 0
    for v, _ in rise.rangeIdx(0.0, float(peak), f):
        yield v, start + at * SINGLE_FRAME
        at += 1

    for _ in range(hold):
        yield float(peak), start + at * SINGLE_FRAME
        at += 1

    for v, _ in fall.rangeIdx(float(peak), 0.0, f):
        yield v, start + at * SINGLE_FRAME
        at += 1


# A shader posed on a frame stops applying on the next one unless it carries a
# `duration`. So an effect that SETTLES — bars, a vignette, a grade meant to
# stay — has to say how long it stays, and there is no "forever" to default to:
# `Input.apply` grows the film to cover every shader's end
# (`Context.lastEverAffectedFrame`, input.py:250), so a template that held its
# look for an hour would render an hour. Measured, not guessed: a 3600 s hold
# turned a 33.8 s reel into 217980 frames. The author knows when the look ends;
# the template cannot, so it asks.
HOLD_NONE: sec = 0


def holdAfter(
    shader: IShader,
    start: sec,
    duration: sec,
    hold: sec,
) -> Generator[IShader, Any, None]:
    """
    Pose `shader` ONCE, for `hold` seconds, on the frame right after an
    animation of `duration` that began at `start` — the "and it stays there"
    half of an effect that settles instead of returning. `hold=0` yields
    nothing, which is the same as not calling it.

    Pick `hold` to reach whatever undoes the look — the next `unscope`, the
    end of the shot. It lengthens the film if it runs past everything else,
    so it is not free: see the module comment above.

    The landing frame is counted in FRAMES, from the same formula
    `rangeIdx` uses, never from `start + duration` in seconds: a duration
    that is not a whole number of frames would put the hold half a frame off
    the grid, where rounding drops it onto the animation's own last frame and
    one of the two is lost.

    A later shader of the same kind on the same input takes over while the
    hold is running, and the hold applies again once that one ends.

        yield from holdAfter(crop(top=b, bottom=b), start, duration, hold)
    """
    if hold <= 0:
        return
    landing = max(1, int(duration * FRAMERATE))
    yield shader.at(start=start + landing * SINGLE_FRAME, duration=hold)
