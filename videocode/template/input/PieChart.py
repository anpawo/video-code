#!/usr/bin/env python3

"""
Data as slices of a pie, and the two sums that have to come out whole.

Drawn by hand, a pie chart is a wedge per value whose angles someone added up,
and two things go wrong. The angles leave a gap or an overlap where the last
slice meets the first. The percentages, rounded one by one, add up to 99 or 101,
and a viewer reads the missing point as a mistake in the data. Here the angles
come from the running total, so they close the circle, and the percentages are
rounded by largest remainder, so they add up to 100.
"""

from __future__ import annotations

import math

from videocode.constants import *
from videocode.input.interface.Group import Group
from videocode.input.shape.Polygon import Polygon
from videocode.input.shape.text.Text import Text
from videocode.shader.vertexShader.position import position
from videocode.template.input.BarChart import BarChart, _readCSV, _rows
from videocode.utils.bezier import Easing, animate, easing
from videocode.utils.classutils import At
from videocode.ty import *

__all__ = ["PieChart"]

# Neighbours that are not alike: the two blues and the two reds are apart.
PALETTE: tuple[rgba, ...] = (BLUE_C, RED_A, GREEN_A, YELLOW, BLUE_A, RED_B)

# The rim is cut into straight pieces of at most this many degrees. At a radius
# of 1.6 units (192 px) a 3° chord is 0.07 px inside the true circle.
_STEP = 3.0


def _ring(start: float, sweep: float, outer: float, inner: float) -> list[point]:
    """The outline of a slice: `sweep` degrees from `start`, negative for clockwise, between two radii."""
    steps = max(1, math.ceil(abs(sweep) / _STEP))
    angles = [math.radians(start + sweep * j / steps) for j in range(steps + 1)]
    rim = [(outer * math.cos(a), outer * math.sin(a)) for a in angles]
    if inner > 0:
        return rim + [(inner * math.cos(a), inner * math.sin(a)) for a in reversed(angles)]
    return [(0.0, 0.0)] + rim


def _centre(points: list[point]) -> point:
    """The middle of the box around `points` — what the renderer puts at a closed shape's position."""
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)


def _wide(text: Text) -> float:
    """
    How wide a label is drawn: from its first letter's left edge to its last letter's right edge.

    `Text.width` adds up the letters' own widths and leaves the spaces out
    (#387): "Rent 53%" measured 1.14 and was drawn 1.44 wide, and its label
    sat on the ring.
    """
    edges = [(Group._anchorOf(letter).x - letter.width / 2, Group._anchorOf(letter).x + letter.width / 2) for letter in text.inputs]
    return max(right for _, right in edges) - min(left for left, _ in edges)


def _percents(values: list[number]) -> list[int]:
    """Whole percentages that add up to exactly 100: the floors, and the points left over to the largest remainders."""
    total = sum(values)
    shares = [100 * value / total for value in values]
    whole = [math.floor(share) for share in shares]
    left = 100 - sum(whole)
    for i in sorted(range(len(values)), key=lambda i: (-(shares[i] - whole[i]), i))[:left]:
        whole[i] += 1
    return whole


class _Slice(Polygon):
    """One slice, its outline in the pie's own coordinates and the pie's centre at (0, 0)."""

    def __init__(self, start: float, sweep: float, outer: float, inner: float, fillColor: paint) -> None:
        self.start, self.sweep, self.outer, self.inner = start, sweep, outer, inner
        super().__init__(vertices=self.generateVertices(), fillColor=fillColor, strokeColor=TRANSPARENT, strokeWidth=0)

    def generateVertices(self) -> list[point]:
        """The whole slice, opened to its full angle — `grow()` writes the frames on the way there."""
        return _ring(self.start, self.sweep, self.outer, self.inner)


