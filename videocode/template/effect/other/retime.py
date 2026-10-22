#!/usr/bin/env python3

from __future__ import annotations

#
# Retiming — slow motion, speed ramps, freeze frames, rewind.
#
# These are NOT `Effect`s, and that is a property of the engine, not an
# oversight. An `Effect` yields per-frame shaders that animate an input's
# STATE; retiming changes which SOURCE FRAME a `Video` decodes, which is
# decided once, at construction, by `Video(speedRamps=[...])`. There is no
# per-frame shader that can reach it.
#
# So these helpers build the `(playbackStart, playbackEnd, rate)` triples
# `Video` expects, in seconds instead of playback frames — the same units the
# rest of a scene is written in:
#
#     Video("game.mov", speedRamps=[
#         slowMotion(at=41.5, duration=3),
#         freezeFrame(at=52.0, duration=1.2),
#         fastForward(at=60, duration=40),
#     ])
#
# One honest limitation, inherited from `Video`: sampling is NEAREST-FRAME at
# every rate. `slowMotion(rate=0.25)` shows each source frame four times — it is
# a slow motion, not an INTERPOLATED one. Optical-flow retiming (what an
# editor means by "smooth slowmo") does not exist in the engine; the smooth
# version has to come from footage shot at a high frame rate.
#

from videocode.constants import FRAMERATE
from videocode.ty import frame, number, sec


def speedRamp(*, at: sec, duration: sec, rate: number) -> tuple[frame, frame, float]:
    """
    The raw triple, in seconds: play `[at, at + duration)` of the PLAYBACK
    timeline at `rate` source-frames per playback-frame.

    `rate > 1` speeds up, `0 < rate < 1` slows down, `0` freezes, negative
    plays backwards. Windows must not overlap — `Video` raises if they do.
    """
    startFrame = int(round(at * FRAMERATE))
    endFrame = max(startFrame + 1, int(round((at + duration) * FRAMERATE)))
    return (startFrame, endFrame, float(rate))


def slowMotion(*, at: sec, duration: sec, rate: number = 0.4) -> tuple[frame, frame, float]:
    """
    Slow motion over a window: `rate=0.4` plays it at 40% speed.

    Nearest-frame, no blending — see the module note. Below ~0.25 the
    stepping becomes visible on real footage.
    """
    return speedRamp(at=at, duration=duration, rate=rate)


def fastForward(*, at: sec, duration: sec, rate: number = 4.0) -> tuple[frame, frame, float]:
    """
    Speed ramp: compress a dull stretch. `rate=4` pushes four seconds of
    source through one second of playback.
    """
    return speedRamp(at=at, duration=duration, rate=rate)


def freezeFrame(*, at: sec, duration: sec) -> tuple[frame, frame, float]:
    """
    Hold on the frame the window opened on for `duration` — the stop that
    lets a caption land.
    """
    return speedRamp(at=at, duration=duration, rate=0.0)


def rewind(*, at: sec, duration: sec, rate: number = -2.0) -> tuple[frame, frame, float]:
    """Play the window backwards — negative `rate`, `-1` for real time."""
    return speedRamp(at=at, duration=duration, rate=rate)


def decimate(first: frame, frames: int, ratio: float) -> list[tuple[frame, frame]]:
    """
    The `cuts=` that keep one SOURCE frame out of `ratio`, starting at `first`,
    for `frames` frames of scene.

    The engine consumes ONE source frame per scene frame and a scene is always
    30 fps, so a 60 fps source plays at half speed unless frames are thrown
    away. `speedRamp` cannot do it — it changes the rate but not the length the
    clip claims; only `cuts` shorten it. `ratio` is `sourceFps / FRAMERATE`.

    The end of the clip is `first + round((frames - 1) * ratio) + 1`:

        ratio = fps / FRAMERATE
        end = first + round((frames - 1) * ratio) + 1
        Video("game.mov", startFrame=first, endFrame=end,
              cuts=decimate(first, frames, ratio))
    """
    kept = {first + round(i * ratio) for i in range(frames)}
    last = first + round((frames - 1) * ratio) + 1
    spans: list[tuple[frame, frame]] = []
    f = first
    while f < last:
        if f in kept:
            f += 1
            continue
        gap = f
        while f < last and f not in kept:
            f += 1
        spans.append((gap, f))
    return spans
