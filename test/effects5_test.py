#!/usr/bin/env python3

"""
Assertion-based tests for effects batch 5 (Tier 1 compositing gap):
- glow/bloom fragment-shader binding + stack shape
Run directly: `python3 test/effects5_test.py`
"""

import sys

sys.path.insert(0, ".")
sys.path.insert(0, "test")
from helpers import check, section, summary

from videocode import *


def framesWith(index: int, key: str) -> dict[int, dict]:
    return {f: entry[key] for f, entry in Context.stack[index].items() if f != -1 and key in entry}


# ---------------------------------------------------------------------------
section("glow — binding and stack presence")

g = glow(radius=9, intensity=1.4)
check("radius/intensity stored", g.radius == 9 and g.intensity == 1.4)

r = Rectangle(width=1, height=1)
r.apply(glow(radius=7, intensity=0.8), duration=0.3)
glows = framesWith(r.meta.index, "Glow")
check("Glow lands in the stack", len(glows) > 0)

# The C++/GLSL side reads args ALPHABETICALLY → intensity before radius. The
# renderer's glow branch depends on this exact order (params[0]=intensity,
# params[1]=radius); assert it so a future rename can't silently swap them.
argKeys = [k for k in next(iter(glows.values()))["args"] if k not in ("start", "duration")]
check("args are exactly {intensity, radius}", set(argKeys) == {"intensity", "radius"})
check("intensity sorts before radius (alphabetical param order)",
      sorted(argKeys) == ["intensity", "radius"])

vals = next(iter(glows.values()))["args"]
check("stored values survive to the stack", vals["radius"] == 7 and vals["intensity"] == 0.8)

# ---------------------------------------------------------------------------
section("popOut — overshoot, shrink to 0, then hide")

from videocode.template.effect.other.popOut import popOut

po = Rectangle(width=1, height=1)
po.apply(popOut(duration=0.4))
poScales = framesWith(po.meta.index, "Scale")
pxs = [e["args"]["x"] for _, e in sorted(poScales.items())]
peak = pxs.index(max(pxs))
check("starts at the current scale", abs(pxs[0] - 1.0) < 0.02)
check("overshoot frame grows ~10%", 1.05 < pxs[peak] < 1.15 and 0 < peak < len(pxs) - 1)
check("shrinks to 0 at the end", abs(pxs[-1]) < 1e-6 and abs(poScales[max(poScales)]["args"]["y"]) < 1e-6)
poHides = framesWith(po.meta.index, "Hide")
check("hide lands after the last scale frame", len(poHides) == 1 and min(poHides) > max(poScales))

# ---------------------------------------------------------------------------
summary()
