#!/usr/bin/env python3

"""
Assertion-based tests for the montage effects pack:
- camera moves (punchIn / zoomTo / snapZoom / travelling) and their framing maths
- impact — punch + damped rumble that lands exactly where it started
- whipPan — position throw with a blur that peaks mid-move
- spotlightOn / zoneFocus — the frame-UV spotlight shader binding
- desaturate / glitchBurst / vignetteBeat / scope
- retime — the speedRamp builders that are NOT effects, and decimate (60 -> 30 fps cuts)
- containSize, reframe, probeVideo — the footage helpers a reel starts from
Run directly: `python3 test/montage_effects_test.py`
"""

import subprocess
import sys
import tempfile

sys.path.insert(0, ".")
sys.path.insert(0, "test")
from helpers import check, needsTool, section, summary

from videocode import *
from videocode.template.effect.framing import containSize, framePosition, mediaBox
from videocode.template.effect.ramp import HOLD_NONE, dipAndReturn, holdAfter
from videocode.template.effect.other.camera import punchIn, reframe, snapZoom, travelling, zoomTo
from videocode.template.effect.other.desaturate import desaturate
from videocode.template.effect.other.glitchBurst import glitchBurst
from videocode.template.effect.other.impact import impact
from videocode.template.effect.other.retime import decimate, fastForward, freezeFrame, rewind, slowMotion, speedRamp
from videocode.template.effect.other.scope import scope, unscope
from videocode.template.effect.other.spotlightOn import spotlightOn, zoneFocus
from videocode.template.effect.other.vignetteIn import vignetteBeat, vignetteIn
from videocode.template.effect.other.whipPan import whipPan
from videocode.utils.probe import probeVideo


def framesWith(index: int, key: str) -> dict[int, dict]:
    return {f: entry[key] for f, entry in Context.stack[index].items() if f != -1 and key in entry}


def last(frames: dict[int, dict]) -> dict:
    return frames[max(frames)]["args"]


# ---------------------------------------------------------------------------
section("framing — fractions of the media's own box")

box = Rectangle(width=4, height=2).position(0.0, 0.0)
mb = mediaBox(box)
check("mediaBox reads the vertices", (mb.x, mb.y) == (4.0, 2.0))
centre = framePosition(box, 0.5, 0.5, 1.0)
check("centre maps to the frame centre", abs(centre.x) < 1e-9 and abs(centre.y) < 1e-9)
# Top-left of the media has to travel DOWN-RIGHT to reach the centre of the
# frame: +x, -y. Getting that sign wrong is the classic framing bug.
tl = framePosition(box, 0.0, 0.0, 1.0)
check("top-left frames to (+2, -1)", abs(tl.x - 2.0) < 1e-9 and abs(tl.y + 1.0) < 1e-9)
tl2 = framePosition(box, 0.0, 0.0, 2.0)
check("zoom scales the offset", abs(tl2.x - 4.0) < 1e-9 and abs(tl2.y + 2.0) < 1e-9)

# A shape's `width` is what is DRAWN, already times its scale: a box read from
# it counted the scale twice, and every move on a shape not at scale 1 — the
# second of two chained moves — missed its point by that factor.
scaled = Rectangle(width=4, height=2).position(0.0, 0.0).scale(2)
sb = mediaBox(scaled)
check("mediaBox is the geometry, whatever the scale", (sb.x, sb.y) == (4.0, 2.0))
tls = framePosition(scaled, 0.0, 0.0, 1.0)
check("a scaled shape counts its scale once", abs(tls.x - 4.0) < 1e-9 and abs(tls.y + 2.0) < 1e-9)

# ---------------------------------------------------------------------------
section("punchIn — scale only, position untouched")

p = Rectangle(width=2, height=1).position(1.0, 1.0)
before = set(framesWith(p.meta.index, "Position"))
p.apply(punchIn(zoom=1.5, duration=1.0))
scales = framesWith(p.meta.index, "Scale")
check("punchIn reaches 1.5x", abs(last(scales)["x"] - 1.5) < 1e-6)
# The `.position(1, 1)` above already wrote frame 0; what matters is that the
# effect adds nothing of its own, so a concurrent move survives it.
check("punchIn claims no position of its own", set(framesWith(p.meta.index, "Position")) == before)

