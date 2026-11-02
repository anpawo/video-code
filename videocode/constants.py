#!/usr/bin/env python3

from __future__ import annotations

#
# Constant
#

import os
from enum import Enum, StrEnum
from sys import stderr
from videocode.ty import *
import videocode.utils.logger as logger

# screen dimension — READ-ONLY here. The resolution is decided by
# --width/--height on the command line (1920x1080 by default) and handed down
# by C++ through VC_SCREEN, before this module is imported. Assigning to these
# in a scene changes nothing: the renderer has already sized its surface, and
# the world box below was built from the real numbers.
DEFAULT_SCREEN = (1920, 1080)


def _screenFromEnv() -> tuple[int, int]:
    raw = os.environ.get("VC_SCREEN", "")
    try:
        width, height = raw.lower().split("x")
        return (int(width), int(height))
    except (ValueError, AttributeError):
        # Plain `import videocode` outside the renderer (tests, tooling).
        return DEFAULT_SCREEN


SCREEN_WIDTH, SCREEN_HEIGHT = _screenFromEnv()
SW, SH = SCREEN_WIDTH, SCREEN_HEIGHT

# world dimension
#
# The world unit is a fixed number of pixels, so a shape keeps its physical
# size across aspect ratios — a portrait render doesn't shrink your content,
# it just gives you a 9x16 world instead of a 16x9 one.
WORLD_TO_SCREEN_RATIO = 120

WORLD_WIDTH = W = SCREEN_WIDTH / WORLD_TO_SCREEN_RATIO
WORLD_HEIGHT = H = SCREEN_HEIGHT / WORLD_TO_SCREEN_RATIO

WORLD_OFFSET_X = WORLD_WIDTH / 2
WORLD_OFFSET_Y = WORLD_HEIGHT / 2

# framerate
FRAMERATE = 30
SINGLE_FRAME = SF = FRAME_TO_SEC = 1 / FRAMERATE

# Reserved zIndex sentinel for background elements (e.g. Plane's grid — see
# Input.background()). User content always has zIndex >= 0 (sendToBack
# clamps to that floor), so this value is never produced by normal
# layer-order operations and unambiguously marks "background".
# Excluded from Context.maxZIndex/minZIndex.
BACKGROUND_Z_INDEX = -1

# fmt: off
# direction
ORIGIN = v2(0, 0)
UP     = v2(None, 1)
DOWN   = v2(None, -1)
RIGHT  = v2(1, None)
LEFT   = v2(-1, None)
# 3d
# OUT = 0, 0, 1
# IN = 0, 0, -1
UR: v2[maybe[number], maybe[number]] = UP + RIGHT
UL: v2[maybe[number], maybe[number]] = UP + LEFT
DR: v2[maybe[number], maybe[number]] = DOWN + RIGHT
DL: v2[maybe[number], maybe[number]] = DOWN + LEFT

TOP_SIDE    = v2(None, WORLD_OFFSET_Y)
BOTTOM_SIDE = v2(None, -WORLD_OFFSET_Y)
RIGHT_SIDE  = v2(WORLD_OFFSET_X, None)
LEFT_SIDE   = v2(-WORLD_OFFSET_X, None)

BL: v2[maybe[number], maybe[number]] = BOTTOM_SIDE + LEFT_SIDE
BR: v2[maybe[number], maybe[number]] = BOTTOM_SIDE + RIGHT_SIDE
TL: v2[maybe[number], maybe[number]] = TOP_SIDE + LEFT_SIDE
TR: v2[maybe[number], maybe[number]] = TOP_SIDE + RIGHT_SIDE
# fmt: on

# Every name above that depends on the resolution — i.e. everything setScreen
# has to rewrite, here and in whoever star-imported it.
_SCREEN_DERIVED = (
    "Align",
    "SCREEN_WIDTH", "SCREEN_HEIGHT", "SW", "SH",
    "WORLD_WIDTH", "W", "WORLD_HEIGHT", "H",
    "WORLD_OFFSET_X", "WORLD_OFFSET_Y",
    "TOP_SIDE", "BOTTOM_SIDE", "RIGHT_SIDE", "LEFT_SIDE",
    "BL", "BR", "TL", "TR",
)  # fmt: skip


