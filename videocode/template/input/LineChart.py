#!/usr/bin/env python3

"""
Data as a line, and the dot that waits for it.

A hand-written line chart is a polyline, a dot per point, a label under each
one and a number over it, with the scale worked out by hand. Its entrance is
where it goes wrong: the dots and numbers are separate inputs that stand there
from the first frame, and the line crawls past them. Here the line is drawn
from the first point to the last, and each dot and its number come on at the
frame the line reaches them.
"""

from __future__ import annotations

from videocode.constants import *
from videocode.input.interface.Group import Group
from videocode.input.shape.Circle import Circle
from videocode.input.shape.Curve import Curve
from videocode.input.shape.text.Text import Text
from videocode.template.input.BarChart import BarChart, _readCSV, _rows
from videocode.utils.bezier import Easing, animate, easing
from videocode.utils.classutils import At
from videocode.ty import *

__all__ = ["LineChart"]


class LineChart(Group):
    """
    One point per row of data, joined by a line, with its label under it and its value over it::

        chart = LineChart({"Mon": 2, "Tue": 5, "Wed": 3, "Thu": 8})
        chart.draw()

    The points are evenly spaced across `width`, the first at the left edge and
    the last at the right. The y scale runs from `bottom` at the baseline to
    `top` at `height` above it: the highest value is exactly `height` up unless
    `top` is given, and a value outside the two is refused by its row. `bottom`
    is 0 by default, as a bar chart's baseline is — a line whose axis starts at
    its lowest value makes every change look steep, so that stays a choice the
    author writes down.

    Built complete, like every other input: `draw()` is the entrance. The chart
    is centred on the group's position, so `chart.position(...)`, `scaleTo`,
    `fadeIn` and the rest work on the whole of it.
    """

    def __init__(
        self,
        data: dict[str, number] | list[tuple[str, number]],
        *,
        width: wunumber = 8,
        height: wunumber = 3.5,
        top: maybe[number] = None,
        bottom: number = 0,
        color: rgba = BLUE_C,
        fontSize: number = 0.28,
        showValues: bool = True,
        dots: bool = True,
        strokeWidth: wufloat = 0.05,
    ) -> None:
        self.rows = _rows(data)
        if not self.rows:
            raise ValueError("LineChart needs at least one row of data")

        highest = max(value for _, value in self.rows)
        self.top = top if top is not None else highest
        self.bottom = bottom
        # The row is named, because "a value is out of range" in a chart of
        # forty rows sends the author reading all forty.
        for name, value in self.rows:
            if value < bottom:
                raise ValueError(
                    f"LineChart row {name!r} is {BarChart._say(value)}, below the bottom of {BarChart._say(bottom)} — "
                    f"pass bottom= at or under the lowest value"
                )
            if value > self.top:
                raise ValueError(
                    f"LineChart row {name!r} is {BarChart._say(value)}, above the top of {BarChart._say(self.top)} — "
                    f"pass top= at or over the highest value"
                )
        if self.top <= bottom:
            raise ValueError(
                f"LineChart cannot draw a top of {BarChart._say(self.top)} over a bottom of {BarChart._say(bottom)} — "
                f"the scale needs the top above the bottom"
            )

        count = len(self.rows)
        self.baseline = -height / 2
        self.pad = fontSize * 0.6
        span = self.top - bottom

        def x(i: int) -> float:
            return 0.0 if count == 1 else -width / 2 + i * width / (count - 1)

        self.points: list[point] = [
            (x(i), self.baseline + height * (value - bottom) / span) for i, (_, value) in enumerate(self.rows)
        ]

        # Placed on the middle of what it covers, its vertices relative to it:
        # an open path is drawn at position + vertex, while a group measures a
        # member around its position — this is where both agree.
        ys = [py for _, py in self.points]
        self.centre: point = (0.0, (min(ys) + max(ys)) / 2)
        self.line = Curve(self._local(self.points), strokeColor=color, strokeWidth=strokeWidth).position(*self.centre)

        self.dots: list[Circle] = []
        self.labels: list[Text] = []
        self.values: list[Text] = []
        for (name, value), (px, py) in zip(self.rows, self.points):
            if dots:
                self.dots.append(
                    Circle(radius=strokeWidth * 1.8, fillColor=color, strokeColor=TRANSPARENT, strokeWidth=0).position(x=px, y=py)
                )
            self.labels.append(
                Text(text=str(name), fontSize=fontSize).position(x=px, y=self.baseline - self.pad - fontSize / 2)
            )
            if showValues:
                self.values.append(
                    Text(text=BarChart._say(value), fontSize=fontSize).position(x=px, y=py + self.pad + fontSize / 2)
                )

        super().__init__(self.line, *self.dots, *self.labels, *self.values)

    def _local(self, points: list[point]) -> list[point]:
        return [(px - self.centre[0], py - self.centre[1]) for px, py in points]

    @classmethod
    def fromCSV(cls, path: str, *, label: str | int = 0, value: str | int = 1, **options) -> "LineChart":
        """
        The same chart, read from a file, with `BarChart.fromCSV`'s rules::

            LineChart.fromCSV("sales.csv", label="day", value="sales", bottom=100)

        `label` and `value` are column names with a header row and column
        numbers without one, and a cell that is not a number is refused at its line.
        """
        return cls(_readCSV(path, label=label, value=value), **options)

    def draw(self, *, duration: sec = 1.2, easing: easing = Easing.InOut) -> "LineChart":
        """
        The line drawn from the first point to the last, and each dot and value on its arrival.

        Dot `i` and value `i` are hidden until the frame the line reaches
        point `i`, and come on at that frame: a number on screen before its
        point is drawn reads as a point that is already there.
        """
        last = len(self.points) - 1
        marks = [self.dots, self.values]
        for mark in (m for group in marks for m in group):
            mark.hide()
        arrived = [False] * len(self.points)

        def _apply(m: number, i: int) -> None:
            # How far along the line the pen is, in points: 2.5 is halfway from
            # point 2 to point 3. An easing that overshoots stops at the last.
            # The tolerance is for the last frame: an easing's 1 can come back
            # as 0.999…, and the last point has to be reached on it.
            head = min(max(m * last, 0.0), float(last))
            whole = min(int(head + 1e-9), last)
            path = self.points[: whole + 1]
            if head > whole + 1e-9:
                (ax, ay), (bx, by) = self.points[whole], self.points[whole + 1]
                path.append((ax + (bx - ax) * (head - whole), ay + (by - ay) * (head - whole)))
            if len(path) == 1:
                # One vertex is not a path the renderer draws; two at the
                # same place are a line of no length, which it does.
                path.append(path[0])
            self.line.vertices = self._local(path)
            self.line.points = At(start=i * SF, duration=SINGLE_FRAME) | self.line.buildPoints()

            for k in range(whole + 1):
                if not arrived[k]:
                    arrived[k] = True
                    for group in marks:
                        if k < len(group):
                            group[k].show(start=i * SF)

        animate(duration, easing, _apply)
        return self
