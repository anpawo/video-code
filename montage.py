#!/usr/bin/env python3

#
# montage.py — the montage of the GAME (reel 2), test bench.
#
# chess_montage.py names the effects one by one; here they are used for real:
# we take a window of the game and lay a few camera moves over it — pushes,
# zooms on a chess move, travellings. Nothing else for now, the goal is to see
# whether the rhythm holds.
#
#   # open in the UI:
#   MONTAGE_SOURCE=~/Desktop/Projets/Evolvia/first_test.mov \
#   ./video-code --editor --file montage.py
#
#   # write the file, at the size and fps of the source:
#   MONTAGE_SOURCE=~/Desktop/Projets/Evolvia/first_test.mov \
#   ./video-code --file montage.py --generate /tmp/montage.mp4 \
#                --width 1322 --height 1526 --framerate 60
#
# In both cases PYTHONPATH MUST be exported first, the embedded interpreter
# ignores the PATH:
#   export PYTHONPATH="$PWD/.venv/lib/python3.14/site-packages"
#

import os

from videocode import *
from videocode.template.effect.framing import containSize
from videocode.template.effect.other.camera import punchIn, reframe, snapZoom, travelling, zoomTo
from videocode.template.effect.other.retime import decimate
from videocode.template.input._inputs import *
from videocode.utils.probe import probeVideo

SOURCE = os.path.expanduser(os.environ.get("MONTAGE_SOURCE", "~/Desktop/Projets/Evolvia/first_test.mov"))

START_AT = 118.0        # where we enter the game, in seconds of source
REEL = 18.0             # duration of the reel, in seconds of scene
BORDER = 26             # macOS recording marquee, in pixels on each edge


# --- the source -------------------------------------------------------------
#
# Probing, fitting the frame and dropping every other frame are tools of the
# library (probeVideo, containSize, decimate): this file only keeps what is
# specific to THIS game.

sourceWidth, sourceHeight, sourceFps = probeVideo(SOURCE)

# The macOS marquee is burned into the pixels: we frame the USABLE area and
# scale the whole media so that the edges fall outside the frame. The GEOMETRY
# does it, not the `crop` shader — there is only one crop per frame and per
# input, and we keep that channel free for the effects.
usableWidth = sourceWidth - 2 * BORDER
usableHeight = sourceHeight - 2 * BORDER
keep = containSize(usableWidth, usableHeight)
keepWidth, keepHeight = keep.x, keep.y
clipWidth = keepWidth * sourceWidth / usableWidth
clipHeight = keepHeight * sourceHeight / usableHeight

# In "contain", what is not covered stays transparent: a full-frame black
# background underneath so that they are BLACK BARS and not a hole.
backdrop = Rectangle(
    width=WORLD_WIDTH, height=WORLD_HEIGHT,
    fillColor=BLACK, strokeColor=TRANSPARENT,
)
backdrop.position(0, 0).zIndex(-1)

sceneFrames = round(REEL * FRAMERATE)
ratio = sourceFps / FRAMERATE          # 2.0 for a 60 fps source
firstFrame = int(START_AT * sourceFps)

clip = Video(
    SOURCE,
    startFrame=firstFrame,
    endFrame=firstFrame + round((sceneFrames - 1) * ratio) + 1,
    cuts=decimate(firstFrame, sceneFrames, ratio),
    width=clipWidth,
    height=clipHeight,
)
clip.position(0, 0).zIndex(0)


# --- where to aim -----------------------------------------------------------
#
# videocode knows nothing about chess, and that is deliberate: the camera
# effects take FRACTIONS of the media box. Turning "d8" into a fraction is the
# job of THIS file, not of the library.
#
# Measured once on a frame of the source (1322x1526): the board runs from x=24
# to x=1304 and from y=124 to y=1400, that is eight squares of 160 px.
BOARD_X, BOARD_Y, SQUARE = 24.0, 124.0, 160.0
FILES = "abcdefgh"


def square(name: str) -> tuple[float, float]:
    """
    The centre of a square, in fractions of the media — "d8" -> (0.460, 0.134).

    The board is seen from White's side: rank 8 is at the top, so rank n is on
    row (8 - n) counting from the top.
    """
    file = FILES.index(name[0])
    rank = int(name[1:])
    x = BOARD_X + (file + 0.5) * SQUARE
    y = BOARD_Y + (8 - rank - 0.5) * SQUARE
    return x / sourceWidth, y / sourceHeight


# --- the reel ---------------------------------------------------------------
#
# The instants are set on REAL moves of the game, read off the source (the
# frame where both squares change), and brought back to the film's clock:
#   film = (source - START_AT). Chess moves used, in seconds of film:
#     2.84  the white queen crosses the d-file and captures on d8
#     5.84  the black rook recaptures on d8
#    14.17  the c2 pawn advances to c4
#    16.51  the black bishop comes out to c5
#
# Each camera move arrives a touch BEFORE its chess move, so that the camera is
# already in place when the piece moves — the other way round feels like
# chasing it.
d8 = square("d8")
c4 = square("c4")
c5 = square("c5")
a1 = square("a1")
h8 = square("h8")

# (at, effect, whether to reframe afterwards)
moves = [
    # A slow opening push: the camera is never still, even while nothing is
    # happening yet.
    (0.0, punchIn(zoom=1.12, duration=2.3), True),

    # The queen capture: a sharp move, hence snapZoom — it rises fast, holds,
    # and comes back by itself (no reframe afterwards, it does it itself).
    (2.5, snapZoom(x=d8[0], y=d8[1], zoom=2.1, hold=0.9, attack=0.12, release=0.4), False),

    # The recapture, on the same square: this time a settled arrival, for the
    # difference in tone between the two moves.
    (5.2, zoomTo(x=d8[0], y=d8[1], zoom=1.9, duration=0.9), True),

    # The wide sweep of the board, corner to corner, while nothing decisive is
    # happening: it fills the dead time without showing it.
    (7.4, travelling(fromX=a1[0], fromY=a1[1], toX=h8[0], toY=h8[1],
                     zoom=1.5, duration=4.2), True),

    # A breath: back to wide, then a gentle push again.
    (12.0, punchIn(zoom=1.1, duration=1.8), True),

    # The c2-c4 pawn.
    (14.0, zoomTo(x=c4[0], y=c4[1], zoom=2.0, duration=0.8), True),

    # The bishop coming out to c5: a small camera move from one square to the
    # other rather than a cut.
    (16.0, travelling(fromX=c4[0], fromY=c4[1], toX=c5[0], toY=c5[1],
                      zoom=1.8, duration=1.4), True),
]

# The `at=` values must be increasing: the film's clock refuses to write in an
# element's past. The list above is already in order, and each reframe slips
# in just before the next camera move.
for index, (at, effect, needsReframe) in enumerate(moves):
    clip.apply(effect, at=at)
    if needsReframe:
        nextAt = moves[index + 1][0] if index + 1 < len(moves) else REEL - 0.2
        clip.apply(reframe(), at=nextAt - 0.15)
