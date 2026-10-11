#!/usr/bin/env python3

"""
The parts of a League of Legends rune page, one class each: the art and what sits over it, the
title block, a tree's heading, the rail down a column, the options and the mark of a pick.

Each part is built at its resting look and brings its own entrance, `animateIn()`:

    LaneTag("TOP LANE").position(-7.2, -1.1).wait(0.3).animateIn()

A line of text is placed by its left edge, as in a column; every other part by its centre, a
`Rail` by its top. Sizes are world units, 120 px each at 1080p. `videos/lol/runes.py` lays a
whole page out of them.
"""

from __future__ import annotations

from videocode import *
from videocode.shader.vertexShader.opacity import opacity as _opacity
from videocode.template.effect.other.popIn import popIn
from videocode.template.effect.other.slide import slideIn
from videocode.template.effect.other.stagger import stagger

__all__ = [
    "Splash", "Shade", "Tint",
    "LaneTag", "ChampionName", "ChampionTitle", "PatchLine",
    "TreeKicker", "TreeBadge", "TreeName",
    "Rail", "RailNode",
    "RuneOption", "ShardOption", "PickRing",
    "RuneLabel", "ShardLabel",
]  # fmt: skip

# the game's own UI
GOLD = rgba(200, 170, 110)
PALE_GOLD = rgba(205, 190, 145)
INK = rgba(240, 230, 210)
DIM = rgba(160, 155, 140)
NIGHT = rgba(1, 10, 19)

PX = 1 / 120


def _hide(part: Input) -> None:
    # what fadeIn(hidden=True) does: nothing on screen before the entrance
    mark = len(Context.statements)
    part.apply(_opacity(0), offset=0)
    for statement in Context.statements[mark:]:
        statement["placement"] = True


def _glow(color: rgba, strength: float = 0.6) -> RadialGradient:
    return RadialGradient((color | strength, 0), (color | 0, 100))


class Splash(Image):
    """Full-frame art behind everything, pushing in slowly for as long as it is on screen."""

    def __init__(self, filepath: str, height: wnumber = H):
        super().__init__(filepath, height=height)

    def animateIn(self, seconds: sec = 10, zoom: float = 1.06, about: maybe[v2] = None) -> Self:
        """Fade in, then push in to `zoom` over `seconds`, around `about` or its own centre."""
        self.fadeIn(duration=0.8, easing=Easing.Out)
        return self.scaleTo(zoom, duration=seconds, easing=Easing.Linear, about=about)


class Shade(Group):
    """A dark scrim over the art, heavier at the foot and on the right, so text reads on it."""

    def __init__(self, color: rgba = NIGHT):
        foot = LinearGradient((color | 0.96, 0), (color | 0.55, 24), (color | 0, 48), (color | 0, 100), angle=90)
        side = LinearGradient((color | 0.2, 0), (color | 0.45, 20), (color | 0.94, 36), (color, 43), (color, 100), angle=0)
        super().__init__(*(Rectangle(width=W, height=H, fillColor=fill, strokeColor=TRANSPARENT) for fill in (foot, side)))


class Tint(Circle):
    """A soft pool of colour behind a column, fading to nothing before its edge."""

    def __init__(self, color: rgba = GOLD, width: wnumber = 728 * PX, height: wnumber = 588 * PX, strength: float = 0.12):
        super().__init__(radius=width / 2, fillColor=_glow(color, strength), strokeColor=TRANSPARENT)
        self.scale(x=1, y=height / width)


class LaneTag(Group):
    """A short rule then a wide-tracked gold label: the tag over a title, sliding in from the left."""

    def __init__(self, text: str, color: rgba = GOLD, fontSize: wnumber = 0.12):
        rule = Rectangle(width=48 * PX, height=2 * PX, fillColor=color, strokeColor=TRANSPARENT).position(24 * PX, 0)
        label = Text(text, fontSize, fillColor=color, bold=True, letterSpacing=0.55).align(x=0).position(64 * PX, 0)
        super().__init__(rule, label)

    def animateIn(self) -> Self:
        """Slide in from the left, fading in."""
        _hide(self)
        return self.apply(slideIn(direction=Direction.LEFT, distance=24 * PX, duration=0.5))