def setScreen(width: int, height: int) -> None:
    """
    Re-derive the world box for a new resolution, mid-process.

    Called from C++ (applyScreenSize) only when videocode is *already*
    imported — the normal path is the import-time read of VC_SCREEN above,
    which needs no rebinding at all. This exists for the one case that can't
    take that path: the visual-regression suite renders scenes of different
    sizes in a single interpreter.

    Star-imports copy values, so rebinding this module's globals isn't
    enough — every videocode module that pulled these names in gets the new
    ones too. The one thing this cannot reach is a value captured as a
    *default argument*, evaluated once when its module was imported: no
    rebinding of a global can change it. So a template whose default depends
    on the world box must not spell it as a literal default — it takes `None`
    and resolves against the live `W`/`H` in its body, as `SplitView`
    (margins) and `PositiveGraph` (ranges) do. Add a new one and follow suit.
    """
    global SCREEN_WIDTH, SCREEN_HEIGHT, SW, SH
    global WORLD_WIDTH, W, WORLD_HEIGHT, H, WORLD_OFFSET_X, WORLD_OFFSET_Y
    global TOP_SIDE, BOTTOM_SIDE, RIGHT_SIDE, LEFT_SIDE, BL, BR, TL, TR

    SCREEN_WIDTH, SCREEN_HEIGHT = int(width), int(height)
    SW, SH = SCREEN_WIDTH, SCREEN_HEIGHT

    WORLD_WIDTH = W = SCREEN_WIDTH / WORLD_TO_SCREEN_RATIO
    WORLD_HEIGHT = H = SCREEN_HEIGHT / WORLD_TO_SCREEN_RATIO

    WORLD_OFFSET_X = WORLD_WIDTH / 2
    WORLD_OFFSET_Y = WORLD_HEIGHT / 2

    TOP_SIDE = v2(None, WORLD_OFFSET_Y)
    BOTTOM_SIDE = v2(None, -WORLD_OFFSET_Y)
    RIGHT_SIDE = v2(WORLD_OFFSET_X, None)
    LEFT_SIDE = v2(-WORLD_OFFSET_X, None)

    BL = BOTTOM_SIDE + LEFT_SIDE
    BR = BOTTOM_SIDE + RIGHT_SIDE
    TL = TOP_SIDE + LEFT_SIDE
    TR = TOP_SIDE + RIGHT_SIDE

    import sys

    fresh = globals()
    for module in list(sys.modules.values()):
        if not getattr(module, "__name__", "").startswith("videocode"):
            continue
        for name in _SCREEN_DERIVED:
            if hasattr(module, name):
                setattr(module, name, fresh[name])


# fmt: off


class Direction(Enum):
    """
    A cardinal screen direction, for entrance/exit/transition effects
    (`slideIn`, `wipeOut`, `push`, ...). The value is the unit vector in
    world coordinates (Y positive-up).

        rect.apply(slideIn(direction=Direction.BOTTOM))
        push(sceneA, sceneB, direction=Direction.LEFT)
    """

    LEFT = (-1.0, 0.0)
    RIGHT = (1.0, 0.0)
    TOP = (0.0, 1.0)
    BOTTOM = (0.0, -1.0)

    @property
    def vector(self) -> tuple[float, float]:
        """Unit direction vector in world coordinates."""
        return self.value

    @property
    def opposite(self) -> Direction:
        x, y = self.value
        return Direction((-x, -y))

    @property
    def side(self) -> str:
        """Lowercase side name — matches `crop()`'s per-side kwargs."""
        return self.name.lower()


class Axis(Enum):
    """Which axis an oscillating effect (`shake`) moves along."""

    X = "x"
    Y = "y"
    BOTH = "both"


class Clock(StrEnum):
    """
    The ambient clocks a `wait(n, stop=[...])` can pause — everything else
    (scheduled state: positions, colors, visibility) holds by itself during
    a gap. `freeze(n)` = a wait stopping ALL of them.

    - `VIDEOS`: Video playback.
    - `PAINTS`: shader fills (silk/fire/starNest/mathShader patterns).
    - `EFFECTS`: time-driven effect progress (vhs, glitch, lightSweep, ...).
    """

    VIDEOS = "videos"
    PAINTS = "paints"
    EFFECTS = "effects"


class UVMapping(StrEnum):
    """
    How a texture (`Image`/`Video`) is wrapped onto its shape. Values match
    the C++ parser in `BezierPath.cpp` (a `StrEnum`, so members serialize to
    the JSON stack as their plain string value).

    - `STRETCH` (default): bbox-normalized UVs — the texture is stretched to
      the shape's bounding box.
    - `RADIAL`/`CONIC`: polar UVs around the bbox center, mirroring
      `RadialGradient`/`ConicGradient`'s center/angle convention; `uvAngle`
      (degrees) rotates the angular origin.
    """

    STRETCH = "stretch"
    RADIAL = "radial"
    CONIC = "conic"


class Split(StrEnum):
    """
    How a `SplitView` lays its two panels out. Named after what each PANEL
    is, like CSS grid — so `COLUMNS` means "two columns", side by side, and
    `ROWS` means "two rows", stacked. Read it as the shape of one panel, not
    as "in a row":

        COLUMNS          ROWS
        ┌───┬───┐        ┌───────┐
        │ a │ b │        │   a   │
        │   │   │        ├───────┤
        └───┴───┘        │   b   │
                         └───────┘

    `a` is always the first panel and `b` the second, so a scene written
    against `sv.a`/`sv.b` reads the same either way — only where they sit
    changes.

    - `AUTO` (default): `COLUMNS` in a landscape world, `ROWS` in a square or
      portrait one. A scene laid out this way survives a change of resolution:
      side-by-side at 16x9, stacked at 9x16, without touching the scene. In a
      16x9 world `AUTO` and `COLUMNS` are the same layout — the two only
      differ once the frame is square or taller.
    - `COLUMNS`: side by side, full height.
    - `ROWS`: stacked, full width — the only layout that leaves each panel
      usable when the frame is as tall as it is wide.

        sv = SplitView(ratio=3 / 5)                    # follows the frame
        sv = SplitView(ratio=3 / 5, split=Split.ROWS)  # stacked, always
    """

    AUTO = "auto"
    COLUMNS = "columns"
    ROWS = "rows"


