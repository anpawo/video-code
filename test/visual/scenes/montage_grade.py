#!/usr/bin/env python3

# Visual regression scene — montage grades and beats (spotlightOn, zoneFocus,
# desaturate, glitchBurst, vignetteBeat, scope).
#
# The two spotlight tiles are the reason this scene exists: `spotlight` is
# placed in FRAME UV, not in the tile's own box, so each tile's spot is
# addressed by where the tile sits ON SCREEN. Get the frame-UV convention
# wrong — y flipped, or measured against the mesh — and the pool lands off the
# tile entirely, which no amount of "the shader does something" hides.
#
# glitchBurst sits on a CIRCLE on purpose (docs/ADDING_EFFECTS.md): a torn
# slice shows as a broken silhouette, where a rectangle would tear invisibly.
# Its seed is pinned so the golden is reproducible.
#
# Frames 0/7/15/29 are sampled, so every effect runs 1.0s.

from videocode import *
from videocode.template.effect.other.desaturate import desaturate
from videocode.template.effect.other.glitchBurst import glitchBurst
from videocode.template.effect.other.scope import scope
from videocode.template.effect.other.spotlightOn import spotlightOn, zoneFocus
from videocode.template.effect.other.vignetteIn import vignetteBeat

DUR = 1.0

TILE = dict(width=4.4, height=3.4, strokeColor=WHITE, strokeWidth=0.05, cornerRadius=8)

# Frame UV of a tile's centre, for the two frame-space effects below. The
# world box is 16x9 with the origin in the middle and y pointing UP; frame UV
# starts top-left with y pointing DOWN.
def uv(x: float, y: float) -> tuple[float, float]:
    return (x + WORLD_WIDTH / 2) / WORLD_WIDTH, (WORLD_HEIGHT / 2 - y) / WORLD_HEIGHT


# --- top row ---------------------------------------------------------------
sx, sy = uv(-5.4, 2.2)
Rectangle(fillColor=LinearGradient(RED_B, BLUE_C), **TILE) \
    .position(-5.4, 2.2).apply(spotlightOn(x=sx, y=sy, radius=0.13, darkness=0.85, duration=DUR, fade=0.3))

zx, zy = uv(0.0, 2.2)
Rectangle(fillColor=LinearGradient(GREEN_A, BLUE_B), **TILE) \
    .position(0.0, 2.2).apply(zoneFocus(x=zx, y=zy, width=0.14, height=0.2, corner=0.0,
                                        darkness=0.85, duration=DUR, fade=0.3))

Rectangle(fillColor=LinearGradient(YELLOW, RED_A), **TILE) \
    .position(5.4, 2.2).apply(desaturate(amount=1.0, duration=DUR, fade=0.3))

# --- bottom row ------------------------------------------------------------
Rectangle(fillColor=LinearGradient(BLUE_C, YELLOW), **TILE) \
    .position(-5.4, -2.2).apply(vignetteBeat(intensity=0.85, duration=DUR))

Circle(radius=1.6, fillColor=LinearGradient(RED_A, GREEN_A), strokeColor=WHITE, strokeWidth=0.06) \
    .position(0.0, -2.2).apply(glitchBurst(amount=7, slices=14, seed=7, blocks=26, duration=DUR))

Rectangle(fillColor=LinearGradient(BLUE_A, RED_B), **TILE) \
    .position(5.4, -2.2).apply(scope(ratio=2.39, duration=DUR))
