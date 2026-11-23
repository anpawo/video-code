#!/usr/bin/env python3

"""
Assertion-based tests for effects batch 6 (everyday explainer-video filters):
- roundCorners / feather / saturation / temperature / chromaticAberration /
  letterbox fragment-shader Python bindings
Run directly: `python3 test/effects6_test.py`
"""

import sys

sys.path.insert(0, ".")
sys.path.insert(0, "test")
from helpers import check, section, summary

from videocode import *


def framesWith(index: int, key: str) -> dict[int, dict]:
    return {f: entry[key] for f, entry in Context.stack[index].items() if f != -1 and key in entry}


# ---------------------------------------------------------------------------
section("fragment shader bindings")

check("roundCorners args", roundCorners(0.3).radius == 0.3)
check("feather args", feather(0.2).softness == 0.2)
check("saturation args", saturation(0.5).amount == 0.5)
check("temperature args", temperature(-0.4).warmth == -0.4)
check("chromaticAberration args", chromaticAberration(0.01).amount == 0.01)
check("letterbox args", letterbox(2.39).ratio == 2.39)

r = Rectangle(width=1, height=1)
r.apply(roundCorners(), duration=0.1)
r.apply(feather(), start=0.2, duration=0.1)
r.apply(saturation(), start=0.4, duration=0.1)
r.apply(temperature(), start=0.6, duration=0.1)
r.apply(chromaticAberration(), start=0.8, duration=0.1)
r.apply(letterbox(), start=1.0, duration=0.1)
names = {k for fr, e in Context.stack[r.meta.index].items() if fr != -1 for k in e}
for n in ("RoundCorners", "Feather", "Saturation", "Temperature", "ChromaticAberration", "Letterbox"):
    check(f"{n} lands in the stack", n in names)

# ---------------------------------------------------------------------------
section("riseIn — fades in while rising into place, claims y only")

from videocode.template.effect.other.riseIn import riseIn

t = Rectangle(width=1, height=1).position(1.0, 2.0)
t.apply(riseIn(distance=0.5, duration=0.6))
pos = framesWith(t.meta.index, "Position")
ys = [e["args"]["y"] for _, e in sorted(pos.items())]
check("starts `distance` below the destination", abs(ys[0] - 1.5) < 1e-6)
check("lands exactly on the destination", ys[-1] == 2.0)
check("only moves up", ys == sorted(ys))
# Frame 0 also holds the earlier .position(1.0, 2.0), which keeps its x; every
# frame riseIn writes on its own leaves x unclaimed.
check("x is not claimed", all(e["args"]["x"] is None for k, e in pos.items() if k > 0) and pos[0]["args"]["x"] == 1.0)
ops = [e["args"]["opacity"] for _, e in sorted(framesWith(t.meta.index, "Opacity").items())]
check("starts at opacity 0", ops[0] == 0)
check("ends at full opacity", ops[-1] == 255)
check("cursor ends on the destination", t.meta.position.y == 2.0 and t.meta.position.x == 1.0)

# A move in x over the same frames must survive, whichever was written first.
for order in ("moveTo first", "riseIn first"):
    m = Rectangle(width=1, height=1).position(1.0, 2.0)
    if order == "moveTo first":
        m.moveTo(x=3, duration=0.6)
        m.apply(riseIn(distance=0.5, duration=0.6))
    else:
        m.apply(riseIn(distance=0.5, duration=0.6))
        m.moveTo(x=3, duration=0.6)
    pos = framesWith(m.meta.index, "Position")
    frames = sorted(pos)
    xs = [pos[f]["args"]["x"] for f in frames]
    ys = [pos[f]["args"]["y"] for f in frames]
    check(f"{order}: x still travels 1 -> 3", xs[0] == 1.0 and xs[-1] == 3.0)
    check(f"{order}: y still rises 1.5 -> 2", abs(ys[0] - 1.5) < 1e-6 and ys[-1] == 2.0)
    check(f"{order}: every shared frame carries both axes", all(x is not None and y is not None for x, y in zip(xs, ys)))

# ---------------------------------------------------------------------------
summary()
