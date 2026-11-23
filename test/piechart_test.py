#!/usr/bin/env python3

"""
`PieChart` — slices whose angles nobody added up by hand.

Two sums have to come out whole. The angles add up to 360, because a pie with
a gap or an overlap is a drawing error anyone sees. The percentages add up to
100, because three thirds rounded one by one say 99 % and the viewer reads the
missing point as a mistake in the data. They are rounded by largest remainder,
and the expected values below come from an exact `Fraction` run of that rule.

The entrance is checked frame by frame: each slice sweeps open from its own
start angle and stays pinned to the pie's centre while its outline changes,
and its label comes on when the slice is open.

Run directly: `python3 test/piechart_test.py`
"""

import math
import os
import sys
import tempfile

sys.path.insert(0, ".")
sys.path.insert(0, "test")
from helpers import check, section, summary

from videocode.constants import BLUE_A, BLUE_C, FRAMERATE, GREEN_A, RED_A, RED_B, TRANSPARENT, YELLOW
from videocode.context import Context
from videocode.input.interface.Group import Group
from videocode.serialize import _resetContext
from videocode.template.input.BarChart import BarChart
from videocode.template.input.PieChart import PieChart
from videocode.utils.bezier import Easing


def approx(a: float, b: float, eps: float = 1e-6) -> bool:
    return abs(a - b) <= eps


def refused(build) -> str:
    """The message of the `ValueError` that `build()` raises, or '' when it raises none."""
    try:
        build()
    except ValueError as error:
        return str(error)
    return ""


def frames(inp, key: str) -> list[int]:
    """The frames on which this input's own slot carries `key`."""
    entry = Context.stack[inp.meta.index]
    return sorted(frame for frame, keys in entry.items() if frame != -1 and key in keys)


def centre(points) -> tuple[float, float]:
    """The middle of the box around these points — where the renderer puts a closed shape's position."""
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


def world(slice_, points, at) -> list[tuple[float, float]]:
    """Where these points of a closed shape are drawn, with the shape at `at` (its scale and rotation as now)."""
    cx, cy = centre(points)
    turn = math.radians(-slice_.meta.rotation)
    sx, sy = slice_.meta.scale.x, slice_.meta.scale.y
    out = []
    for x, y in points:
        dx, dy = (x - cx) * sx, (y - cy) * sy
        out.append((at[0] + dx * math.cos(turn) - dy * math.sin(turn), at[1] + dx * math.sin(turn) + dy * math.cos(turn)))
    return out


def pinned(points, hub, radius) -> bool:
    """A pie's slice as drawn: one corner at the hub, and no point past the rim."""
    distances = [math.hypot(x - hub[0], y - hub[1]) for x, y in points]
    return min(distances) < 1e-6 and max(distances) <= radius + 1e-6


def angleOf(x: float, y: float) -> float:
    return math.degrees(math.atan2(y, x)) % 360


# ── The angles ─────────────────────────────────────────────────────────────
section("one slice per row, the angles in proportion and adding up to 360")
_resetContext()
pie = PieChart({"a": 1, "b": 2, "c": 3, "d": 4}, radius=2)
check("one slice and one label per row", len(pie.slices) == 4 and len(pie.labels) == 4)
check("each angle is 360 times its share", all(approx(a, b) for a, b in zip(pie.angles, [36, 72, 108, 144])))
_resetContext()
odd = PieChart({"a": 2, "b": 3, "c": 5, "d": 7})
check("the angles add up to exactly 360, even when no share is round", abs(sum(odd.angles) - 360) < 1e-9)
check("slice by slice, from the top, clockwise", [round(s, 9) for s in pie.starts] == [90, 54, -18, -126])

_resetContext()
back = PieChart({"a": 1, "b": 2, "c": 3, "d": 4}, startAngle=0, clockwise=False)
check("startAngle and clockwise=False turn the other way, from where they are told",
      [round(s, 9) for s in back.starts] == [0, 36, 108, 216])

section("the defaults: a whole pie of radius 1.6, from the top, clockwise, labels at 0.24")
_resetContext()
basic = PieChart({"a": 1, "b": 3})
corners = world(basic.slices[0], basic.slices[0].vertices, (basic.slices[0].meta.position.x, basic.slices[0].meta.position.y))
check("radius 1.6, and no hole: a corner at the centre",
      approx(max(math.hypot(x, y) for x, y in corners), 1.6) and approx(min(math.hypot(x, y) for x, y in corners), 0))
check("from the top, clockwise", basic.starts == [90, 0])
check("labels written at 0.24", all(label.fontSize == 0.24 for label in basic.labels))

