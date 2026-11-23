#!/usr/bin/env python3

"""
`LineChart` — one point per row, and the dot that waits for its line.

The scale is held the way `BarChart` holds it: the highest value is exactly the
height asked for, unless `top` says otherwise, and `bottom` is the floor. The
entrance is the other half. A hand-written line chart shows every dot from the
first frame and lets the line crawl past them; here dot `i` and its value come
on at the frame the line reaches point `i`, and the proof is frame by frame.

Run directly: `python3 test/linechart_test.py`
"""

import os
import sys
import tempfile

sys.path.insert(0, ".")
sys.path.insert(0, "test")
from helpers import check, section, summary

from videocode.constants import FRAMERATE
from videocode.context import Context
from videocode.serialize import _resetContext
from videocode.template.input.BarChart import BarChart
from videocode.template.input.LineChart import LineChart

DATA = {"Mon": 2, "Tue": 5, "Wed": 3, "Thu": 8, "Fri": 6}


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


# ── The scale ──────────────────────────────────────────────────────────────
section("one point per row, the highest at exactly the height asked for")
_resetContext()
chart = LineChart(DATA, width=8, height=4)

check("one dot, one label and one value per row",
      len(chart.dots) == 5 and len(chart.labels) == 5 and len(chart.values) == 5)
check("the points are evenly spaced, the first at the left edge and the last at the right",
      [round(dot.meta.position.x, 9) for dot in chart.dots] == [-4, -2, 0, 2, 4])
check("the highest value is exactly `height` above the baseline",
      approx(chart.dots[3].meta.position.y - chart.baseline, 4))
check("the others are their share of it, from a bottom of 0",
      approx(chart.dots[1].meta.position.y - chart.baseline, 4 * 5 / 8)
      and approx(chart.dots[0].meta.position.y - chart.baseline, 4 * 2 / 8))
check("the baseline is the bottom of the chart", approx(chart.baseline, -2))
check("the labels are under the baseline, each under its point",
      all(label.meta.position.y < chart.baseline for label in chart.labels)
      and all(approx(label.meta.position.x, dot.meta.position.x) for label, dot in zip(chart.labels, chart.dots)))
check("each value is above its point",
      all(value.meta.position.y > dot.meta.position.y and approx(value.meta.position.x, dot.meta.position.x)
          for value, dot in zip(chart.values, chart.dots)))
check("the values are written the way BarChart writes them",
      [value.text for value in chart.values] == ["2", "5", "3", "8", "6"])
check("the line passes through every dot",
      all(approx(chart.line.meta.position.x + vx, dot.meta.position.x)
          and approx(chart.line.meta.position.y + vy, dot.meta.position.y)
          for (vx, vy), dot in zip(chart.line.vertices, chart.dots)))
check("the line is placed on the middle of what it covers, so the group measures it where it is drawn",
      approx(chart.line.meta.position.y, (chart.dots[3].meta.position.y + chart.dots[0].meta.position.y) / 2))

check("and centred across, where the points run from -width/2 to +width/2", chart.line.meta.position.x == 0)

section("the defaults: 8 by 3.5, BarChart's font size, a 0.05 line")
_resetContext()
plain = LineChart(DATA)
pad, size = 0.28 * 0.6, 0.28
check("8 wide, the points from -4 to 4", [round(dot.meta.position.x, 9) for dot in plain.dots] == [-4, -2, 0, 2, 4])
check("3.5 high, the baseline at -1.75 and the highest point at 1.75",
      approx(plain.baseline, -1.75) and approx(plain.dots[3].meta.position.y, 1.75))
check("the line is 0.05 wide and each dot is 1.8 times that, with no outline",
      plain.line.strokeWidth == 0.05 and all(approx(dot.radius, 0.09) and dot.strokeWidth == 0 for dot in plain.dots))
check("labels and values are written at 0.28", all(text.fontSize == size for text in plain.labels + plain.values))
check("a label's middle is 0.6 of the font size under the baseline, plus half a line",
      all(approx(label.meta.position.y, -1.75 - pad - size / 2) for label in plain.labels))
