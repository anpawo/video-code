#!/usr/bin/env python3

"""
Assertion-based smoke tests for the Manim-inspired rate functions added to
`Easing` (`videocode/utils/bezier.py`): `Smooth`, `RushInto`, `RushFrom`,
`SlowInto`, `DoubleSmooth`, `ThereAndBack`, `ThereAndBackWithPause`, `Wiggle`,
`ExponentialDecay`. These are `Func`-based `RateFunc`s (not `CubicBezier`),
exercising the generalized `easing` type used by `ease`/`moveTo`/`scaleTo`/
`rotateTo`/`fadeIn`/... .
Run directly: `python3 test/easing_test.py`
"""

import math
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "test")
from helpers import check, section, summary

from videocode import Rectangle, Context, CubicBezier, Easing
from videocode.utils.bezier import curves

def approx(a: float, b: float, tol: float = 1e-3) -> bool:
    return abs(a - b) < tol

# ── 0→1 rate functions ──────────────────────────────────────────────────────
section("0->1 rate functions: endpoints")
for name in ("Smooth", "RushInto", "RushFrom", "SlowInto", "DoubleSmooth"):
    f = getattr(Easing, name)
    check(f"{name}(0) == 0", approx(f(0), 0))
    check(f"{name}(1) == 1", approx(f(1), 1))

# ── "there and back" rate functions: start == end ───────────────────────────
section("there-and-back rate functions: start == end")
check("ThereAndBack(0) == 0", approx(Easing.ThereAndBack(0), 0))
check("ThereAndBack(1) == 0", approx(Easing.ThereAndBack(1), 0))
check("ThereAndBack(0.5) == 1 (peak)", approx(Easing.ThereAndBack(0.5), 1))

check("ThereAndBackWithPause(0) == 0", approx(Easing.ThereAndBackWithPause(0), 0))
check("ThereAndBackWithPause(1) == 0", approx(Easing.ThereAndBackWithPause(1), 0))
check("ThereAndBackWithPause(0.5) == 1 (plateau)", approx(Easing.ThereAndBackWithPause(0.5), 1))

check("Wiggle(0) == 0", approx(Easing.Wiggle(0), 0))
check("Wiggle(1) == 0", approx(Easing.Wiggle(1), 0))

# ── exponential decay ────────────────────────────────────────────────────────
section("ExponentialDecay")
check("ExponentialDecay(0) == 0", approx(Easing.ExponentialDecay(0), 0))
check("ExponentialDecay(1) ~= 1", approx(Easing.ExponentialDecay(1), 1, tol=1e-3))

# ── rangeIdx/range smoke test on a Func-based easing ────────────────────────
section("rangeIdx on a Func-based easing")
samples = list(Easing.Wiggle.rangeIdx(0, 10, 0.2))  # 6 frames
check("rangeIdx produced frames", len(samples) == 6)
check("first sample ~= start", approx(samples[0][0], 0))
check("last sample ~= start (wiggle returns)", approx(samples[-1][0], 0))

# ── end-to-end: Input.rotateBy/moveBy with the new easings ──────────────────
section("Input.rotateBy(easing=Easing.Wiggle) — wiggles out and back")
r = Rectangle()
r.rotateBy(30, easing=Easing.Wiggle, duration=0.2)  # 6 frames

rotFrames = sorted(f for f, entry in Context.stack[r.meta.index].items() if f != -1 and "Rotation" in entry)
check("Rotation frames pushed", len(rotFrames) > 1)
lastDegree = Context.stack[r.meta.index][rotFrames[-1]]["Rotation"]["args"]["degree"]
check("final rotation back near start (0)", approx(lastDegree, 0, tol=1e-2))
check("rotation meta updated", approx(r.meta.rotation, lastDegree))

section("Input.moveBy(easing=Easing.ThereAndBack) — moves out and back")
r2 = Rectangle()
r2.moveBy(x=2, easing=Easing.ThereAndBack, duration=0.2)  # 6 frames

posFrames = sorted(f for f, entry in Context.stack[r2.meta.index].items() if f != -1 and "Position" in entry)
check("Position frames pushed", len(posFrames) > 1)
lastX = Context.stack[r2.meta.index][posFrames[-1]]["Position"]["args"]["x"]
check("final x back near start (0)", approx(lastX, 0, tol=1e-2))