class Align(StrEnum):
    """
    Where a member sits ACROSS a `Row` or a `Column` — the axis the layout does
    not space along. Named after the edge it flushes, so the word reads the same
    whichever way the line runs::

        Row                         Column
        START   tops flush          START   left edges flush
        CENTER  middles (default)   CENTER  middles (default)
        END     bottoms flush       END     right edges flush

        Row(a, b, gap=0.3, align=Align.START)
    """

    START = "start"
    CENTER = "center"
    END = "end"


class Anchor(StrEnum):
    """
    What a per-letter transform on a `Text` turns around — After Effects' Anchor
    Point Grouping, and for the same reason it exists there: a `Letter` has no
    downstream identity to parent to, so its pivot has to be a rule the engine
    resolves when it emits, not an object an author can hold.

        Anchor.ALL          Anchor.WORD         Anchor.CHARACTER
        one pivot for       one per word,       one per letter, so
        the whole line      words spin as       each spins in place
                            wholes

    - `ALL` (default): the group's own pivot — what a `Text` has always done.
    - `LINE`: one pivot per line, split on newlines.
    - `WORD`: one per whitespace-separated run.
    - `CHARACTER`: each letter turns and scales about its own centre, so
      nothing travels and every glyph spins where it stands.

    Set it on the text, the way After Effects sets it on the layer, rather
    than per call:

        t = Text("hello world")
        t.anchor = Anchor.WORD
        t.rotateBy(20)

    `about=` still wins over all of it: a point the author placed by hand is
    an answer, not a question about the content.
    """

    ALL = "all"
    LINE = "line"
    WORD = "word"
    CHARACTER = "character"


class Space(StrEnum):
    """
    Which space a math-shader paint (`fillColor=starNest()`, `silk()`, ...)
    is measured in — where its pattern is centred and what one pattern-unit
    is worth. Resolved in C++ by `resolveEffectParams`, the one place that
    knows a mesh's real extents.

    - `SHAPE` (default): the host shape's own box, every frame. The pattern
      moves and scales WITH its host, so a growing shape magnifies the
      pattern instead of resampling it. This is what every other paint in
      the repo already does (gradients project in local mesh space, textures
      default to `UVMapping.STRETCH`) and what Manim does, where colour data
      rides the mobject's points.
    - `FRAME`: the whole frame. The host becomes a window onto a
      frame-wide pattern — move the shape and it slides over a fixed
      pattern, like a torch beam.
    - `ANCHOR`: the host's box FROZEN at the frame the fill was assigned
      (`Metadata::fillShaderSince`, the same instant that already freezes
      the paint's clock). The pattern stays pinned where it was, so a
      growing shape UNCOVERS it. Re-derived from that declared frame, never
      remembered from render history — so it survives hot-reload and
      preview scrubbing.
    - `GROUP`: the union of every host sharing this paint instance — one
      nebula across a whole `Text` instead of one per letter (assigning one
      `starNest()` to a `Text` broadcasts that instance to every letter).

    Rotation is not followed in any mode yet; the shape's box is an AABB.

        Text("HI", fontSize=3, fillColor=starNest(space=Space.GROUP))
        sq.fillColor = silk(space=Space.ANCHOR)   # revealed, not resampled
    """

    SHAPE = "shape"
    FRAME = "frame"
    ANCHOR = "anchor"
    GROUP = "group"


# colors
TRANSPARENT = rgba(000, 000, 000, 0)
WHITE       = rgba(255, 255, 255)
BLACK       = rgba(000, 000, 000)
GRAY        = WHITE | BLACK
GRAY_10     = rgba(10, 10, 10)

RED         = rgba(255, 0, 0)
GREEN       = rgba(0, 255, 0)
BLUE        = rgba(0, 0, 255)
YELLOW      = rgba(255, 255, 0)

RED_A       = rgba("#FC6255")
RED_B       = rgba("#ED7F7B")

GREEN_A     = rgba("#9ADF8E")

BLUE_A      = rgba("#58C4DD") # light blue
BLUE_B      = rgba("#0B142B") # very dark blue
BLUE_C      = rgba("#69A5F1")
# fmt: on

DEBUG = logger.Logger(prefix="Debug", color=logger.TEXT_GREEN)
