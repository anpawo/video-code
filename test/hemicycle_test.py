#!/usr/bin/env python3

"""
`Hemicycle` — every deputy has a seat, and a vote comes on from its own side.

A seat chart is believed at a glance, so the first thing to hold is the count:
577 deputies are 577 seats, whatever the rounding did to each row, and a group
of 71 is 71 of them, sitting together. The second is the vote. It is read as a
wave, and a wave that starts in the middle of a group, or on the wrong side of
the chamber, says something else than the vote did; so the order the seats come
on in is checked seat by seat, and so is the frame the first one comes on at.

Run directly: `python3 test/hemicycle_test.py`
"""

import math
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "test")
from helpers import check, section, summary

from videocode.color import rgba
from videocode.constants import FRAMERATE
from videocode.context import Context, wait
from videocode.serialize import _resetContext, templateCatalogue
from videocode.template.input.Hemicycle import SEAT, Hemicycle

# left of the picture to right; 577 in all
ASSEMBLEE = {
    "GDR": 17, "LFI": 71, "ECO": 38, "SOC": 66, "LIOT": 23, "DEM": 36,
    "EPR": 91, "HOR": 34, "DR": 49, "UDR": 16, "RN": 123, "NI": 13,
}  # fmt: skip
GREEN = rgba(78, 203, 113)
RED = rgba(229, 72, 77)
WIDTH = 7


def everySeat(chamber: Hemicycle) -> list:
    return [seat for seats in chamber.seatsOf.values() for seat in seats]


def place(seat) -> tuple[float, float]:
    return seat.meta.position.x, seat.meta.position.y


def angle(seat) -> float:
    """From the right-hand end of the baseline, in radians: 0 on the right, pi on the left."""
    x, y = place(seat)
    return math.atan2(y + WIDTH / 4, x)


def colours(seat) -> dict[int, rgba]:
    """The fill this seat is given, frame by frame."""
    entry = Context.stack[seat.meta.index]
    return {
        frame: keys["Args:fillColor"]["args"]["value"]
        for frame, keys in entry.items()
        if frame != -1 and "Args:fillColor" in keys
    }


def light(colour) -> int:
    r, g, b, _ = colour.jsonSerialization() if isinstance(colour, rgba) else colour
    return r + g + b


def same(colour, wanted: rgba) -> bool:
    return tuple(colour.jsonSerialization() if isinstance(colour, rgba) else colour) == tuple(wanted.jsonSerialization())


# ── The count ──────────────────────────────────────────────────────────────
section("every deputy has a seat, whatever the rounding did to a row")
sizes = (1, 2, 7, 20, 100, 348, 577, 925)
seated = []
for size in sizes:
    _resetContext()
    seated.append(len(Hemicycle({"all": size}).seatsOf["all"]))
check(f"a chamber of n has n seats, for n in {sizes}", seated == list(sizes))

_resetContext()
chamber = Hemicycle(ASSEMBLEE, width=WIDTH)
check("each group has the seats it was given", {name: len(seats) for name, seats in chamber.seatsOf.items()} == ASSEMBLEE)
check("and no seat is counted twice", len({id(seat) for seat in everySeat(chamber)}) == 577)

_resetContext()
again = Hemicycle(ASSEMBLEE, width=WIDTH)
check("the same counts draw the same chamber, seat for seat",
      [place(seat) for seat in everySeat(again)] == [place(seat) for seat in everySeat(chamber)])

# ── The picture ────────────────────────────────────────────────────────────
section("the seats sit on a half-ring, mirrored, and never on each other")
radius = WIDTH / 2
reach = [math.hypot(x, y + radius / 2) for x, y in map(place, everySeat(chamber))]
check("every seat is between the well and the outer wall", all(0.3 * radius < r < radius for r in reach))
check("and above the baseline", all(y > -radius / 2 for _, y in map(place, everySeat(chamber))))

spots = {(round(x, 6), round(y, 6)) for x, y in map(place, everySeat(chamber))}
check("the left half is the right half, mirrored", all((-x, y) in spots for x, y in spots))

ordered = sorted(everySeat(chamber), key=place)
spare = min(
    math.hypot(b.meta.position.x - a.meta.position.x, b.meta.position.y - a.meta.position.y) - max(a.width, b.width)
    for i, a in enumerate(ordered)
    for b in ordered[i + 1 :]
)
check(f"two seats are always further apart than either is wide (by {spare:.3f} at the closest)", spare > 0)

