#!/usr/bin/env python3

"""
Data as bars, and the number that stays on its bar.

Every hand-written chart in this project's corpus is the same twelve lines: a
rectangle per value, a label under each one, a number beside it, and four
constants worked out by hand from the frame's size. The number is where it goes
wrong — it is a separate `Text` at a fixed place, so the moment the bars grow it
sits over the middle of a bar or off the end of it. Here the number is written
with the same ramp as its bar and arrives where the bar arrives.
"""

from __future__ import annotations

import csv

from videocode.constants import *
from videocode.input.interface.Group import Group
from videocode.input.shape.Rectangle import Rectangle
from videocode.input.shape.text.Text import Text
from videocode.utils.bezier import Easing, easing
from videocode.ty import *

__all__ = ["BarChart", "Leaderboard"]


def _rows(data: dict[str, number] | list[tuple[str, number]]) -> list[tuple[str, number]]:
    return list(data.items()) if isinstance(data, dict) else list(data)


def _readCSV(path: str, *, label: str | int, value: str | int) -> list[tuple[str, number]]:
    """
    The rows of a chart, read from a file — the reading every chart's `fromCSV` shares.

    `label` and `value` are column names when the file has a header row and
    column numbers when it does not. A bad cell is refused at its line.
    """
    with open(path, newline="") as file:
        rows = list(csv.reader(file))
    if not rows:
        raise ValueError(f"{path} has no rows")

    named = isinstance(label, str) or isinstance(value, str)
    header = rows[0] if named else []
    body = rows[1:] if named else rows

    def column(which: str | int) -> int:
        if isinstance(which, int):
            return which
        if which not in header:
            raise ValueError(f"{path} has no column called {which!r} — it has {', '.join(header)}")
        return header.index(which)

    at, of = column(label), column(value)
    data: list[tuple[str, number]] = []
    for line, row in enumerate(body, start=2 if named else 1):
        if len(row) <= max(at, of):
            raise ValueError(f"{path}:{line} has {len(row)} column(s), not enough for this chart")
        try:
            data.append((row[at], float(row[of])))
        except ValueError:
            raise ValueError(f"{path}:{line} says {row[of]!r} where a number was expected") from None
    return data


class BarChart(Group):
    """
    One bar per row of data, with its label under it and its value on it::

        chart = BarChart({"Rust": 82, "Go": 61, "Python": 55})
        chart.grow()

    `width` and `height` are the whole chart in world units (1 unit = 120 px,
    the 1080p world is 16 x 9), and the tallest bar is exactly `height` unless
    `top` says otherwise — pass `top` when several charts have to be read
    against each other, because a bar is only comparable to another bar drawn
    to the same scale.

    Built at its full height, like every other input: `grow()` is what animates
    it, and it moves each value with its own bar. The chart is centred on the
    group's position, so `chart.position(...)`, `scaleTo`, `fadeIn` and the rest
    work on the whole of it.
    """

    def __init__(
        self,
        data: dict[str, number] | list[tuple[str, number]],
        *,
        width: wunumber = 8,
        height: wunumber = 3.5,
        gap: wunumber = 0.3,
        top: maybe[number] = None,
        color: paint = BLUE_C,
        fontSize: number = 0.28,
        showValues: bool = True,
    ) -> None:
        self.rows = _rows(data)
        if not self.rows:
            raise ValueError("BarChart needs at least one row of data")

        # The scale every bar is drawn to. A chart of one value is a full bar,
        # which is the only honest answer: there is nothing to compare it with.
        self.top = top if top is not None else max(value for _, value in self.rows)
        if self.top <= 0:
            raise ValueError(f"BarChart cannot draw a top of {self.top} — the values have to be positive")

        count = len(self.rows)
        barWidth = (width - gap * (count - 1)) / count
        if barWidth <= 0:
            raise ValueError(f"{count} bars and a gap of {gap} do not fit in a width of {width}")

        self.baseline = -height / 2
        self.barWidth = barWidth
        self.pad = fontSize * 0.6

        self.bars: list[Rectangle] = []
        self.labels: list[Text] = []
        self.values: list[Text] = []

        for i, (name, value) in enumerate(self.rows):
            x = -width / 2 + barWidth / 2 + i * (barWidth + gap)
            tall = height * max(0.0, value) / self.top

            self.bars.append(
                Rectangle(width=barWidth, height=tall, fillColor=color, strokeColor=TRANSPARENT, cornerRadius=6)
                .position(x=x, y=self.baseline + tall / 2)
            )
            self.labels.append(
                Text(text=str(name), fontSize=fontSize)
                .position(x=x, y=self.baseline - self.pad - fontSize / 2)
            )
            if showValues:
                self.values.append(
                    Text(text=self._say(value), fontSize=fontSize)
                    .position(x=x, y=self.baseline + tall + self.pad)
                )

        super().__init__(*self.bars, *self.labels, *self.values)

    @staticmethod
    def _say(value: number) -> str:
        """`82`, not `82.0` — the chart writes the number the data had."""
        return str(int(value)) if float(value).is_integer() else str(value)

    @classmethod
    def fromCSV(
        cls,
        path: str,
        *,
        label: str | int = 0,
        value: str | int = 1,
        **options,
    ) -> "BarChart":
        """
        The same chart, read from a file::

            BarChart.fromCSV("votes.csv", label="party", value="seats")

        `label` and `value` are column names when the file has a header row and
        column numbers when it does not. A row whose value is not a number is
        refused by name rather than skipped: a chart missing a bar nobody
        mentioned is the kind of quiet wrong this library exists to avoid.
        """
        return cls(_readCSV(path, label=label, value=value), **options)

    def grow(self, *, duration: sec = 0.8, every: sec = 0.06, easing: easing = Easing.InOut) -> "BarChart":
        """
        Bars up from nothing, each one a moment after the last.

        The value travels with its bar — same start, same duration, same easing
        — because a number that arrives before or after the bar it belongs to is
        the whole reason charts are written by hand twice.
        """
        for i, (bar, (_, value)) in enumerate(zip(self.bars, self.rows)):
            start = i * every
            tall = bar.height
            bar.height = 0
            bar.position(y=self.baseline)
            bar.ease("height", tall, start=start, duration=duration, easing=easing)
            bar.moveTo(y=self.baseline + tall / 2, start=start, duration=duration, easing=easing)

            if i < len(self.values):
                self.values[i].position(y=self.baseline + self.pad)
                self.values[i].moveTo(
                    y=self.baseline + tall + self.pad, start=start, duration=duration, easing=easing
                )
        return self


class Leaderboard(BarChart):
    """
    The same data, biggest first::

        Leaderboard({"Ada": 12, "Grace": 31, "Alan": 22}).grow()

    Sorting is the whole difference, and it is worth its own name: a leaderboard
    read in the order the data happened to be in is not a leaderboard.
    """

    def __init__(self, data: dict[str, number] | list[tuple[str, number]], **options) -> None:
        super().__init__(sorted(_rows(data), key=lambda row: row[1], reverse=True), **options)
