#!/usr/bin/env python3

"""
The rune page — seventeen parts, each one findable, and the page they make.

A part nobody can find is a part nobody uses: the Library's search matches a
word against a part's name and the first line of its docstring, so every part
has to say what it is in words a person would type. The page itself is held to
the two things that broke while it was written: it lasts the seconds it was
given, to the frame, and no two of its lines write the same channel over the
same frames.

Two things the page needed from the library ride along: `Text(letterSpacing=…)`
and a `Group` that lands on `at=` like a plain shape does.

Run directly: `python3 test/rune_page_test.py`
"""

import os
import sys
import tempfile

sys.path.insert(0, ".")
sys.path.insert(0, "test")
from helpers import check, section, summary

from PIL import Image as Picture

from videocode import *
from videocode.serialize import _resetContext, lintSource, templateCatalogue
import videocode.input.shape.text._TextHelper as _helper
from videocode.template.input import RunePage
from videocode.template.input.RunePage import (
    ChampionName, ChampionTitle, LaneTag, PatchLine, PickRing, Rail, RailNode, RuneLabel, RuneOption,
    Shade, ShardLabel, ShardOption, Splash, Tint, TreeBadge, TreeKicker, TreeName,
)  # fmt: skip

# a word a person would type for each part, never its class name
WORDS = {
    "Splash": "art", "Shade": "scrim", "Tint": "pool of colour",
    "LaneTag": "rule", "ChampionName": "serif", "ChampionTitle": "epithet", "PatchLine": "context",
    "TreeKicker": "heading", "TreeBadge": "emblem", "TreeName": "sliding in",
    "Rail": "grows", "RailNode": "dot",
    "RuneOption": "choices", "ShardOption": "stat", "PickRing": "ring",
    "RuneLabel": "keystone", "ShardLabel": "capitals",
}  # fmt: skip

# ── Seventeen parts, each one findable ─────────────────────────────────────
section("every part is in the Library, and a word finds it")
catalogue = {one["name"]: one for one in templateCatalogue()}


def found(word: str) -> set[str]:
    # LibraryPanel.matching()
    return {name for name, one in catalogue.items() if word in name.lower() or word in one["says"].lower()}


check("the module offers seventeen parts", len(RunePage.__all__) == 17 and set(RunePage.__all__) == set(WORDS))
for name, word in WORDS.items():
    one = catalogue.get(name)
    check(f"{name} is listed as a template, with a sentence", bool(one) and one["group"] == "template" and len(one["says"]) > 20)
    check(f'"{word}" finds {name}', name in found(word))

# ── The page ───────────────────────────────────────────────────────────────
section("the page lasts what it was given, and no two lines fight")
media = tempfile.mkdtemp()
icon = os.path.join(media, "icon.png")
art = os.path.join(media, "art.jpg")
Picture.new("RGBA", (64, 64), (200, 170, 110, 255)).save(icon)
Picture.new("RGB", (1215, 717), (20, 30, 60)).save(art)

SCENE = f"""
from videocode import *
from videos.lol.runes import Row, Tree, runePage

runePage(
    champion="LOCKE", title="THE ASHEN EXORCIST", lane="TOP LANE", patch="RUNE PAGE",
    splash={art!r},
    primary=Tree("DOMINATION", {icon!r}, rgba(212, 66, 66), [
        Row([{icon!r}] * 3, pick=0, name="ELECTROCUTE"),
        Row([{icon!r}] * 3, pick=2, name="SUDDEN IMPACT"),
        Row([{icon!r}] * 3, pick=1, name="GRISLY MEMENTOS"),
        Row([{icon!r}] * 3, pick=0, name="TREASURE HUNTER"),
    ]),
    secondary=Tree("PRECISION", {icon!r}, rgba(200, 170, 110), [
        Row([{icon!r}] * 3, pick=1, name="TRIUMPH"),
        Row([{icon!r}] * 3),
        Row([{icon!r}] * 3, pick=1, name="CUT DOWN"),
    ]),
    shards=[Row([{icon!r}] * 3, pick=k, name="SHARD") for k in (2, 0, 0)],
)
"""

