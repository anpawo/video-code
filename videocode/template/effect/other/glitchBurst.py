#!/usr/bin/env python3

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generator

from videocode.constants import *
from videocode.shader.fragmentShader.glitch import glitch as _glitch
from videocode.shader.fragmentShader.pixelate import pixelate as _pixelate
from videocode.shader.ishader import Effect, IShader
from videocode.utils.bezier import *

if TYPE_CHECKING:
    from videocode.input.input import Input


def glitchBurst(
    *,
    amount: percent = 4.0,
    slices: number = 16,
    seed: number = 7,
    blocks: number = 0,
    start: sec = 0,
    duration: sec = 0.4,
) -> Effect:
    """
    A short signal drop-out: slices tear sideways, the channels split, and
    (with `blocks`) the picture blocks up for the first third of it.

    `glitch` is TIME-DRIVEN — the renderer feeds it 0..1 progress over the
    window and it re-rolls its slices ~24 times across that. So the burst is
    emitted as ONE `glitch` covering `duration`, not one per frame: re-issuing
    it every frame would restart its clock every frame and freeze the pattern
    on its first roll. That is why `amount` here is constant and not a ramp —
    a ramped tear would need the amplitude inside the shader's own clock.

    `seed` is fixed by default so the same call renders the same burst twice.

        clip.apply(glitchBurst())
        clip.apply(glitchBurst(amount=8, blocks=40, duration=0.6))
    """

    def _apply(_input: Input) -> Generator[IShader, Any, None]:
        yield _glitch(amount, slices, seed).at(start=start, duration=duration)
        if blocks:
            # The blocky part is short and front-loaded: a drop-out recovers
            # its resolution before it recovers its sync.
            for b, i in Easing.In.rangeIdx(float(blocks), 1.0, duration / 3):
                if b > 1.5:
                    yield _pixelate(b).at(start=start + i * SINGLE_FRAME)

    return _apply
