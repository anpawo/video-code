#!/usr/bin/env python3

"""
The rune page's parts, one of each, with the repository's logo standing in for the art and the
icons.

    ./video-code --file docs/by-example/features/rune_page.py --generate rune_page.mp4

Every part is built at its resting look and brings its own entrance, `animateIn()`; a `wait(t)`
on the part says when. An option then takes `pick()` or `drain()`, a rail `growTo()`, a ring
`pulse()`. `videos/lol/runes.py` lays a whole page out of them, from data.
"""


from videocode import *
from card import card
from videocode.template.input.RunePage import (
    ChampionName, ChampionTitle, LaneTag, PatchLine, PickRing, Rail, RailNode, RuneLabel, RuneOption,
    Shade, ShardLabel, ShardOption, Splash, Tint, TreeBadge, TreeKicker, TreeName,
)  # fmt: skip

ART = "logo.png"
RED = rgba(212, 66, 66)

intro = card(
    "Rune page · its seventeen parts",
    "each part brings its own entrance: animateIn()",
    "an option is picked or drained, a rail grows, a ring pulses",
    code=['LaneTag("TOP LANE").position(-7.2, -1.1).wait(0.3).animateIn()'],
)

with shot() as demo:
    Rectangle(width=W, height=H, fillColor=rgba(1, 10, 19), strokeColor=TRANSPARENT)
    Splash(ART, height=5).position(-5, 1.5).animateIn(seconds=4)
    Shade()
    Tint(RED).position(-0.7, 0.9)

    LaneTag("TOP LANE").position(-7.2, -1.1).wait(0.3).animateIn()
    ChampionName("LOCKE").position(-7.2, -1.8).wait(0.4).animateIn()
    ChampionTitle("THE ASHEN EXORCIST").position(-7.2, -2.5).wait(0.9).animateIn()
    PatchLine("RUNE PAGE · PATCH 26.19").position(-7.2, -2.95).wait(1.1).animateIn()

    TreeKicker("PRIMARY").position(-3, 3.2).wait(1.3).animateIn()
    TreeBadge(ART, RED).position(-2.77, 2.76).wait(1.3).animateIn()
    TreeName("DOMINATION", RED).position(-2.38, 2.78).wait(1.4).animateIn()

    # the rail's tip reaches the row as the row comes in; the node marks it once the pick is made
    Rail(1.5, RED).position(-2.77, 2.49).growTo(0.78, start=1.7)
    RailNode(RED).position(-2.77, 1.71).wait(2.15).animateIn()

    picked = RuneOption(ART, 1).position(-2, 1.71).wait(1.7).animateIn()
    passed = RuneOption(ART, 1).position(-0.8, 1.71).wait(1.76).animateIn()
    picked.pick(start=0.45)
    passed.drain(start=0.39, hold=2)
    PickRing(1.18, RED).position(-2, 1.71).wait(2.15).animateIn().pulse(start=1.2)
    RuneLabel("ELECTROCUTE", RED, 0.175).position(-2.5, 0.85).wait(2.25).animateIn()

    shard = ShardOption(ART).position(-2.3, -0.4).wait(2.6).animateIn()
    shard.pick(start=0.35)
    ShardLabel("ADAPTIVE FORCE").position(-1.9, -0.4).wait(3).animateIn()
    wait(1.5)

cut(intro, demo)