# ── the easings.net families ─────────────────────────────────────────────────
# Each is a CubicBezier with easings.net's control points. Two references at
# t=0.5: the curve itself, solved by bisection (what CubicBezier must compute,
# to 1e-6), and easings.net's FORMULA, which the curve only approximates —
# Sine, Expo and Circ have no cubic form — so that one gets 0.01.

EASINGS_NET = {
    "InSine": 1 - math.cos(math.pi / 4), "OutSine": math.sin(math.pi / 4), "InOutSine": 0.5,
    "InQuad": 0.25, "OutQuad": 0.75, "InOutQuad": 0.5,
    "InCubic": 0.125, "OutCubic": 0.875, "InOutCubic": 0.5,
    "InQuart": 0.0625, "OutQuart": 0.9375, "InOutQuart": 0.5,
    "InExpo": 2**-5, "OutExpo": 1 - 2**-5, "InOutExpo": 0.5,
    "InCirc": 1 - math.sqrt(0.75), "OutCirc": math.sqrt(0.75), "InOutCirc": 0.5,
}


def bisected(curve: CubicBezier, x: float) -> float:
    """y of `curve` at `x`, found by bisection on t — independent of CubicBezier's Newton solve."""
    def at(t: float, p1: float, p2: float) -> float:
        return 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t**2 * p2 + t**3
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if at(mid, curve.x1, curve.x2) < x else (lo, mid)
    return at((lo + hi) / 2, curve.y1, curve.y2)


section("easings.net families: endpoints and midpoint")
for name, formula in EASINGS_NET.items():
    f = getattr(Easing, name)
    check(f"{name} is a CubicBezier", isinstance(f, CubicBezier))
    check(f"{name}(0) == 0", approx(f(0), 0, tol=1e-9))
    check(f"{name}(1) == 1", approx(f(1), 1, tol=1e-9))
    check(f"{name}(0.5) is the curve's own value", approx(f(0.5), bisected(f, 0.5), tol=1e-6))
    check(f"{name}(0.5) ~= easings.net formula", approx(f(0.5), formula, tol=0.01))
check("In and Out mirror each other", approx(Easing.InExpo(0.3) + Easing.OutExpo(0.7), 1, tol=1e-6))

# ── the presets, as the four numbers behind them ─────────────────────────────
# What the editor's curve reads to open on `Easing.Out` and to drag away from
# it. The spelling matters as much as the numbers: it is written back into the
# call, so it has to be what a person would have typed.
section("curves(): the Easing presets that ARE curves")
table = curves()
check("keyed the way a scene writes them", "Easing.Out" in table)
check("Easing.Out is its own control points", table["Easing.Out"] == (0.0, 0.0, 0.58, 1.0))
check("Easing.Linear is the straight line", table["Easing.Linear"] == (0.0, 0.0, 1.0, 1.0))
check("every CubicBezier preset is there", set(table) == {f"Easing.{n}" for n in ("Linear", "In", "Out", "InOut", *EASINGS_NET)})
check("a Func easing has no handles to show", "Easing.Wiggle" not in table)
for name, points in table.items():
    curve = getattr(Easing, name.split(".")[1])
    check(f"{name} matches the object", points == (curve.x1, curve.y1, curve.x2, curve.y2))

# A curve the editor wrote has to RUN. `easing=CubicBezier(...)` goes into a
# scene whose only import is `from videocode import *`, so the name has to be
# in that namespace — it was not, and every curve the editor drew would have
# been a NameError the moment the scene re-ran.
section("CubicBezier is in a scene's own scope")
check("videocode exports CubicBezier", CubicBezier(0.42, 0.0, 0.58, 1.0)(0.5) > 0)

r3 = Rectangle()
r3.moveBy(x=2, easing=CubicBezier(0.2, 0.9, 0.8, 0.1), duration=0.2)
movedX = sorted(f for f, entry in Context.stack[r3.meta.index].items() if f != -1 and "Position" in entry)
check("a hand-drawn curve animates", len(movedX) > 1)
check("and arrives where it was sent", approx(Context.stack[r3.meta.index][movedX[-1]]["Position"]["args"]["x"], 2, tol=1e-2))

# ── summary ──────────────────────────────────────────────────────────────────
summary()