class ChampionName(Text):
    """A big serif title whose letters rise into place one after the other."""

    def __init__(self, text: str, fontSize: wnumber = 0.72, fillColor: rgba = INK):
        super().__init__(text, fontSize, "Cinzel", fillColor, bold=True)
        self.align(x=0)

    def animateIn(self) -> Self:
        """Each letter rises into place, 0.06 s after the one before."""
        _hide(self)
        return self.apply(stagger(slideIn(direction=Direction.BOTTOM, distance=0.5, duration=0.6), every=0.06))


class ChampionTitle(Text):
    """The champion's epithet under the name: gold, wide-tracked capitals that fade in."""

    def __init__(self, text: str, fontSize: wnumber = 0.133, fillColor: rgba = GOLD):
        super().__init__(text, fontSize, fillColor=fillColor, letterSpacing=0.44)
        self.align(x=0)

    def animateIn(self) -> Self:
        """Fade in."""
        return self.fadeIn(duration=0.6, easing=Easing.Out)


class PatchLine(Text):
    """A small grey line of context under a title: what this is, and for which patch."""

    def __init__(self, text: str, fontSize: wnumber = 0.097, fillColor: rgba = DIM):
        super().__init__(text, fontSize, fillColor=fillColor, letterSpacing=0.385)
        self.align(x=0)

    def animateIn(self) -> Self:
        """Fade in."""
        return self.fadeIn(duration=0.6, easing=Easing.Out)


class TreeKicker(Text):
    """A tiny grey heading over a column: PRIMARY, SECONDARY, SHARDS."""

    def __init__(self, text: str, fontSize: wnumber = 0.085, fillColor: rgba = DIM):
        super().__init__(text, fontSize, fillColor=fillColor, bold=True, letterSpacing=0.58)
        self.align(x=0)

    def animateIn(self) -> Self:
        """Fade in."""
        return self.fadeIn(duration=0.4, easing=Easing.Out)


class TreeBadge(Group):
    """A rune tree's emblem in a dark disc ringed in the tree's colour, popping in."""

    def __init__(self, filepath: str, color: rgba = GOLD, size: wnumber = 56 * PX):
        disc = Circle(radius=size / 2, fillColor=NIGHT | 0.7, strokeColor=color, strokeWidth=2 * PX)
        super().__init__(disc, Image(filepath, width=size * 0.6, height=size * 0.6))

    def animateIn(self) -> Self:
        """Pop in from a third of its size."""
        _hide(self)
        return self.apply(popIn(scale=0.3, duration=0.5))


class TreeName(Text):
    """A rune tree's name in the tree's colour, sliding in from the left."""

    def __init__(self, text: str, fillColor: rgba = GOLD, fontSize: wnumber = 0.233):
        super().__init__(text, fontSize, "Cinzel", fillColor, bold=True, letterSpacing=0.086)
        self.align(x=0)

    def animateIn(self) -> Self:
        """Slide in from the left, fading in."""
        _hide(self)
        return self.apply(slideIn(direction=Direction.LEFT, distance=20 * PX, duration=0.5))


class Rail(Rectangle):
    """A thin line that grows down a column, stop by stop, tying its rows together."""

    def __init__(self, length: wnumber, color: rgba = GOLD, width: wnumber = 2 * PX):
        super().__init__(width=width, height=length, fillColor=color | 0.55, strokeColor=TRANSPARENT)
        self.align(0.5, 1)
        self.scale(x=1, y=0.0001)

    def growTo(self, length: wnumber, start: sec = 0, duration: sec = 0.45) -> Self:
        """Bring the tip `length` below the top."""
        full = self.height / self.meta.scale.y  # height reads scaled
        return self.scaleTo(x=1, y=length / full, start=start, duration=duration, about=v2(*self.meta.position))


