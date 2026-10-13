#!/usr/bin/env python3

"""
A parliament's chamber as a seat chart, and a vote lit seat by seat.

The picture every vote explainer draws: the half-ring of seats, the groups
seated left to right, and one group's seats coming on in green or red as its
vote is read out. Drawn by hand it is five hundred rectangles and a page of
trigonometry per scene; here it is the seat counts and one line per vote.
"""

from __future__ import annotations

import math
from typing import Self

from videocode.color import rgba
from videocode.constants import *
from videocode.input.interface.Group import Group
from videocode.input.shape.Rectangle import Rectangle
from videocode.ty import *
from videocode.utils.bezier import Easing, animate
from videocode.utils.classutils import At

__all__ = ["Hemicycle"]

# a chamber with the lights down: seats a shade above the card they sit on
CARD = rgba(27, 32, 40)
SEAT = rgba(56, 64, 78)


def _layout(total: int, rows: int, wedges: int, hole: float, aisle: float) -> list[tuple[float, float, float]]:
    """
    Where every seat goes on a half-ring of outer radius 1: `(angle, radius, room)`,
    the angle in radians from the right-hand end of the baseline, and `room` the
    angle the seat has to itself on its row.

    A row holds seats in proportion to its radius, so the seats are the same
    distance apart on every row; the shares are rounded by largest remainder,
    so the rows add up to `total` exactly. The half-ring is cut into `wedges`
    blocks by radial aisles, as chambers are.
    """
    radii = [hole + (1 - hole) * (i + 0.5) / rows for i in range(rows)]
    shares = [total * r / sum(radii) for r in radii]
    counts = [int(s) for s in shares]
    for i in sorted(range(rows), key=lambda i: shares[i] - counts[i], reverse=True)[: total - sum(counts)]:
        counts[i] += 1

    # A row's seats are dealt to the wedges in whole numbers, the odd ones to the
    # middle first and then in pairs either side of it, so the picture stays
    # symmetric and every wedge is filled from aisle to aisle.
    middle = [wedges // 2] if wedges % 2 else []
    pairs = [w for d in range(1, wedges // 2 + 1) for w in (wedges // 2 - d, (wedges - 1) // 2 + d)]

    seats: list[tuple[float, float, float]] = []
    for radius, count in zip(radii, counts):
        each, spare = divmod(count, wedges)
        extra = (middle + pairs)[:spare] if spare % 2 else (pairs + middle)[:spare]
        for wedge in range(wedges):
            inWedge = each + (wedge in extra)
            for j in range(inWedge):
                along = aisle / 2 + (j + 0.5) / inWedge * (1 - aisle)
                seats.append((math.pi * (1 - (wedge + along) / wedges), radius, math.pi / wedges * (1 - aisle) / inWedge))
    return seats


class Hemicycle(Group):
    """
    A parliament's seat chart: every seat on a half-ring, the groups seated left to right::

        chamber = Hemicycle({"LFI": 71, "SOC": 66, "EPR": 91, "RN": 123})
        chamber.light("LFI", GREEN_A)
        chamber.light("RN", RED_A, count=27, start=1.2)

    `groups` is each group's name and its number of seats, in the order they
    sit from the left of the picture to the right; the chamber has as many
    seats as they add up to. A group takes a slice of the half-ring, cut along
    its radius, the way a seating plan is drawn.

    `light()` turns a group's seats to a colour in a wave that starts at the
    end of the baseline on the group's side — `count` of them when only part of
    the group voted. `clear()` puts the lights back down.

    `width` is the outer diameter in world units; the chart is centred on the
    group's position, so `position`, `scaleTo`, `fadeIn` and the rest work on
    the whole of it. `card=None` leaves the dark card out, for a chamber drawn
    on a scene's own background.
    """

    def __init__(
        self,
        groups: dict[str, int] | list[tuple[str, int]],
        *,
        width: wunumber = 7,
        rows: maybe[int] = None,
        wedges: int = 9,
        hole: float = 0.32,
        seatColor: rgba = SEAT,
        card: maybe[paint] = CARD,
    ) -> None:
        named = list(groups.items()) if isinstance(groups, dict) else list(groups)
        if not named:
            raise ValueError("Hemicycle needs at least one group")
        for name, count in named:
            if count <= 0:
                raise ValueError(f"Hemicycle cannot seat {count} deputies for {name!r} — a group has at least one seat")
        total = sum(count for _, count in named)
        if rows is None:
            # about as many rows as a chamber of this size has: 15 for the 577 of the Assemblée
            rows = max(1, round(math.sqrt(total) / 1.6))
        if rows < 1 or wedges < 1:
            raise ValueError(f"Hemicycle needs at least one row and one wedge, not rows={rows}, wedges={wedges}")
        radius = width / 2
        aisle = 0.2 if wedges > 1 else 0.0
        plan = _layout(total, rows, wedges, hole, aisle)

        # One size for every seat, rows holding seats in proportion to their radius;
        # narrower only where a row's rounding leaves a seat less room than that.
        rowPitch = radius * (1 - hole) / rows
        seatPitch = math.pi * radius * (1 - aisle) * sum({r for _, r, _ in plan}) / total
        self.seatColor = seatColor

        backing: list[Rectangle] = []
        if card is not None:
            pad = width * 0.036
            backing.append(
                Rectangle(width=width + 2 * pad, height=radius + 2 * pad, fillColor=card, strokeColor=TRANSPARENT, cornerRadius=9)
            )

        # Left to right, and from the well outwards inside one angle: a group is
        # then a slice of the half-ring, not a patch of it.
        order = sorted(range(total), key=lambda i: (-plan[i][0], plan[i][1]))
        seats: dict[int, Rectangle] = {}
        for i in order:
            angle, r, room = plan[i]
            seats[i] = (
                Rectangle(
                    width=0.74 * min(seatPitch, radius * r * room),
                    height=rowPitch * 0.42,
                    fillColor=seatColor,
                    strokeColor=TRANSPARENT,
                    cornerRadius=40,
                )
                .position(x=radius * r * math.cos(angle), y=radius * r * math.sin(angle) - radius / 2)
                # long side along the row: `rotation` turns clockwise
                .rotation(90 - math.degrees(angle))
            )

        self.seatsOf: dict[str, list[Rectangle]] = {}
        taken = 0
        for name, count in named:
            if name in self.seatsOf:
                raise ValueError(f"Hemicycle was given the group {name!r} twice")
            mine = order[taken : taken + count]
            taken += count
            # The wave a vote comes on in: from the end of the baseline on this
            # group's side, up the half-ring, the outer rows a step ahead.
            onTheRight = sum(plan[i][0] for i in mine) / count < math.pi / 2
            mine.sort(key=lambda i: ((plan[i][0] if onTheRight else math.pi - plan[i][0]) - 0.12 * plan[i][1]))
            self.seatsOf[name] = [seats[i] for i in mine]

        super().__init__(*backing, *(seats[i] for i in order))

    def light(
        self,
        group: str,
        color: rgba,
        *,
        count: maybe[int] = None,
        start: sec = 0,
        duration: sec = 0.6,
        settle: sec = 0.2,
    ) -> Self:
        """
        A group's seats to `color`, one after the other over `duration`.

        Each seat comes on brighter than it stays and settles over `settle`:
        the bright edge is what the eye follows up the half-ring. `count`
        lights that many seats, the first the wave reaches — the ones who
        voted, when a group did not turn out whole.
        """
        if group not in self.seatsOf:
            raise ValueError(f"Hemicycle has no group called {group!r} — it seats {', '.join(self.seatsOf)}")
        seats = self.seatsOf[group]
        if count is None:
            count = len(seats)
        if not 0 < count <= len(seats):
            raise ValueError(f"{group!r} has {len(seats)} seats — {count} of them cannot be lit")

        bright = color + (WHITE - color) * 0.5
        for k, seat in enumerate(seats[:count]):
            began = start + duration * k / max(1, count - 1)

            def _apply(m: number, i: int, seat: Rectangle = seat, began: sec = began):
                seat.fillColor = At(start=began + i * SF, duration=SINGLE_FRAME) | (bright + (color - bright) * m)

            animate(settle, Easing.InOut, _apply)
        return self

    def clear(self, *, start: sec = 0, duration: sec = 0.3) -> Self:
        """Every lit seat back to the chamber's own colour, together."""
        for seats in self.seatsOf.values():
            for seat in seats:
                if seat.fillColor != self.seatColor:
                    seat.over(start=start, duration=duration).fillColor = self.seatColor
        return self