section("the slices are drawn where their angles say")
check("a slice's outline is rebuilt the same from its angles", all(s.generateVertices() == s.vertices for s in pie.slices))
# A chord of 3° at 1.6 units (192 px) bows 0.07 px inside the circle.
steps = [min(abs(b - a), 360 - abs(b - a)) for s in pie.slices for (a, b) in zip(*(lambda r: (r, r[1:]))(
    [math.degrees(math.atan2(y, x)) for x, y in s.vertices if math.hypot(x, y) > 1]))]
check(f"the rim is cut into pieces of at most 3° ({max(steps):.3f}°)", max(steps) <= 3 + 1e-9)
_resetContext()
thin = PieChart({"thin": 1, "rest": 199})
check("and into no more pieces than that: a slice under 3° is one straight piece, a 358.2° one is 120",
      [len([v for v in s.vertices if math.hypot(*v) > 1]) for s in thin.slices] == [2, 121])
check("a slice has no outline, so neighbours meet edge to edge",
      all(s.strokeWidth == 0 and s.strokeColor == TRANSPARENT for s in thin.slices))
for i, slice_ in enumerate(pie.slices):
    drawn = world(slice_, slice_.vertices, (slice_.meta.position.x, slice_.meta.position.y))
    radii = [math.hypot(x, y) for x, y in drawn]
    check(f"slice {i}: every point is on the rim or at the centre",
          all(approx(r, 2, 1e-6) or approx(r, 0, 1e-6) for r in radii))
    rim = [angleOf(x, y) for (x, y), r in zip(drawn, radii) if r > 1]
    first, last = pie.starts[i] % 360, (pie.starts[i] - pie.angles[i]) % 360
    check(f"slice {i}: its rim runs from its start angle to its end angle",
          any(approx(a, first, 1e-6) for a in rim) and any(approx(a, last, 1e-6) for a in rim))

_resetContext()
ring = PieChart({"a": 1, "b": 3}, radius=2, donut=0.5)
radii = [math.hypot(x, y) for x, y in world(ring.slices[1], ring.slices[1].vertices,
                                             (ring.slices[1].meta.position.x, ring.slices[1].meta.position.y))]
check("donut=0.5 leaves a hole of half the radius",
      all(approx(r, 2, 1e-6) or approx(r, 1, 1e-6) for r in radii) and any(approx(r, 1, 1e-6) for r in radii))

section("each label sits outside the ring, on its slice's middle angle")
for i, label in enumerate(pie.labels):
    x, y = label.meta.position.x, label.meta.position.y
    middle = (pie.starts[i] - pie.angles[i] / 2) % 360
    check(f"label {i} is past the rim, on the angle {middle:g}",
          math.hypot(x, y) > 2 and approx(angleOf(x, y), middle, 1e-6))

_resetContext()
budget = PieChart({"Rent": 950, "Food": 420, "Travel": 180, "Other": 250}, radius=1.8, donut=0.5)
for label in budget.labels:
    # The box the letters are drawn in, from the first one's edge to the last
    # one's: `Text.width` leaves the spaces out (#387), and a label placed by
    # it sat on the ring in the rendered sheet.
    lefts = [Group._anchorOf(g).x - g.width / 2 for g in label.inputs]
    rights = [Group._anchorOf(g).x + g.width / 2 for g in label.inputs]
    y, half = label.meta.position.y, label.height / 2
    nearX = min(max(0.0, min(lefts)), max(rights))
    nearY = min(max(0.0, y - half), y + half)
    # The pad is 0.6 of the font size, 0.144 here: placed by `Text.width`, the
    # nearest edges stood 1.806, 1.841, 1.775 and 1.981 from the centre.
    check(f"{label.text!r} is drawn clear of the ring ({math.hypot(nearX, nearY):.3f} from the centre, the rim at 1.8)",
          math.hypot(nearX, nearY) > 1.9)
    # Along the middle angle, the label's near side stands 0.6 of the font
    # size off the rim: its middle is that far out, plus half its box.
    middle = math.atan2(label.meta.position.y, label.meta.position.x)
    reach = abs(math.cos(middle)) * (max(rights) - min(lefts)) / 2 + abs(math.sin(middle)) * half
    check(f"{label.text!r} stands 0.6 of the font size off the rim, along its middle angle",
          approx(math.hypot(label.meta.position.x, label.meta.position.y), 1.8 + 0.24 * 0.6 + reach))