class RailNode(Group):
    """A glowing dot on the rail, marking a row that has been decided."""

    def __init__(self, color: rgba = GOLD, size: wnumber = 14 * PX):
        halo = Circle(radius=size * 1.5, fillColor=_glow(color), strokeColor=TRANSPARENT)
        super().__init__(halo, Circle(radius=size / 2, fillColor=color, strokeColor=TRANSPARENT))

    def animateIn(self) -> Self:
        """Pop in from nothing."""
        _hide(self)
        return self.apply(popIn(scale=0.01, duration=0.3))


class _Option(Input):
    def animateIn(self) -> Self:
        """Pop in from a little smaller."""
        _hide(self)
        return self.apply(popIn(scale=0.6, duration=0.35))

    def pick(self, start: sec = 0) -> Self:
        """The chosen one swells."""
        return self.scaleTo(1.1, start=start, duration=0.4, easing=Easing.Back)

    def drain(self, start: sec = 0, at: maybe[sec] = None, hold: sec = 0) -> Self:
        """One that was passed over fades back, and stays grey for `hold` seconds."""
        if hold:
            self.apply(grayscale(), start=start, at=at, duration=hold)
        # under a fragment shader the opacity lands twice: 120 then reads as 56 does without one
        return self.fadeTo(120 if hold else 56, start=start, at=at, duration=0.35, easing=Easing.Out)


class RuneOption(_Option, Image):
    """A rune among its row's choices: it swells when it is the pick, and fades back when it is not."""

    def __init__(self, filepath: str, size: wnumber = 76 * PX):
        super().__init__(filepath, width=size, height=size)


class ShardOption(_Option, Group):
    """A stat shard in a small ringed disc, picked or passed over like a rune."""

    def __init__(self, filepath: str, size: wnumber = 42 * PX):
        disc = Circle(radius=size / 2, fillColor=rgba(10, 20, 32), strokeColor=GOLD | 0.35, strokeWidth=PX)
        super().__init__(disc, Image(filepath, width=size * 0.71, height=size * 0.71))


class PickRing(Group):
    """A glowing ring that closes in around the chosen option."""

    def __init__(self, size: wnumber = 99 * PX, color: rgba = GOLD, strokeWidth: wnumber = 3 * PX):
        halo = RadialGradient((color | 0, 0), (color | 0, 50), (color | 0.3, 73), (color | 0, 100))
        glow = Circle(radius=size / 2 * 1.35, fillColor=halo, strokeColor=TRANSPARENT)
        super().__init__(glow, Circle(radius=size / 2, fillColor=TRANSPARENT, strokeColor=color, strokeWidth=strokeWidth))

    def animateIn(self) -> Self:
        """Close in from a wider ring, fading in."""
        _hide(self)
        return self.apply(popIn(scale=1.4, duration=0.4, easing=Easing.Out))

    def pulse(self, start: sec = 0, at: maybe[sec] = None) -> Self:
        """Swell and settle, once."""
        return self.scaleTo(1.08, start=start, at=at, duration=0.44, easing=Easing.ThereAndBack)


class RuneLabel(Text):
    """The name of a picked rune, rising a little as it appears; a keystone's is larger."""

    def __init__(self, text: str, fillColor: rgba = INK, fontSize: wnumber = 0.1225):
        super().__init__(text, fontSize, "Cinzel", fillColor, bold=True, letterSpacing=0.17)
        self.align(x=0)

    def animateIn(self) -> Self:
        """Rise a few pixels, fading in."""
        _hide(self)
        return self.apply(slideIn(direction=Direction.BOTTOM, distance=8 * PX, duration=0.35))


class ShardLabel(Text):
    """The name of a picked shard: small gold capitals beside its row."""

    def __init__(self, text: str, fillColor: rgba = PALE_GOLD, fontSize: wnumber = 0.091):
        super().__init__(text, fontSize, fillColor=fillColor, bold=True, letterSpacing=0.41)
        self.align(x=0)

    def animateIn(self) -> Self:
        """Rise a few pixels, fading in."""
        _hide(self)
        return self.apply(slideIn(direction=Direction.BOTTOM, distance=8 * PX, duration=0.35))