_resetContext()
exec(compile(SCENE, "page.py", "exec"), {})
check("ten seconds, to the frame", Context.waitOffset == 10 * FRAMERATE)

said, failed = lintSource(SCENE, os.path.join(media, "page.py"))
check("the scene runs", not failed)
check("no two lines write the same channel over the same frames", "[contended-key]" not in said)

# ── Each part, by itself ───────────────────────────────────────────────────
section("a part is not on screen before its entrance")

ENTRANCES = {
    Splash: lambda: Splash(art), LaneTag: lambda: LaneTag("TOP LANE"), ChampionName: lambda: ChampionName("LOCKE"),
    ChampionTitle: lambda: ChampionTitle("THE ASHEN EXORCIST"), PatchLine: lambda: PatchLine("RUNE PAGE"),
    TreeKicker: lambda: TreeKicker("PRIMARY"), TreeBadge: lambda: TreeBadge(icon), TreeName: lambda: TreeName("DOMINATION"),
    RailNode: RailNode, RuneOption: lambda: RuneOption(icon), ShardOption: lambda: ShardOption(icon), PickRing: PickRing,
    RuneLabel: lambda: RuneLabel("ELECTROCUTE"), ShardLabel: lambda: ShardLabel("HEALTH"),
}  # fmt: skip


def hiddenUntilItsEntrance(make) -> bool:
    _resetContext()
    mark = len(Context.statements)
    make().wait(1).animateIn()
    spans = [span for st in Context.statements[mark:] for key, span in st["keys"].items() if key == "Opacity"]
    return bool(spans) and min(first for first, _ in spans) == 0 and max(last for _, last in spans) > FRAMERATE


for part, make in ENTRANCES.items():
    check(f"{part.__name__} is hidden from frame 0 and comes in after its wait", hiddenUntilItsEntrance(make))

section("and what it does once it is in")
_resetContext()
rail = Rail(2).growTo(0.5)
check("a rail's tip is brought to the length asked, from its top", abs(rail.height - 0.5) < 1e-9 and rail.meta.align.y == 1)
check("a picked option swells by a tenth", abs(RuneOption(icon).pick().meta.scale.x - 1.1) < 1e-9)
check("one passed over fades to 22 %", RuneOption(icon).drain()._opacityNow() == 56)
check("a shard does the same, disc and icon together", [member._opacityNow() for member in ShardOption(icon).drain().inputs] == [56, 56])
check("a ring's pulse leaves it at its size", PickRing().pulse().meta.scale.x == 1)
check("the shade covers the frame, twice over", [(member.width, member.height) for member in Shade().inputs] == [(W, H)] * 2)
check("a tint is an ellipse, wider than tall", Tint().width > Tint().height)

# ── What it needed from the library ────────────────────────────────────────
section("letterSpacing is added after every letter, in fontSizes")


def span(text: Text) -> float:
    data = _helper.buildLetterData(text.text, text.fontSize, text.fontFamily, text.bold, text.italic, letterSpacing=text.letterSpacing)
    return data[-1][1] - data[0][1]


_resetContext()
tight, wide = Text("TOP", fontSize=0.4), Text("TOP", fontSize=0.4, letterSpacing=0.5)
check("two gaps of half a fontSize over three letters", abs(span(wide) - span(tight) - 2 * 0.5 * 0.4) < 1e-9)
check("none by default", Text("TOP").letterSpacing == 0)
tight.letterSpacing = 0.5
check("and it can be set afterwards", abs(span(tight) - span(wide)) < 1e-9)

section("a group lands on at= like a plain shape")


def firstScaleFrame(make) -> int:
    _resetContext()
    mark = len(Context.statements)
    make().scaleTo(1.1, at=5, duration=0.4)
    return min(first for st in Context.statements[mark:] for key, (first, _) in st["keys"].items() if key.startswith("Scale"))


check("a circle scales at second 5", firstScaleFrame(Circle) == 5 * FRAMERATE)
check("and so does a group of two", firstScaleFrame(lambda: Group(Circle(), Circle())) == 5 * FRAMERATE)

# ── summary ────────────────────────────────────────────────────────────────
summary()