# ── The percentages ────────────────────────────────────────────────────────
section("the percentages, rounded by largest remainder, add up to exactly 100")
for data, expected in (
    ([1, 1, 1], [34, 33, 33]),
    ([1, 1, 1, 1, 1, 1], [17, 17, 17, 17, 16, 16]),
    ([2, 3, 5, 7], [12, 18, 29, 41]),
    ([3, 0, 1], [75, 0, 25]),
    ([1, 1, 4], [17, 17, 66]),
):
    _resetContext()
    shares = PieChart([(f"r{i}", v) for i, v in enumerate(data)])
    check(f"{data} → {shares.percents}", shares.percents == expected and sum(shares.percents) == 100)

_resetContext()
thirds = PieChart({"x": 1, "y": 1, "z": 1})
check("the label carries its name and its percentage", [label.text for label in thirds.labels] == ["x 34%", "y 33%", "z 33%"])
_resetContext()
check("showPercent=False leaves the name alone",
      [label.text for label in PieChart({"x": 1, "y": 1}, showPercent=False).labels] == ["x", "y"])
_resetContext()
check("showLabels=False keeps only the percentage",
      [label.text for label in PieChart({"x": 1, "y": 3}, showLabels=False).labels] == ["25%", "75%"])
_resetContext()
check("and with neither, there is no label",
      PieChart({"x": 1, "y": 3}, showLabels=False, showPercent=False).labels == [])

# ── The colours ────────────────────────────────────────────────────────────
section("colours: a palette that cycles, or one per slice")
_resetContext()
many = PieChart([(str(i), 1) for i in range(8)])
fills = [slice_.fillColor for slice_ in many.slices]
check("the palette, in order: the two blues and the two reds apart",
      fills[:6] == [BLUE_C, RED_A, GREEN_A, YELLOW, BLUE_A, RED_B])
check("it starts again once it has gone round", fills[6:] == fills[:2])
_resetContext()
told = PieChart({"a": 1, "b": 2}, colors=[GREEN_A, RED_A])
check("a list gives each slice its colour, in order", [s.fillColor for s in told.slices] == [GREEN_A, RED_A])

# ── The refusals ───────────────────────────────────────────────────────────
section("refused, with the cause named")
for build, needle, why in (
    (lambda: PieChart({}), "at least one row", "no rows at all"),
    (lambda: PieChart({"a": 3, "b": -1, "c": 2}), "'b' is -1", "a negative value"),
    (lambda: PieChart({"a": 0, "b": 0}), "add up to 0", "a data set whose sum is 0"),
    (lambda: PieChart({"a": 1, "b": 2}, donut=1), "donut=1", "a hole as big as the pie"),
    (lambda: PieChart({"a": 1, "b": 2}, donut=-0.2), "donut=-0.2", "a negative hole"),
    (lambda: PieChart({"a": 1, "b": 2, "c": 3}, colors=[RED_A, GREEN_A]), "2 colours for 3 slices", "too few colours"),
):
    _resetContext()
    message = refused(build)
    check(f"{why} is refused ({message})", needle in message)

# ── The entrance ───────────────────────────────────────────────────────────
section("grow() — each slice sweeps open from its start angle, pinned to the centre")


def sweeps(chart: PieChart, i: int) -> dict[int, list[tuple[float, float]]]:
    """Frame → the points of slice i as drawn on that frame, with the position written on it."""
    slice_ = chart.slices[i]
    entry = Context.stack[slice_.meta.index]
    out = {}
    # A position the frame does not write is the one before it, held.
    place = dict(Context.starts.get(slice_.meta.index, {}))
    at = [place.get("Position:x"), place.get("Position:y")]
    for frame in sorted(f for f in entry if f != -1):
        keys = entry[frame]
        written = keys.get("Position", {}).get("args", {})
        at = [at[0] if written.get("x") is None else written["x"], at[1] if written.get("y") is None else written["y"]]
        if "Args:points" in keys:
            out[frame] = world(slice_, keys["Args:points"]["args"]["value"], (at[0], at[1]))
    return out


_resetContext()
growing = PieChart({"a": 1, "b": 2, "c": 3}, radius=2)
growing.grow()  # 0.8 s each, 0.1 s apart, by default
steps = round(0.8 * FRAMERATE)

