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
drawn.draw(duration=1.2)

written = Context.stack[drawn.line.meta.index]
heads = {frame: max(x for x, _ in keys["Args:points"]["args"]["value"]) + drawn.line.meta.position.x
         for frame, keys in written.items() if frame != -1 and "Args:points" in keys}
order = sorted(heads)
check(f"the line is written on every frame of the draw ({len(order)} frames)", len(order) >= round(1.2 * FRAMERATE) - 1)
check("it starts at the first point", approx(heads[order[0]], drawn.dots[0].meta.position.x))
check("it ends at the last point", approx(heads[order[-1]], drawn.dots[-1].meta.position.x))
check("and it only ever extends", all(heads[a] <= heads[b] + 1e-9 for a, b in zip(order, order[1:])))
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

summary()
