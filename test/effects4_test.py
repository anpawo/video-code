#!/usr/bin/env python3

"""
Assertion-based tests for effects batch 4 (Tier 1 compositing gap):
- chromaKey fragment-shader binding
- crossfade / push / wipeBetween transition templates
Run directly: `python3 test/effects4_test.py`
"""

import sys

sys.path.insert(0, ".")
sys.path.insert(0, "test")
from helpers import check, section, summary

from videocode import *
from videocode.template.effect.other.transitions import crossfade, push, wipeBetween
from videocode.template.effect.other.blink import blink


def framesWith(index: int, key: str) -> dict[int, dict]:
    return {f: entry[key] for f, entry in Context.stack[index].items() if f != -1 and key in entry}


# ---------------------------------------------------------------------------
section("chromaKey — binding and stack presence")

ck = chromaKey(color=GREEN, tolerance=0.35, softness=0.2)
check("tolerance/softness stored", ck.tolerance == 0.35 and ck.softness == 0.2)
check("color flattened to 0..1 floats", 0.0 <= ck.keyG <= 1.0)

r = Rectangle(width=1, height=1)
r.apply(chromaKey(), duration=0.2)
names = {k for fr, e in Context.stack[r.meta.index].items() if fr != -1 for k in e}
check("ChromaKey lands in the stack", "ChromaKey" in names)

# ---------------------------------------------------------------------------
section("crossfade — opposite fades, same window")

# Inputs default to opacity=255, so a's very first eased frame (value 255,
# equal to its current opacity) autodestroys — same "frame 0 skipped, by
# design" behavior as resize_test.py. Assert the resulting trend instead of
# exact frame-0 presence.
a = Rectangle(width=1, height=1)
b = Rectangle(width=1, height=1).opacity(0).hide()
crossfade(a, b, duration=0.5)

aOps = framesWith(a.meta.index, "Opacity")
bOps = framesWith(b.meta.index, "Opacity")
aVals = [e["args"]["opacity"] for _, e in sorted(aOps.items())]
bVals = [e["args"]["opacity"] for _, e in sorted(bOps.items())]
check("outgoing fades down to 0", aVals[-1] == 0.0 and all(x >= y for x, y in zip(aVals, aVals[1:])))
check("incoming fades up to 255", bVals[-1] == 255.0 and all(x <= y for x, y in zip(bVals, bVals[1:])))
check("both finish on the same last frame", max(aOps) == max(bOps))
bShows = framesWith(b.meta.index, "Show")
check("incoming is shown", len(bShows) == 1)

# ---------------------------------------------------------------------------
section("push — outgoing exits, incoming enters from the opposite side")

out = Rectangle(width=1, height=1).position(0.0, 0.0)
inc = Rectangle(width=1, height=1).position(0.0, 0.0).hide()
push(out, inc, direction=Direction.LEFT, distance=2.0, duration=0.5)

outPos = framesWith(out.meta.index, "Position")
incPos = framesWith(inc.meta.index, "Position")
outXs = [e["args"]["x"] for _, e in sorted(outPos.items())]
incXs = [e["args"]["x"] for _, e in sorted(incPos.items())]
check("outgoing exits toward the left", outXs[-1] < outXs[0])
check("incoming enters from the right, lands at 0", incXs[0] > 0.0 and abs(incXs[-1]) < 1e-6)
check("outgoing ends 2 units left", abs(outXs[-1] - (-2.0)) < 1e-6)

# ---------------------------------------------------------------------------
section("wipeBetween — reveal sweep, outgoing hidden after")

o2 = Rectangle(width=1, height=1)
i2 = Rectangle(width=1, height=1).hide()
wipeBetween(o2, i2, direction=Direction.LEFT, duration=0.5)

crops = framesWith(i2.meta.index, "Crop")
rightVals = [e["args"]["right"] for _, e in sorted(crops.items())]
check("incoming crop sweeps 100 -> 0", abs(rightVals[0] - 100) < 1e-6 and abs(rightVals[-1]) < 1e-6)
hides = framesWith(o2.meta.index, "Hide")
check("outgoing hidden once the wipe completes", len(hides) == 1 and max(hides) >= max(crops))

# ---------------------------------------------------------------------------
section("blink — opacity off and on `times` times, ends at the original")

bl = Rectangle(width=1, height=1).opacity(200)
bl.apply(blink(times=3, duration=1.5))
blOps = framesWith(bl.meta.index, "Opacity")
blVals = [e["args"]["opacity"] for _, e in sorted(blOps.items())]
blChanges = [v for prev, v in zip([200.0] + blVals, blVals) if v != prev]
check("six opacity changes, alternating 0 and the original", blChanges == [0, 200] * 3)
check("last frame is visible at the original opacity", blVals[-1] == 200)
check("all blinks fit in the duration", max(blOps) - min(blOps) < 1.5 * FRAMERATE)
check("meta ends at the original opacity", bl.meta.opacity == 200)

bs = Rectangle(width=1, height=1).opacity(200)
bs.apply(blink(times=3, start=0.5, duration=1.5))
bsOps = framesWith(bs.meta.index, "Opacity")
offs = sorted(f for f, e in bsOps.items() if e["args"]["opacity"] == 0)
ons = sorted(f for f, e in bsOps.items() if f > 0 and e["args"]["opacity"] == 200)
check("blink r goes off at start + r * duration / times", offs == [round((0.5 + r * 0.5) * FRAMERATE) for r in range(3)])
check("and comes back on half a period later", ons == [round((0.75 + r * 0.5) * FRAMERATE) for r in range(3)])

bd = Rectangle(width=1, height=1).opacity(200)
bd.apply(blink())
be = Rectangle(width=1, height=1).opacity(200)
be.apply(blink(times=3, start=0, duration=1.5))
check("the defaults are times=3, start=0, duration=1.5", framesWith(bd.meta.index, "Opacity") == framesWith(be.meta.index, "Opacity"))

# ---------------------------------------------------------------------------
summary()