class PieChart(Group):
    """
    One slice per row of data, its label outside the ring::

        chart = PieChart({"Rent": 950, "Food": 420, "Travel": 180}, donut=0.5)
        chart.grow()

    The slices follow the data's order from `startAngle` (degrees, 90 is the
    top), clockwise unless `clockwise=False`. A slice's angle is `360 * value /
    sum`, and the angles close the circle exactly. `donut` is the hole's radius
    as a fraction of `radius`, from 0 (a pie) up to but not including 1.

    `colors=None` cycles a fixed palette; a list gives each slice its colour in
    order. The label carries the row's name when `showLabels` is on and its
    percentage when `showPercent` is on — the percentages are whole numbers
    that add up to exactly 100, rounded by largest remainder.

    Built complete, like every other input: `grow()` is the entrance. The pie is
    centred on the group's position, so `chart.position(...)`, `scaleTo`,
    `fadeIn` and the rest work on the whole of it.
    """

    def __init__(
        self,
        data: dict[str, number] | list[tuple[str, number]],
        *,
        radius: wunumber = 1.6,
        colors: maybe[list[paint]] = None,
        donut: float = 0,
        startAngle: number = 90,
        clockwise: bool = True,
        fontSize: number = 0.24,
        showLabels: bool = True,
        showPercent: bool = True,
    ) -> None:
        self.rows = _rows(data)
        if not self.rows:
            raise ValueError("PieChart needs at least one row of data")
        for name, value in self.rows:
            if value < 0:
                raise ValueError(f"PieChart row {name!r} is {BarChart._say(value)} — a slice cannot be smaller than nothing")
        total = sum(value for _, value in self.rows)
        if total == 0:
            raise ValueError("PieChart's values add up to 0 — there is no whole to cut into slices")
        if not 0 <= donut < 1:
            raise ValueError(f"PieChart donut={donut} is outside 0 <= donut < 1 — it is the hole's radius as a fraction of the pie's")
        count = len(self.rows)
        if colors is not None and len(colors) < count:
            raise ValueError(f"PieChart has {len(colors)} colours for {count} slices — give one per slice, or colors=None for the palette")

        self.radius = radius
        self.donut = donut
        turn = -1 if clockwise else 1

        # From the running total, not slice by slice: each edge is the same
        # number for the slice that ends there and the one that starts there,
        # so the circle closes with no gap and no overlap.
        edges = [0.0]
        running = 0.0
        for _, value in self.rows:
            running += value
            edges.append(360 * running / total)
        self.angles: list[float] = [b - a for a, b in zip(edges, edges[1:])]
        self.starts: list[float] = [startAngle + turn * edge for edge in edges[:-1]]
        self.percents = _percents([value for _, value in self.rows])

        self.slices: list[_Slice] = []
        self.labels: list[Text] = []
        pad = fontSize * 0.6
        for i, (name, _) in enumerate(self.rows):
            color = colors[i] if colors is not None else PALETTE[i % len(PALETTE)]
            slice_ = _Slice(self.starts[i], turn * self.angles[i], radius, radius * donut, color)
            self.slices.append(slice_.position(*_centre(slice_.vertices)))

            words = ([str(name)] if showLabels else []) + ([f"{self.percents[i]}%"] if showPercent else [])
            if not words:
                continue
            label = Text(text=" ".join(words), fontSize=fontSize)
            # Out along the slice's middle angle, far enough that the side of
            # the label nearest the pie stands `pad` off the rim.
            middle = math.radians(self.starts[i] + turn * self.angles[i] / 2)
            ux, uy = math.cos(middle), math.sin(middle)
            away = radius + pad + abs(ux) * _wide(label) / 2 + abs(uy) * label.height / 2
            self.labels.append(label.position(x=away * ux, y=away * uy))

        super().__init__(*self.slices, *self.labels)

    @classmethod
    def fromCSV(cls, path: str, *, label: str | int = 0, value: str | int = 1, **options) -> "PieChart":
        """
        The same chart, read from a file, with `BarChart.fromCSV`'s rules::

            PieChart.fromCSV("budget.csv", label="item", value="cost", donut=0.5)

        `label` and `value` are column names with a header row and column
        numbers without one, and a cell that is not a number is refused at its line.
        """
        return cls(_readCSV(path, label=label, value=value), **options)

    def grow(self, *, duration: sec = 0.8, every: sec = 0.1, easing: easing = Easing.InOut) -> "PieChart":
        """
        Each slice sweeps open from its own start angle, `every` seconds after the one before.

        A slice is hidden until it starts to open, and its label until it has
        finished: a percentage beside a slice that is still opening reads as
        the share of the part already drawn.
        """
        for i, slice_ in enumerate(self.slices):
            begins = i * every
            label = self.labels[i] if i < len(self.labels) else None
            slice_.hide()
            if label is not None:
                label.hide()

            # The renderer puts the middle of a closed shape's box at its
            # position, and an opening slice's box moves. So the pie's centre is
            # worked out once, where the slice stands now — after any move,
            # turn or scale of the chart — and every frame puts the box's
            # middle where it is from that centre.
            turn = math.radians(-slice_.meta.rotation)
            sx, sy = slice_.meta.scale.x, slice_.meta.scale.y

            def placed(local: point, turn: float = turn, sx: float = sx, sy: float = sy) -> point:
                x, y = local[0] * sx, local[1] * sy
                return (x * math.cos(turn) - y * math.sin(turn), y * math.cos(turn) + x * math.sin(turn))

            full = placed(_centre(slice_.vertices))
            hub = (slice_.meta.position.x - full[0], slice_.meta.position.y - full[1])
            shown = [False]

            def _apply(m: number, k: int, slice_: _Slice = slice_, begins: sec = begins, label: maybe[Text] = label,
                       placed=placed, hub: point = hub, shown: list[bool] = shown) -> None:
                # An easing that overshoots would push into the next slice.
                sweep = slice_.sweep * min(max(m, 0.0), 1.0)
                at = begins + k * SF
                if sweep != 0:
                    if not shown[0]:
                        shown[0] = True
                        slice_.show(start=at)
                    slice_.vertices = _ring(slice_.start, sweep, slice_.outer, slice_.inner)
                    slice_.points = At(start=at, duration=SINGLE_FRAME) | slice_.buildPoints()
                    offset = placed(_centre(slice_.vertices))
                    slice_.apply(position(hub[0] + offset[0], hub[1] + offset[1]).at(start=at))
                if label is not None and k == max(1, int(duration * FRAMERATE)) - 1:
                    label.show(start=at)

            animate(duration, easing, _apply)
        return self