check("a value's middle is the same distance over its point",
      all(approx(value.meta.position.y, dot.meta.position.y + pad + size / 2) for value, dot in zip(plain.values, plain.dots)))

_resetContext()
scaled = LineChart({"a": 5, "b": 2}, height=4, top=10)
check("`top` fixes the scale, so two charts can be read against each other",
      approx(scaled.dots[0].meta.position.y - scaled.baseline, 2))

_resetContext()
floored = LineChart({"a": 10, "b": 20, "c": 15}, height=4, bottom=10)
check("`bottom` is the value drawn at the baseline",
      approx(floored.dots[0].meta.position.y, floored.baseline)
      and approx(floored.dots[2].meta.position.y - floored.baseline, 2))

_resetContext()
alone = LineChart({"only": 3})
check("a single row is one point in the middle", approx(alone.dots[0].meta.position.x, 0))

_resetContext()
bare = LineChart(DATA, showValues=False, dots=False)
check("showValues=False writes no value, dots=False draws no dot", bare.values == [] and bare.dots == [])

# ── The refusals ───────────────────────────────────────────────────────────
section("a value off the scale is refused, by its row")
_resetContext()
message = refused(lambda: LineChart({}))
check(f"no rows at all is refused ({message})", "at least one row" in message)

_resetContext()
message = refused(lambda: LineChart({"Mon": 2, "Tue": -1, "Wed": 3}))
check(f"a value below the bottom names its row ({message})",
      "'Tue'" in message and "-1" in message and "below the bottom of 0" in message)

_resetContext()
message = refused(lambda: LineChart({"Mon": 2, "Tue": 12, "Wed": 3}, top=10))
check(f"a value above the top names its row ({message})",
      "'Tue'" in message and "12" in message and "above the top of 10" in message)

_resetContext()
message = refused(lambda: LineChart({"Mon": 5}, top=5, bottom=5))
check(f"a top that is not above the bottom is refused ({message})",
      "top of 5" in message and "bottom of 5" in message)

# ── The entrance ───────────────────────────────────────────────────────────
section("draw() — dot i and its value arrive with the line, frame by frame")
_resetContext()
drawn = LineChart(DATA, width=8)
drawn.draw()  # 1.2 s by default

written = Context.stack[drawn.line.meta.index]
pointsOf = {frame: keys["Args:points"]["args"]["value"] for frame, keys in written.items()
            if frame != -1 and "Args:points" in keys}
heads = {frame: max(x for x, _ in points) + drawn.line.meta.position.x for frame, points in pointsOf.items()}
order = sorted(heads)
check(f"the line is written on every frame of the draw ({len(order)} frames)", len(order) >= round(1.2 * FRAMERATE) - 1)
check("it starts at the first point", approx(heads[order[0]], drawn.dots[0].meta.position.x))
check("it ends at the last point", approx(heads[order[-1]], drawn.dots[-1].meta.position.x))
check("and its head moves on, frame after frame", all(heads[a] < heads[b] for a, b in zip(order, order[1:])))
# An open path's points are anchor and handle in turn, last vertex first
# (`Polygon.buildPoints`): the anchors of a line drawn left to right are in
# falling x, and a path the renderer draws has at least four points.
check("on every frame the path runs one way only, and is long enough for the renderer to draw",
      all(len(points) >= 4 and all(a[0] >= b[0] for a, b in zip(points[0::2], points[2::2]))
          for points in pointsOf.values()))


def onTheLine(x: float, y: float) -> bool:
    """Whether (x, y) is on the straight segment between the two points either side of x."""
    xs = [dot.meta.position.x for dot in drawn.dots]
    ys = [dot.meta.position.y for dot in drawn.dots]
    k = min(max(0, next(i for i in range(len(xs)) if xs[i] >= x - 1e-9) - 1), len(xs) - 2)
    share = (x - xs[k]) / (xs[k + 1] - xs[k])
    return approx(y, ys[k] + (ys[k + 1] - ys[k]) * share)


