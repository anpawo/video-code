#!/usr/bin/env python3

# Visual regression scene — Shadow + layer-order API.
#
# Shadow: an offset, darker, semi-transparent copy of `box`'s geometry,
# rendered behind it via zIndex (with an independent blur effect).
#
# Layers: three overlapping rectangles (a, b, c) reordered over time using
# the semantic layer-order helpers:
#   .inFrontOf(other) / .behind(other)   — relative to one input
#   .bringToFront()   / .sendToBack()    — relative to everything in the scene
#
# Plane is included to exercise that it's excluded from layer-order queries
# (sendToBack should not put `c` behind the opaque background).
#
# Golden frames (kGoldenCases "layers" — frames 0, 31, 61, 91):
#   - frame0:  initial order a < b < c (back→front). a∩b shows b (cyan),
#              b∩c shows c (green).
#   - frame31: a.bringToFront() in effect — a∩b now shows a (red); a is in
#              front of everything. b∩c unchanged.
#   - frame61: b.behind(c) in effect, but a no-visible-change checkpoint —
#              b's zIndex value doesn't move (already c.zIndex - 1), so this
#              frame is pixel-identical to frame31.
#   - frame91 (last frame): c.sendToBack() in effect — b∩c now shows b
#              (cyan); c dropped behind b (and a). `c` must still render in
#              front of the Plane background grid (not hidden by it) — this
#              is the regression check for Plane being excluded from
#              sendToBack's layer-order query.

from videocode import *
from videocode.template.input._inputs import *

p = Plane()

box = Rectangle(width=5, height=2.5, fillColor=BLUE_C, strokeColor=TRANSPARENT)
Shadow(box, offset=(0.3, -0.3), color=BLACK | 0.35).apply(blur(5))

a = Rectangle(width=3, height=3, fillColor=RED_A, strokeColor=TRANSPARENT)
a.position(-4.5, -2.5)

b = Rectangle(width=3, height=3, fillColor=BLUE_A, strokeColor=TRANSPARENT)
b.position(-3, -2.5)
# created after `a` → in front of it by default

c = Rectangle(width=3, height=3, fillColor=GREEN_A, strokeColor=TRANSPARENT)
c.position(-1.5, -2.5)
# created after `b` → in front of it by default. Order so far (back→front): a, b, c

a.wait(1).bringToFront()  # `a` now in front of everything
b.wait(2).behind(c)  # `b` now behind `c` (but still in front of `a`)
c.wait(3).sendToBack()  # `c` now behind everything