section("the groups sit left to right, each a slice of the half-ring")
names = list(ASSEMBLEE)
check("a group ends where the next one starts, going round from the left",
      all(min(map(angle, chamber.seatsOf[a])) >= max(map(angle, chamber.seatsOf[b])) - 1e-9 for a, b in zip(names, names[1:])))

# ── The vote ───────────────────────────────────────────────────────────────
section("a vote comes on from the group's own side of the chamber")
chamber.light("RN", RED, start=1, duration=0.6)
chamber.light("LFI", GREEN, count=27, start=1, duration=0.6)

rn = chamber.seatsOf["RN"]
began = [min(colours(seat)) for seat in rn]
check("the first seat comes on at the second asked for", began[0] == round(1 * FRAMERATE))
check("the last one as the wave ends", began[-1] == round(1.6 * FRAMERATE))
check("and none before the one ahead of it in the wave", began == sorted(began))
check("on the right, the wave starts at the right-hand end of the baseline and climbs",
      sum(map(angle, rn[:10])) < sum(map(angle, rn[-10:])) and angle(rn[0]) - min(map(angle, rn)) < 0.1)

lfi = chamber.seatsOf["LFI"]
check("on the left, at the left-hand end",
      sum(map(angle, lfi[:10])) > sum(map(angle, lfi[-10:])) and max(map(angle, lfi)) - angle(lfi[0]) < 0.1)
check("`count` lights that many seats, the first the wave reaches",
      [bool(colours(seat)) for seat in lfi] == [True] * 27 + [False] * 44)
check("a group nobody lit is not written at all", not any(colours(seat) for seat in chamber.seatsOf["SOC"]))

shades = colours(rn[0])
check("a seat comes on brighter than it stays", light(shades[min(shades)]) > light(shades[max(shades)]))
check("and stays the colour asked for, exactly", same(shades[max(shades)], RED))
check("settling takes a fifth of a second", max(shades) - min(shades) == round(0.2 * FRAMERATE) - 1)

section("clear() puts the lights back down, and only those that were on")
chamber.clear(start=3, duration=0.3)
check("a lit seat ends on the chamber's own colour", all(same(colours(seat)[max(colours(seat))], SEAT) for seat in rn + lfi[:27]))
check("a seat that was never lit is still not written", not any(colours(seat) for seat in lfi[27:] + chamber.seatsOf["SOC"]))

# ── The clock ──────────────────────────────────────────────────────────────
section("a vote after a wait() starts at the wait, not at the film's first frame")
_resetContext()
late = Hemicycle({"left": 30, "right": 30})
late.light("left", GREEN, duration=0.2)
wait(2)
late.light("right", RED, duration=0.2)
check(f"the second vote's first seat comes on at the frame the wait ends ({Context.waitOffset})",
      Context.waitOffset > 2 * FRAMERATE and min(colours(late.seatsOf["right"][0])) == Context.waitOffset)

# ── The Library ────────────────────────────────────────────────────────────
section("the Library lists it, and the word a person would type finds it")
listed = {one["name"]: one for one in templateCatalogue()}.get("Hemicycle")
check("Hemicycle is listed as a template", bool(listed) and listed["group"] == "template" and listed["required"] == ["groups"])
# LibraryPanel.matching()
check('"parliament" and "seat" find it', bool(listed) and all(word in listed["says"].lower() for word in ("parliament", "seat")))

# ── What is refused ────────────────────────────────────────────────────────
section("what cannot be drawn is refused, with the reason")
for wrong, why in (
    ({}, "no group at all"),
    ({"a": 3, "b": 0}, "a group with no seat"),
    ([("a", 3), ("a", 4)], "the same group twice"),
):
    _resetContext()
    try:
        Hemicycle(wrong)
        check(f"{why} is refused", False)
    except ValueError as error:
        check(f"{why} is refused ({error})", True)

_resetContext()
small = Hemicycle({"left": 4, "right": 6})
try:
    small.light("centre", GREEN)
    check("a group that is not seated is refused", False)
except ValueError as error:
    check(f"a group that is not seated is refused, naming the ones that are ({error})", "left" in str(error) and "right" in str(error))

for count in (0, 5):
    try:
        small.light("left", GREEN, count=count)
        check(f"{count} seats of a group of 4 is refused", False)
    except ValueError as error:
        check(f"{count} seats of a group of 4 is refused ({error})", True)

summary()
