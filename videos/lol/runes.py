"""
A champion's rune page, as a template: the art on the left under a title block, then the two
trees and the shards filling in row by row — the options come in, the pick is ringed and named,
the rest fade back. A champion's page is only data:

    runePage(
        champion="LOCKE", title="THE ASHEN EXORCIST", lane="TOP LANE", patch="RUNE PAGE · PATCH 26.19",
        splash=f"{MEDIA}/splash.jpg",
        primary=Tree("DOMINATION", f"{MEDIA}/runes/tree-8100.png", rgba(212, 66, 66), [
            Row([f"{MEDIA}/runes/8112.png", ...], pick=0, name="ELECTROCUTE"),
            ...
        ]),
        secondary=Tree(...),
        shards=[Row([...], pick=2, name="ABILITY HASTE"), ...],
    )

The first row of the primary tree is the keystone row, drawn larger. A row given no pick fades
back whole: the secondary tree shows three rows and takes from two.

Built from the parts in `videocode/template/input/RunePage.py`, on a 1920x1080 frame.
"""

from dataclasses import dataclass, field

from videocode import *
from videocode.template.input.RunePage import *
from videocode.template.input.RunePage import NIGHT, PALE_GOLD, PX


@dataclass
class Row:
    options: list[str]  # icon files, left to right
    pick: int | None = None
    name: str = ""


@dataclass
class Tree:
    name: str
    icon: str
    color: rgba
    rows: list[Row] = field(default_factory=list)


def at(x: float, y: float) -> tuple[float, float]:
    """A pixel of the 1080p frame, in world units."""
    return (x - 960) * PX, (540 - y) * PX


def _choose(row: Row, options: list, t: sec, lag: sec, seconds: sec) -> None:
    began = Context.waitOffset / FRAMERATE
    turn = began + t + lag
    # in whole frames: a grey counted in seconds outlasts the page by a frame or two
    grey = (round((began + seconds) * FRAMERATE) - round(turn * FRAMERATE)) / FRAMERATE
    for k, option in enumerate(options):
        option.wait(t + 0.06 * k).animateIn()
        if k == row.pick:
            option.pick(start=max(lag - 0.06 * k, 0.35))  # once it has landed
        else:
            option.drain(at=turn, hold=grey)


def _tree(tree: Tree, kicker: str, x: float, t: sec, beat: sec, keystone: bool, seconds: sec) -> list[PickRing]:
    TreeKicker(kicker).position(*at(x - 50, 158.5)).wait(t).animateIn()
    TreeBadge(tree.icon, tree.color).position(*at(x - 22, 209)).wait(t).animateIn()
    TreeName(tree.name, tree.color).position(*at(x + 24, 207)).wait(t + 0.1).animateIn()

    rail = Rail(4.8, tree.color).position(*at(x - 22, 241))
    rings: list[PickRing] = []
    top, t = 273, t + 0.4
    for n, row in enumerate(tree.rows):
        big = keystone and not n
        size, step = (124, 142) if big else (76, 106)
        cy = top + size / 2
        _choose(row, [RuneOption(icon, size * PX).position(*at(x + size / 2 + k * step, cy)) for k, icon in enumerate(row.options)], t, 0.45, seconds)
        if row.pick is not None:
            rail.growTo((cy - 241) * PX, start=t)
            RailNode(tree.color).position(*at(x - 22, cy)).wait(t + 0.45).animateIn()
            rings.append(PickRing((141 if big else 99) * PX, tree.color).position(*at(x + size / 2 + row.pick * step, cy)).wait(t + 0.45).animateIn())
            label = RuneLabel(row.name, tree.color, 0.175).position(*at(x, top + 162.5)) if big else RuneLabel(row.name).position(*at(x, top + 112))
            label.wait(t + 0.55).animateIn()
        top += 202 if big else 146
        t += beat + 0.3 if big else beat
    return rings


def runePage(
    champion: str,
    title: str,
    lane: str,
    patch: str,
    splash: str,
    primary: Tree,
    secondary: Tree,
    shards: list[Row],
    seconds: sec = 10,
) -> None:
    began = Context.waitOffset / FRAMERATE

    Rectangle(width=W, height=H, fillColor=NIGHT, strokeColor=TRANSPARENT)
    Splash(splash).position(*at(115, 540)).animateIn(seconds=seconds, about=v2(*at(335, 216)))
    Shade()
    Tint(primary.color, strength=0.13).position(*at(880, 430))
    Tint(secondary.color, strength=0.1).position(*at(1520, 430))

    LaneTag(lane).position(*at(96, 670)).wait(0.3).animateIn()
    ChampionName(champion).position(*at(96, 752)).wait(0.4).animateIn()
    ChampionTitle(title).position(*at(96, 843)).wait(0.9).animateIn()
    PatchLine(patch).position(*at(96, 896)).wait(1.1).animateIn()

    rings = _tree(primary, "PRIMARY", 650, 1.3, 0.8, True, seconds)
    rings += _tree(secondary, "SECONDARY", 1290, 5.3, 0.6, False, seconds)

    TreeKicker("SHARDS").position(*at(1290, 719.5)).wait(7.6).animateIn()
    for n, row in enumerate(shards):
        cy, t = 763 + 66 * n, 7.8 + 0.3 * n
        _choose(row, [ShardOption(icon).position(*at(1311 + 64 * k, cy)) for k, icon in enumerate(row.options)], t, 0.3, seconds)
        if row.pick is not None:
            rings.append(PickRing(55 * PX, PALE_GOLD, 2 * PX).position(*at(1311 + 64 * row.pick, cy)).wait(t + 0.3).animateIn())
            ShardLabel(row.name).position(*at(1484, cy)).wait(t + 0.4).animateIn()

    # the page closes on a wave through every pick, in the order they were made
    for k, ring in enumerate(rings):
        ring.pulse(at=began + 8.95 + 0.04 * k)

    wait()