# ---------------------------------------------------------------------------
section("zoomTo — the target point lands at the frame centre")

z = Rectangle(width=4, height=2).position(0.0, 0.0)
z.apply(zoomTo(x=0.25, y=0.75, zoom=2.0, duration=1.0))
scales, pos = framesWith(z.meta.index, "Scale"), framesWith(z.meta.index, "Position")
check("zoomTo reaches 2x", abs(last(scales)["x"] - 2.0) < 1e-6)
# (0.25, 0.75) is one quarter left and one quarter down: at 2x that is
# (+2, +1) of correction.
check("zoomTo frames the point", abs(last(pos)["x"] - 2.0) < 1e-6 and abs(last(pos)["y"] - 1.0) < 1e-6)
check("zoom and pan share frames", set(scales) == set(pos))

# ---------------------------------------------------------------------------
section("snapZoom — returns exactly to the original framing")

s = Rectangle(width=4, height=2).position(0.0, 0.0)
s.apply(snapZoom(x=0.2, y=0.2, zoom=3.0, hold=0.5, attack=0.1, release=0.3))
scales, pos = framesWith(s.meta.index, "Scale"), framesWith(s.meta.index, "Position")
check("snapZoom peaks at 3x", abs(max(e["args"]["x"] for e in scales.values()) - 3.0) < 1e-6)
check("snapZoom ends back at 1x", abs(last(scales)["x"] - 1.0) < 1e-6)
check("snapZoom ends back at origin", abs(last(pos)["x"]) < 1e-6 and abs(last(pos)["y"]) < 1e-6)

# ---------------------------------------------------------------------------
section("travelling — fixed zoom, moving frame")

t = Rectangle(width=4, height=2).position(0.0, 0.0)
t.apply(travelling(fromX=0.0, fromY=0.5, toX=1.0, toY=0.5, zoom=2.0, duration=1.0))
scales, pos = framesWith(t.meta.index, "Scale"), framesWith(t.meta.index, "Position")
check("travelling sets the zoom once", len(scales) == 1 and abs(last(scales)["x"] - 2.0) < 1e-6)
xs = [e["args"]["x"] for _, e in sorted(pos.items())]
check("travelling pans left edge -> right edge", abs(xs[0] - 4.0) < 1e-6 and abs(xs[-1] + 4.0) < 1e-6)
check("travelling holds y", all(abs(e["args"]["y"]) < 1e-9 for e in pos.values()))

# ---------------------------------------------------------------------------
section("impact — punch + rumble, back to zero")

i = Rectangle(width=2, height=1).position(0.5, -0.5)
i.apply(impact(zoom=1.4, amplitude=0.2, duration=0.8))
scales, pos = framesWith(i.meta.index, "Scale"), framesWith(i.meta.index, "Position")
check("impact peaks above 1.4x", max(e["args"]["x"] for e in scales.values()) >= 1.4 - 1e-6)
check("impact ends at 1x", abs(last(scales)["x"] - 1.0) < 1e-6)
check("impact ends at its origin", abs(last(pos)["x"] - 0.5) < 1e-6 and abs(last(pos)["y"] + 0.5) < 1e-6)
check("impact actually rumbles", max(abs(e["args"]["x"] - 0.5) for e in pos.values()) > 0.05)

# ---------------------------------------------------------------------------
section("whipPan — blur peaks mid-throw, gone at the ends")