for i, slice_ in enumerate(growing.slices):
    drawn = sweeps(growing, i)
    order = sorted(drawn)
    begins = round(i * 0.1 * FRAMERATE)
    check(f"slice {i} is hidden from the start, and comes on as it starts opening (shown {frames(slice_, 'Show')})",
          frames(slice_, "Hide") == [0] and len(frames(slice_, "Show")) == 1 and abs(frames(slice_, "Show")[0] - begins) <= 1)
    check(f"slice {i} is written on every frame of its sweep ({len(order)})", len(order) >= steps - 2)
    edge = growing.starts[i] % 360
    rims = {frame: [(x, y) for x, y in drawn[frame] if math.hypot(x, y) > 1] for frame in order}
    check(f"slice {i}: on every frame it has a corner at the pie's centre and nothing past the rim, so it is pinned there",
          all(pinned(drawn[frame], (0, 0), 2) for frame in order))
    check(f"slice {i}: on every frame it opens from its own start angle",
          all(any(approx(angleOf(x, y), edge, 1e-6) for x, y in rims[frame]) for frame in order))
    opens = [max((edge - angleOf(x, y)) % 360 for x, y in rims[frame] if not approx(angleOf(x, y), edge, 1e-6))
             for frame in order]
    check(f"slice {i} only ever opens", all(a <= b + 1e-9 for a, b in zip(opens, opens[1:])))
    check(f"slice {i} ends at its full angle ({opens[-1]:.4f} of {growing.angles[i]:g})",
          approx(opens[-1], growing.angles[i], 1e-6))
    check(f"label {i} comes on when its slice is open (frame {order[-1]})",
          frames(growing.labels[i].inputs[0], "Show") == [order[-1]]
          and frames(growing.labels[i].inputs[0], "Hide") == [0])
    check(f"slice {i} opens over the duration asked for", order[-1] - begins <= steps)

_resetContext()
moved = PieChart({"a": 1, "b": 2}, radius=2)
moved.position(x=3, y=1)
moved.rotation(90)
moved.scale(1.5)
# The first corner of a pie's slice is the pie's centre: where it is drawn now,
# before the entrance, is where every frame of the entrance has to keep it.
hubs = [world(s, s.vertices, (s.meta.position.x, s.meta.position.y))[0] for s in moved.slices]
check(f"moved, turned and scaled, the two slices still share a centre ({hubs[0][0]:.4f}, {hubs[0][1]:.4f})",
      approx(hubs[0][0], hubs[1][0]) and approx(hubs[0][1], hubs[1][1]))
moved.grow(duration=0.4, every=0)
for i in range(2):
    drawn = sweeps(moved, i)
    check(f"moved, turned and scaled first: slice {i} still grows about that centre, on all {len(drawn)} frames",
          len(drawn) > 5 and all(pinned(points, hubs[0], 3) for points in drawn.values()))

_resetContext()
nothing = PieChart({"a": 3, "none": 0, "b": 1}, radius=2)
nothing.grow(every=0)
check("a slice of 0 never comes on, and its label still does when its sweep is over",
      frames(nothing.slices[1], "Show") == [] and frames(nothing.labels[1].inputs[0], "Show") == [round(0.8 * FRAMERATE) - 1])

_resetContext()
instant = PieChart({"a": 1, "b": 3}, radius=2)
instant.grow(duration=0, every=0)
check("duration=0 opens every slice and shows every label on the one frame it has",
      all(frames(s, "Show") == [0] for s in instant.slices)
      and all(frames(label.inputs[0], "Show") == [0] for label in instant.labels))

_resetContext()
springy = PieChart({"a": 1, "b": 1}, radius=2)
springy.grow(easing=Easing.Back)
for i in range(2):
    drawn = sweeps(springy, i)
    edge = springy.starts[i] % 360
    widest = max(max(((edge - angleOf(x, y)) % 360 for x, y in points if math.hypot(x, y) > 1 and not approx(angleOf(x, y), edge, 1e-6)), default=0)
                 for points in drawn.values())
    check(f"an easing that overshoots stops slice {i} at its own angle ({widest:.4f} of 180)", widest <= 180 + 1e-6)

# ── From a file ────────────────────────────────────────────────────────────
section("fromCSV — the same reading as BarChart.fromCSV")
with tempfile.TemporaryDirectory() as folder:
    plain = os.path.join(folder, "plain.csv")
    with open(plain, "w") as file:
        file.write("reds,1\nblues,3\n")
    _resetContext()
    fromFile = PieChart.fromCSV(plain, donut=0.4)
    check("columns by number, the options passed on",
          fromFile.rows == [("reds", 1.0), ("blues", 3.0)] and fromFile.percents == [25, 75] and fromFile.donut == 0.4)
    _resetContext()
    check("the rows BarChart reads from the same file", fromFile.rows == BarChart.fromCSV(plain).rows)

    broken = os.path.join(folder, "broken.csv")
    with open(broken, "w") as file:
        file.write("party,seats\nreds,12\nblues,many\n")
    _resetContext()
    message = refused(lambda: PieChart.fromCSV(broken, label="party", value="seats"))
    check(f"a value that is not a number is refused BY LINE ({message})", "broken.csv:3" in message and "many" in message)

summary()
