#!/usr/bin/env python3

# Visual regression scene — montage camera moves (punchIn, zoomTo, snapZoom,
# travelling, impact, whipPan).
#
# Every tile is a GRADIENT rectangle, not a flat one, and the two circles carry
# a stroke: a camera move that scales or pans the wrong way moves the gradient
# ramp and the stroke ring visibly, where a flat fill would look identical
# whatever the framing. The goldens sample frames 0/7/15/29, so each effect
# runs 1.0s (30 frames) and frame 29 is its last.
#
# snapZoom and impact are round-trips: at frame 29 they are back where they
# started, which is exactly what makes them worth a golden — a broken return
# shows up as a tile that no longer lines up with its neighbours.

from videocode import *
from videocode.template.effect.other.camera import punchIn, snapZoom, travelling, zoomTo
from videocode.template.effect.other.impact import impact
from videocode.template.effect.other.whipPan import whipPan

DUR = 1.0

TILE = dict(width=4.4, height=3.4, strokeColor=WHITE, strokeWidth=0.05, cornerRadius=8)

# --- top row ---------------------------------------------------------------
Rectangle(fillColor=LinearGradient(RED_B, BLUE_C), **TILE) \
    .position(-5.4, 2.2).apply(punchIn(zoom=1.4, duration=DUR))

Rectangle(fillColor=LinearGradient(GREEN_A, BLUE_B), **TILE) \
    .position(0.0, 2.2).apply(zoomTo(x=0.25, y=0.25, zoom=1.8, duration=DUR))

Rectangle(fillColor=LinearGradient(YELLOW, RED_A), **TILE) \
    .position(5.4, 2.2).apply(snapZoom(x=0.8, y=0.2, zoom=2.0, attack=0.1, hold=0.6, release=0.3))

# --- bottom row ------------------------------------------------------------
Rectangle(fillColor=LinearGradient(BLUE_C, YELLOW), **TILE) \
    .position(-5.4, -2.2).apply(travelling(fromX=0.1, fromY=0.9, toX=0.9, toY=0.1, zoom=1.6, duration=DUR))

Circle(radius=1.6, fillColor=LinearGradient(RED_A, GREEN_A), strokeColor=WHITE, strokeWidth=0.06) \
    .position(0.0, -2.2).apply(impact(zoom=1.35, amplitude=0.25, frequency=8, duration=DUR))

Circle(radius=1.6, fillColor=LinearGradient(BLUE_A, RED_B), strokeColor=WHITE, strokeWidth=0.06) \
    .position(5.4, -2.2).apply(whipPan(toX=0.9, toY=0.5, blur=10, duration=DUR))