w = Rectangle(width=4, height=2).position(0.0, 0.0)
w.apply(whipPan(toX=1.0, toY=0.5, blur=12, duration=0.6))
blurs = framesWith(w.meta.index, "Blur")
amounts = [e["args"]["strength"] for _, e in sorted(blurs.items())]
check("whipPan blurs", len(amounts) > 0)
check("whipPan blur peaks in the middle", amounts[len(amounts) // 2] == max(amounts))
check("whipPan blur peak <= requested", max(amounts) <= 12 + 1e-6)
check("whipPan ends sharp", max(framesWith(w.meta.index, "Position")) > max(blurs))

# ---------------------------------------------------------------------------
section("spotlight — frame-UV pool of light")

sp = spotlight(x=0.25, y=0.75, width=0.4, height=0.2, corner=0.5, softness=0.02, darkness=0.9)
check("spotlight centre", sp.centerX == 0.25 and sp.centerY == 0.75)
check("spotlight stores half extents", sp.halfWidth == 0.2 and sp.halfHeight == 0.1)
check("spotlight corner/softness/darkness", sp.corner == 0.5 and sp.softness == 0.02 and sp.darkness == 0.9)
# The GLSL reads p[] alphabetically by attribute name. Pin that order here:
# renaming an attribute silently reshuffles the push constants.
check(
    "spotlight attribute order is the documented one",
    sorted(vars(sp)) == ["centerX", "centerY", "corner", "darkness", "halfHeight", "halfWidth", "softness"],
)

sl = Rectangle(width=2, height=1)
sl.apply(spotlightOn(x=0.4, y=0.6, radius=0.2, duration=1.0, fade=0.3))
spots = framesWith(sl.meta.index, "Spotlight")
darks = [e["args"]["darkness"] for _, e in sorted(spots.items())]
check("spotlightOn fades in and back out", darks[0] < darks[len(darks) // 2] and darks[-1] < darks[len(darks) // 2])
check("spotlightOn keeps the pool round", abs(spots[max(spots)]["args"]["halfWidth"] * SCREEN_WIDTH
                                              - spots[max(spots)]["args"]["halfHeight"] * SCREEN_HEIGHT) < 1e-6)

zf = Rectangle(width=2, height=1)
zf.apply(zoneFocus(x=0.5, y=0.5, width=0.6, height=0.4, corner=0.0, duration=1.0))
zones = framesWith(zf.meta.index, "Spotlight")
check("zoneFocus keeps its rectangle", abs(zones[max(zones)]["args"]["halfWidth"] - 0.3) < 1e-6)

# ---------------------------------------------------------------------------
section("desaturate / glitchBurst / vignette / scope")

d = Rectangle(width=1, height=1)
d.apply(desaturate(amount=1.0, duration=1.2, fade=0.3))
grays = [e["args"]["strength"] for _, e in sorted(framesWith(d.meta.index, "Grayscale").items())]
check("desaturate rises then falls", grays[len(grays) // 2] > grays[0] and grays[len(grays) // 2] > grays[-1])

# The hold, not only the two ramps. A fragment shader only applies to the
# frame it is posed on: while the hold was emitted once, the frames in the
# middle got none and the effect vanished between its entrance and its exit —
# visible on screen, invisible to the assertions above, which only looked at
# the start, the middle and the end of the LIST.
dh = Rectangle(width=1, height=1)
dh.apply(desaturate(amount=1.0, duration=1.2, fade=0.3))
held = sorted(framesWith(dh.meta.index, "Grayscale"))
check("desaturate has no gap", held == list(range(min(held), max(held) + 1)))

sh = Rectangle(width=1, height=1)
sh.apply(spotlightOn(x=0.5, y=0.5, radius=0.2, duration=1.2, fade=0.3))
lit = sorted(framesWith(sh.meta.index, "Spotlight"))
check("spotlightOn has no gap", lit == list(range(min(lit), max(lit) + 1)))
check("spotlightOn covers its whole duration", len(lit) >= round(1.2 * FRAMERATE) - 1)

# ... and the gap does not only come from a hold emitted once. A `fade` that
# is not a whole number of frames put the hold half a frame off, and `round()`
# (half to even) sent the emissions to 10, 12, 12, 14, 14...: two shaders on
# one frame, NONE on the next. spotlightOn's default, fade=0.35, is exactly
# 10.5 frames at 30 fps — the assertions above passed because they forced
# fade=0.3. So: the DEFAULT values, and a sweep of awkward fades.
sd = Rectangle(width=1, height=1)
sd.apply(spotlightOn(x=0.5, y=0.5))
byDefault = sorted(framesWith(sd.meta.index, "Spotlight"))
check("spotlightOn has no gap with its defaults",
      byDefault == list(range(min(byDefault), max(byDefault) + 1)))

for awkward in (0.35, 0.25, 0.17, 0.05, 0.383):
    r = Rectangle(width=1, height=1)
    r.apply(spotlightOn(x=0.5, y=0.5, duration=2.0, fade=awkward))
    posed = sorted(framesWith(r.meta.index, "Spotlight"))
    check(f"a {awkward}s fade stays on the frame grid",
          posed == list(range(min(posed), max(posed) + 1)))

# A frame must not get TWO shaders either: that is the other half of the same
# offset, and it wastes a render pass.
doubled = [t for _, t in dipAndReturn(peak=1.0, duration=2.0, fade=0.35)]
poses = [round(t * FRAMERATE) for t in doubled]
check("dipAndReturn poses one shader per frame, and only one",
      len(poses) == len(set(poses)) and poses == list(range(poses[0], poses[0] + len(poses))))
check("dipAndReturn lasts exactly its duration", len(poses) == round(2.0 * FRAMERATE))

g = Rectangle(width=1, height=1)
g.apply(glitchBurst(amount=6, slices=16, seed=7, blocks=30, duration=0.6))
glitches = framesWith(g.meta.index, "Glitch")
check("glitchBurst emits ONE glitch window", len({e["args"]["seed"] for e in glitches.values()}) == 1)
check("glitchBurst keeps its seed", glitches[min(glitches)]["args"]["seed"] == 7)
check("glitchBurst blocks up first", len(framesWith(g.meta.index, "Pixelate")) > 0)

v = Rectangle(width=1, height=1)
v.apply(vignetteBeat(intensity=0.8, duration=1.0))
vs = [e["args"]["intensity"] for _, e in sorted(framesWith(v.meta.index, "Vignette").items())]
check("vignetteBeat opens back up", abs(vs[0]) < 1e-6 and abs(vs[-1]) < 1e-6 and max(vs) > 0.7)

vi = Rectangle(width=1, height=1)
vi.apply(vignetteIn(intensity=0.5, duration=1.0))
check("vignetteIn persists at full intensity",
      abs([e["args"]["intensity"] for _, e in sorted(framesWith(vi.meta.index, "Vignette").items())][-1] - 0.5) < 1e-6)

sc = Rectangle(width=1, height=1)
sc.apply(scope(ratio=2.39, duration=0.5))
bars = [e["args"]["top"] for _, e in sorted(framesWith(sc.meta.index, "Crop").items())]
expected = max(0.0, (1.0 - (SCREEN_WIDTH / 2.39) / SCREEN_HEIGHT) / 2) * 100
check("scope closes to the 2.39:1 bar height", abs(bars[-1] - expected) < 1e-6)
check("scope starts from nothing", abs(bars[0]) < 1e-6)

us = Rectangle(width=1, height=1)
us.apply(unscope(ratio=2.39, duration=0.5))
openBars = [e["args"]["top"] for _, e in sorted(framesWith(us.meta.index, "Crop").items())]
check("unscope opens back to zero", abs(openBars[-1]) < 1e-6 and abs(openBars[0] - expected) < 1e-6)

# A ratio narrower than the frame closes from the SIDES, as `letterbox` does.
# The bars used to clamp to zero there, so `scope(ratio=1)` did nothing.
side = (1.0 - SCREEN_HEIGHT / SCREEN_WIDTH) / 2 * 100
sq = Rectangle(width=1, height=1)
sq.apply(scope(ratio=1, duration=0.5))
square = last(framesWith(sq.meta.index, "Crop"))
check("scope(ratio=1) closes from the left and the right",
      abs(square["left"] - side) < 1e-6 and abs(square["right"] - side) < 1e-6)
check("scope(ratio=1) leaves top and bottom alone", square["top"] == 0 and square["bottom"] == 0)
check("a wide ratio leaves the sides alone", last(framesWith(sc.meta.index, "Crop"))["left"] == 0)

uq = Rectangle(width=1, height=1)
uq.apply(unscope(ratio=1, duration=0.5))
openSides = [e["args"]["left"] for _, e in sorted(framesWith(uq.meta.index, "Crop").items())]
check("unscope(ratio=1) opens the sides back", abs(openSides[0] - side) < 1e-6 and abs(openSides[-1]) < 1e-6)

# A "look" has to HOLD after its move. A shader posed on a frame with the
# default one-frame duration stops applying on the next one: the bars sprang
# back open the second the move ended. In the reel, the 0.2 s between the end
# of `scope` and the start of `unscope` let the full image come back, then the
# bars slammed shut again — a clearly visible flicker. The assertions before
# could not see it: they only looked at the VALUES emitted, never at how long
# they last.
sh = Rectangle(width=1, height=1)
sh.apply(scope(ratio=2.39, duration=0.6, hold=1.5))
posed = {f: e["args"] for f, e in sorted(framesWith(sh.meta.index, "Crop").items())}
landing = max(posed)
check("scope holds its bars after the move", posed[landing]["duration"] > 1)
check("scope lands on the frame right after the animation",
      landing == int(0.6 * FRAMERATE) and sorted(posed) == list(range(0, landing + 1)))
check("scope holds at the right value", abs(posed[landing]["top"] - expected) < 1e-6)

uh = Rectangle(width=1, height=1)
uh.apply(unscope(ratio=2.39, duration=0.6, hold=1.5))
openPosed = {f: e["args"] for f, e in sorted(framesWith(uh.meta.index, "Crop").items())}
check("unscope holds the frame open", openPosed[max(openPosed)]["duration"] > 1
      and abs(openPosed[max(openPosed)]["top"]) < 1e-6)

vh = Rectangle(width=1, height=1)
vh.apply(vignetteIn(intensity=0.5, duration=0.6, hold=1.5))
vPosed = {f: e["args"] for f, e in sorted(framesWith(vh.meta.index, "Vignette").items())}
check("vignetteIn holds when asked to",
      vPosed[max(vPosed)]["duration"] > 1 and abs(vPosed[max(vPosed)]["intensity"] - 0.5) < 1e-6)

# And the hold costs film length: `apply` grows the film to cover the end of
# every shader. A hold "forever" would render a film that long — measured: a
# one-hour hold turned a 33.8 s reel into 217980 frames. Hence the default of
# zero.
hf = Rectangle(width=1, height=1)
before = Context.lastEverAffectedFrame
hf.apply(scope(ratio=2.39, duration=0.6, hold=4))
check("the hold lengthens the film by exactly what was asked",
      Context.lastEverAffectedFrame == int(0.6 * FRAMERATE) + round(4 * FRAMERATE))


nh = Rectangle(width=1, height=1)
nh.apply(scope(ratio=2.39, duration=0.6))
check("by default, no hold: the film is not lengthened behind the author's back",
      all(e["args"]["duration"] == 1 for e in framesWith(nh.meta.index, "Crop").values()))

# ---------------------------------------------------------------------------
section("holdAfter — one shader, on the frame after the move")

kept = list(holdAfter(crop(top=5, bottom=5), 1.0, 0.6, 1.5))
check("holdAfter poses ONE shader", len(kept) == 1)
check("holdAfter lands on the frame right after the animation",
      round(kept[0].start * FRAMERATE) == FRAMERATE + int(0.6 * FRAMERATE))
check("holdAfter keeps it for the hold asked", kept[0].duration == 1.5)
# 0.05 s is 1.5 frames: the move emits ONE frame, so the hold belongs on frame
# 1. Anchored in seconds it would round to frame 2 and leave a frame bare.
check("holdAfter counts the landing in frames, not seconds",
      round(next(holdAfter(crop(), 0, 0.05, 1)).start * FRAMERATE) == 1)
check("no hold, no shader", list(holdAfter(crop(), 0, 0.6, HOLD_NONE)) == [])

# ---------------------------------------------------------------------------
section("retime — speedRamp builders, in seconds")

check("speedRamp turns seconds into playback frames", speedRamp(at=1, duration=2, rate=0.5) == (FRAMERATE, 3 * FRAMERATE, 0.5))
check("speedRamp rounds to the nearest frame", speedRamp(at=0.51, duration=0.98, rate=2)[:2] == (round(0.51 * FRAMERATE), round(1.49 * FRAMERATE)))
check("a zero-length window still spans one frame", speedRamp(at=1, duration=0, rate=1)[:2] == (FRAMERATE, FRAMERATE + 1))
check("slowMotion slows", slowMotion(at=1, duration=2, rate=0.4) == (FRAMERATE, 3 * FRAMERATE, 0.4))
check("fastForward speeds up", fastForward(at=0, duration=1, rate=4)[2] == 4.0)
check("freezeFrame holds", freezeFrame(at=2, duration=1)[2] == 0.0)
check("rewind goes backwards", rewind(at=2, duration=1)[2] < 0)
check("the builders are speedRamp with a rate of their own",
      slowMotion(at=1, duration=2) == speedRamp(at=1, duration=2, rate=0.4)
      and fastForward(at=1, duration=2) == speedRamp(at=1, duration=2, rate=4))

# A Video accepts them as-is — that is the whole contract.
ramps = [slowMotion(at=0, duration=1), fastForward(at=2, duration=1), freezeFrame(at=4, duration=1)]
check("Video accepts the builders' output", all(isinstance(r, tuple) and len(r) == 3 for r in ramps))

# ---------------------------------------------------------------------------
section("decimate — one source frame out of `ratio`")

def keptFrames(first: int, frames: int, ratio: float) -> list[int]:
    cuts = decimate(first, frames, ratio)
    end = first + round((frames - 1) * ratio) + 1
    return [f for f in range(first, end) if not any(a <= f < b for a, b in cuts)]

check("a 60 fps source keeps every other frame", keptFrames(100, 10, 2.0) == list(range(100, 120, 2)))
check("as many frames kept as scene frames asked", len(keptFrames(0, 90, 2.0)) == 90)
check("ratio 1 cuts nothing", decimate(5, 20, 1.0) == [])
check("a fractional ratio still keeps one per scene frame", len(keptFrames(0, 50, 2.5)) == 50)
check("cuts are ordered and never overlap",
      all(a < b for a, b in decimate(0, 40, 2.0)) and decimate(0, 40, 2.0) == sorted(decimate(0, 40, 2.0)))

# ---------------------------------------------------------------------------
section("containSize — fits the frame, never stretched")

wide = containSize(WORLD_WIDTH * 2, WORLD_HEIGHT)
check("a source wider than the frame is limited by width", abs(wide.x - WORLD_WIDTH) < 1e-6)
tall = containSize(1322, 1526)
check("a tall source is limited by height", abs(tall.y - WORLD_HEIGHT) < 1e-6 and tall.x < WORLD_WIDTH)
check("aspect ratio preserved", abs(tall.x / tall.y - 1322 / 1526) < 1e-6)

# ---------------------------------------------------------------------------
section("reframe — position (0, 0), scale (1, 1)")

rf = Rectangle(width=1, height=1)
rf.apply(zoomTo(x=0.2, y=0.8, zoom=2.0, duration=0.5))
rf.apply(reframe(), at=1)
check("reframe poses position (0, 0)", last(framesWith(rf.meta.index, "Position")) == {"x": 0, "y": 0} or
      tuple(last(framesWith(rf.meta.index, "Position")).values())[:2] == (0, 0))
check("reframe poses scale (1, 1)", tuple(last(framesWith(rf.meta.index, "Scale")).values())[:2] == (1, 1))

# ---------------------------------------------------------------------------
section("probeVideo — size and average frame rate")

if needsTool("ffmpeg", "probeVideo reads a real clip") and needsTool("ffprobe", "probeVideo reads a real clip"):
    with tempfile.TemporaryDirectory() as tmp:
        clipPath = f"{tmp}/probe.mp4"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=64x48:r=25:d=1", "-pix_fmt", "yuv420p", clipPath],
            check=True,
        )
        check("probeVideo reads width, height and fps", probeVideo(clipPath) == (64.0, 48.0, 25.0))

# ---------------------------------------------------------------------------
summary()