ends = {frame: max(keys["Args:points"]["args"]["value"]) for frame, keys in written.items()
        if frame != -1 and "Args:points" in keys}
check("between two points, the pen is on the straight line that joins them",
      all(onTheLine(x + drawn.line.meta.position.x, y + drawn.line.meta.position.y) for x, y in ends.values()))
check("the draw lasts as long as it was asked to", order[-1] <= round(1.2 * FRAMERATE) + 1)

for i, dot in enumerate(drawn.dots):
    reached = next(frame for frame in order if heads[frame] >= dot.meta.position.x - 1e-6)
    shown = frames(dot, "Show")
    glyph = drawn.values[i].inputs[0]
    check(f"dot {i} comes on at the frame the line reaches it (frame {reached}, shown {shown})",
          len(shown) == 1 and abs(shown[0] - reached) <= 1)
    check(f"and is hidden until then (dot {i})", reached == 0 or frames(dot, "Hide") == [0])
    check(f"value {i} comes on with its dot", frames(glyph, "Show") == shown)

# ── From a file ────────────────────────────────────────────────────────────
section("fromCSV — the same reading as BarChart.fromCSV")
with tempfile.TemporaryDirectory() as folder:
    named = os.path.join(folder, "week.csv")
    with open(named, "w") as file:
        file.write("day,sales\nMon,2\nTue,5\n")
    _resetContext()
    fromFile = LineChart.fromCSV(named, label="day", value="sales", height=2)
    check("columns by name, the options passed on",
          fromFile.rows == [("Mon", 2.0), ("Tue", 5.0)] and approx(fromFile.dots[1].meta.position.y - fromFile.baseline, 2))
    _resetContext()
    check("the rows BarChart reads from the same file",
          fromFile.rows == BarChart.fromCSV(named, label="day", value="sales").rows)

    broken = os.path.join(folder, "broken.csv")
    with open(broken, "w") as file:
        file.write("day,sales\nMon,2\nTue,many\n")
    _resetContext()
    message = refused(lambda: LineChart.fromCSV(broken, label="day", value="sales"))
    check(f"a value that is not a number is refused BY LINE ({message})",
          "broken.csv:3" in message and "many" in message)

    # The shared reading's other rules, checked here because they moved out
    # of BarChart.fromCSV into the helper all three charts call.
    _resetContext()
    check("one column named is enough to say the file has a header row",
          LineChart.fromCSV(named, label="day", value=1).rows == [("Mon", 2.0), ("Tue", 5.0)])

    bare = os.path.join(folder, "bare.csv")
    with open(bare, "w") as file:
        file.write("Mon,2\nTue,5\n")
    _resetContext()
    check("with no header, the first column is the label and the second the value",
          LineChart.fromCSV(bare).rows == [("Mon", 2.0), ("Tue", 5.0)])

    badBare = os.path.join(folder, "badbare.csv")
    with open(badBare, "w") as file:
        file.write("Mon,2\nTue,lots\n")
    _resetContext()
    message = refused(lambda: LineChart.fromCSV(badBare))
    check(f"with no header, the lines count from 1 ({message})", "badbare.csv:2" in message and "lots" in message)

    short = os.path.join(folder, "short.csv")
    with open(short, "w") as file:
        file.write("day,sales\nMon,2\nTue\n")
    _resetContext()
    message = refused(lambda: LineChart.fromCSV(short, label="day", value="sales"))
    check(f"a row with too few cells is refused at its line ({message})",
          "short.csv:3 has 1 column(s)" in message)

    empty = os.path.join(folder, "empty.csv")
    with open(empty, "w") as file:
        file.write("")
    _resetContext()
    message = refused(lambda: LineChart.fromCSV(empty))
    check(f"an empty file is refused ({message})", "empty.csv has no rows" in message)

summary()
