#!/usr/bin/env python3

#
# chess_montage.py — the montage of the chess game, in two reels.
#
# Reel 1 (this file): the EFFECT SHOWCASE. Each shot plays a single effect and
# writes its name on screen, so that "put a snapZoom there" later means
# something precise.
#
# Reel 2 (to come): the montage of the game itself, which will draw on the
# vocabulary named below.
#
#   # open in the UI (dock, timeline, properties):
#   MONTAGE_SOURCE=~/Desktop/Projets/Evolvia/first_test.mov \
#   ./video-code --editor --file chess_montage.py
#
#   # write the file, at the size and fps of the source:
#   MONTAGE_SOURCE=~/Desktop/Projets/Evolvia/first_test.mov \
#   ./video-code --file chess_montage.py --generate reel.mp4 \
#                --width 1322 --height 1526 --framerate 60
#
# --width/--height are FREE: the shot is scaled to FIT the frame (never
# stretched, never cropped), and what is left is black. Giving them at the
# native size of the source avoids a needless resampling.
#
# --framerate only shapes the output file: a scene is ALWAYS written at 30 fps
# (Config::SCENE_FRAMERATE, hard-coded in the C++), and the compiler duplicates
# or drops frames to reach the requested fps. A render at 60 therefore gives a
# 60 fps file with 30 distinct frames per second. The PLAYBACK speed of the
# source is set by the decimation further down.
#
# Every coordinate is a FRACTION, never pixels and never anything that knows
# what is being filmed:
#   - the camera moves (zoomTo, travelling, impact, whipPan) take fractions of
#     the MEDIA box;
#   - the light (spotlightOn, zoneFocus) takes fractions of the FRAME.
# Turning "square c5" into either one is the caller's job — videocode knows
# nothing about chess, and that is deliberate.
#

import os

from videocode import *
from videocode.template.effect.framing import containSize
# The montage effects live in effect/other/: they are not methods of Input,
# they are imported one by one and passed to .apply().
from videocode.template.effect.other.camera import punchIn, reframe, snapZoom, travelling, zoomTo
from videocode.template.effect.other.desaturate import desaturate
from videocode.template.effect.other.flash import flash
from videocode.template.effect.other.glitchBurst import glitchBurst
from videocode.template.effect.other.impact import impact
from videocode.template.effect.other.retime import decimate
from videocode.template.effect.other.scope import scope, unscope
from videocode.template.effect.other.spotlightOn import spotlightOn, zoneFocus
from videocode.template.effect.other.vignetteIn import vignetteBeat
from videocode.template.effect.other.whipPan import whipPan
from videocode.template.input._inputs import *
from videocode.utils.probe import probeVideo

# The source is an environment variable so that the file stays valid when the
# video changes name or folder.
SOURCE = os.path.expanduser(os.environ.get("MONTAGE_SOURCE", "~/Desktop/Projets/Evolvia/first_test.mov"))

SHOT = 2.6              # seconds per shot: long enough to read the label, short enough to cut
LEAD = 0.5              # delay before the effect starts: the plate is up (0.15 + 0.3) before it fires
TAIL = 0.4              # tail at the end of the shot: leaves room for the reframe before the cut
EFFECT = SHOT - LEAD - TAIL   # longest an effect may last and still fit in its shot
START_AT = 19.0         # we enter the game at 19 s, where something happens

PLATE = rgba(28, 30, 40, 235)   # background of the title plate (opaque: otherwise the pieces show through)
ACCENT = rgba(255, 168, 150)    # the name of the effect
MUTED = rgba(150, 162, 200)     # the description line

# The point we keep coming back to: the centre of the board in THIS capture.
# A fraction, measured once by eye — videocode is given a number, not the name
# of a square.
FOCUS_X, FOCUS_Y = 0.5, 0.52


# Usable width: keep a margin on each side, otherwise the plate touches the
# edge of the frame and the long descriptions run out of the picture.
MARGIN = 0.5
USABLE = WORLD_WIDTH - 2 * MARGIN

# MEASURED LIBRARY DEFECT: Text.width underestimates the rendered width.
# Measured at 936x1080, fontSize 0.3, default font: a 42-character caption
# reports 5.79 world units and takes ~8.0 on screen (a Rectangle of
# width=t.width placed behind the text only covers the middle of the
# sentence). The ratio is stable from one string to the next, so we correct by
# this factor instead of trusting the raw value. To be removed the day
# Text.width is right — hence the named constant rather than a 1.4 scattered
# through the code.
TEXT_ADVANCE = 1.4


def drawnWidth(text: Text) -> number:
    """Width really taken on screen — see TEXT_ADVANCE."""
    return text.width * TEXT_ADVANCE


def title(name: str, description: str, at: sec) -> None:
    """The name plate — the whole point of the reel."""
    label = Text(name, fontSize=0.5, fillColor=ACCENT, bold=True)
    # It takes a Text to measure a Text — but a Text built then thrown away
    # does not go away: it stays in the scene and is drawn at the origin
    # (defect X8, docs/by-example/features/shots.py), which left a ghost line
    # across every frame. So we measure at a reference size, then hide the
    # gauge FOR GOOD — letter by letter, the only way to mask a Text (see the
    # gating comment further down).
    RULER = 0.3
    gauge = Text(description, fontSize=RULER, fillColor=MUTED)
    ruler = drawnWidth(gauge)
    for letter in gauge.inputs:
        letter.hide()
    sub = Text(
        description,
        fontSize=RULER * min(1.0, USABLE / ruler),
        fillColor=MUTED,
    )
    # The plate is sized on the widest text: a fixed width would cut the long
    # descriptions.
    plate = Rectangle(
        width=min(max(drawnWidth(label), drawnWidth(sub)) + 0.6, WORLD_WIDTH - 0.3),
        height=1.4,
        fillColor=PLATE,
        strokeColor=TRANSPARENT,
        cornerRadius=12,
    )
    # WORLD_HEIGHT/2 is the top of the frame, so -WORLD_HEIGHT/2 + 1.5 puts the
    # plate at the bottom with a margin (the y axis points up, as in maths).
    y = -WORLD_HEIGHT / 2 + 1.5
    plate.position(0, y).zIndex(10)
    label.position(0, y + 0.28).zIndex(11)
    sub.position(0, y - 0.32).zIndex(11)
    for part in (plate, label, sub):
        # Hide FIRST, otherwise the 13 plates are all on screen from frame 0.
        #
        # And what must be hidden is what is REALLY DRAWN: a Text is not a
        # placed input, it is a Group of Letter (`composite is True`), and only
        # its letters reach the render. Measured: on a Text, neither
        # `opacity(0)`, nor `hide()` on the group, nor parking it off-frame
        # holds before the first fadeIn — only `hide()` set on each letter
        # does. On a Rectangle, `composite is False` and the list comes down to
        # the element itself: the same code works for both.
        for drawn in (part.inputs if part.composite else [part]):
            drawn.hide()
            drawn.show(at=at + 0.15)
        # at= is the FILM's clock; start= would be the element's clock, hence
        # cumulative — exactly the trap that stacked the shots.
        #
        # SAME frame as the show, never the next one: a `show` sets no
        # opacity, it makes the input visible at its current opacity, that is
        # FULL. Starting the fadeIn one frame later therefore let the plate pop
        # in at once, drop to zero, then rise again — a flicker before each
        # fade. On the same frame, `show` and the first step of the fade
        # (opacity 0) are set together and the entrance really starts from
        # nothing.
        part.fadeIn(at=at + 0.15, duration=0.3)
        # fadeOut does not pass at= through to apply(): we advance the
        # element's clock by hand, then leave with start=0 (= "now").
        part.waitTo(round((at + SHOT - TAIL) * FRAMERATE))
        # hide=True: once invisible, the input really leaves the render.
        part.fadeOut(duration=0.3, hide=True)


# --- the reel ---------------------------------------------------------------
# (name, one-line description, the effect, whether to reframe after the shot)

# The last shot closes the cinema bars, holds them, then opens them again. The
# three durations must fit together EXACTLY: a shader only holds for the frame
# it is set on, so the slightest gap between the closing and the opening shows
# the full picture again and then slams the bars back. That is what flickered.
SCOPE_MOVE = 0.6        # closing of the bars
SCOPE_TO_OPEN = 0.8     # delay before they reopen, measured from the same instant
SCOPE_HOLD = SCOPE_TO_OPEN - SCOPE_MOVE   # what the bars must hold between the two

shots: list[tuple[str, str, Effect, bool]] = [
    # slow continuous zoom: touches ONLY scale, so it would combine with a pan
    # without the two stepping on each other.
    ("punchIn", "slow push, the camera is never still",
     punchIn(zoom=1.22, duration=EFFECT), True),
    # the zoom is set once on the first frame, after that it is a pure move:
    # from one corner of the media to the other.
    ("travelling", "glide from one point to another, fixed zoom",
     travelling(fromX=0.15, fromY=0.8, toX=0.85, toY=0.2, zoom=1.7, duration=EFFECT), True),
    # zoomTo reframes to bring (x, y) to the centre of the frame, and stays there.
    ("zoomTo", "push in on one exact point and stay there",
     zoomTo(x=FOCUS_X, y=FOCUS_Y, zoom=2.2, duration=1.2), True),
    # there and back: exponential attack, hold, exact return to the origin —
    # hence needsReframe=False, it puts itself back.
    ("snapZoom", "jump onto the point, hold, come back",
     snapZoom(x=FOCUS_X, y=FOCUS_Y, zoom=2.4, hold=EFFECT - 0.9), False),
    # punch + damped shake in ONE effect: two separate effects would fight
    # over the position channel and the last one would overwrite the other.
    ("impact", "the hit: punch + damped shake",
     impact(x=FOCUS_X, y=FOCUS_Y, zoom=1.3, amplitude=0.14, duration=0.9), False),
    # Accepted DOWNGRADE: a real whip streaks along the direction of the move,
    # videocode's blur is isotropic (no directional blur shader). At 0.4 s it
    # passes for a whip; slower, it shows.
    ("whipPan", "whip from one point to another, blurred in motion",
     whipPan(toX=0.85, toY=0.35, blur=12, duration=0.4), True),
    # spotlight: coordinates of the FRAME, not of the media (it is a shader, it
    # works on the rendered pixels and ignores the geometry of the shot).
    ("spotlightOn", "everything dims except a pool of light",
     spotlightOn(x=0.5, y=0.5, radius=0.17, duration=EFFECT), False),
    ("zoneFocus", "same thing, but on a rectangular zone",
     zoneFocus(x=0.5, y=0.45, width=0.62, height=0.5, duration=EFFECT), False),
    ("desaturate", "the colour drains out, then comes back",
     desaturate(amount=1.0, duration=EFFECT, fade=0.5), False),
    ("flash", "a burst of white",
     flash(amount=170, times=2, duration=0.9), False),
    # glitch is driven by time: we emit ONE with a duration. Emitting one per
    # frame would restart its clock on every frame and the pattern would freeze.
    ("glitchBurst", "signal loss: slices and blocks",
     glitchBurst(amount=6, blocks=30, duration=0.5), False),
    ("vignetteBeat", "the corners close in and open again",
     vignetteBeat(intensity=0.75, duration=EFFECT), False),
    ("scope", "cinema bars, 2.39:1",
     scope(ratio=2.39, duration=SCOPE_MOVE, hold=SCOPE_HOLD), False),
]

REEL = len(shots) * SHOT  # total target duration, in seconds of film

# Read the real size instead of hard-coding it, otherwise changing the source
# silently breaks the framing.
sourceWidth, sourceHeight, sourceFps = probeVideo(SOURCE)
# The source is a region screen capture: macOS burned its marquee (the dashed
# rectangle and its round handles) into the four edges. Measured on a still
# frame: the band runs from the edge to ~23 px, and the real content only
# starts at ~27 px — 26 px per edge removes it without biting into the content.
#
# We remove it by pushing the media OUT of the frame, not with the `crop`
# shader. A `crop` would have worked, but there is only one crop per frame and
# per input: `scope` sets one too, and the last write wins — the cinema bars
# would have erased the edge trim, and the marquee would have come back for
# that whole shot. Here the GEOMETRY does the work, so the `crop` channel stays
# free, and the margin follows the zooms without any care from us.
#
# The usable area is the one made to FIT the frame; the whole media is larger
# in the same proportion, and its border overflows just outside.
BORDER = 26  # pixels of marquee on each edge of the source
usableWidth = sourceWidth - 2 * BORDER
usableHeight = sourceHeight - 2 * BORDER
keepWidth, keepHeight = containSize(usableWidth, usableHeight)
clipWidth = keepWidth * sourceWidth / usableWidth
clipHeight = keepHeight * sourceHeight / usableHeight

# The bars. In "contain", what the shot does not cover stays transparent: a
# full-frame black background goes underneath so that they are BLACK BARS and
# not a hole. zIndex(-1): under everything else.
backdrop = Rectangle(
    width=WORLD_WIDTH, height=WORLD_HEIGHT,
    fillColor=BLACK, strokeColor=TRANSPARENT,
)
backdrop.position(0, 0).zIndex(-1)

# PLAYBACK SPEED — the least obvious trap of this engine.
#
# The engine consumes ONE source frame per SCENE frame, and a scene is always
# written at 30 fps (`Config::SCENE_FRAMERATE`, hard-coded on the C++ side;
# --framerate only changes the output file, by duplicating frames). A 60 fps
# source therefore played at HALF SPEED: everything was in slow motion.
#
# This cannot be fixed with `speedRamps`: a ramp does change which source frame
# is decoded, but the length the clip claims stays `endFrame - startFrame`,
# whatever the rate — the reel came out twice too long, with a dead tail after
# the last shot. Only `cuts` shorten that length.
#
# Which is convenient, because going from 60 to 30 fps is literally dropping
# every other frame. `decimate` does it, for any ratio.
#
# startFrame / endFrame are in SOURCE frames, at the fps of the source. The
# window must therefore cover REEL seconds of SOURCE, which the decimation then
# brings down to REEL seconds of scene. Without endFrame, the clip would claim
# its whole duration (here 10 min of render).
sceneFrames = round(REEL * FRAMERATE)
ratio = sourceFps / FRAMERATE          # 2.0 for a 60 fps source, 1.0 at 30
firstFrame = int(START_AT * sourceFps)
clip = Video(
    SOURCE,
    startFrame=firstFrame,
    endFrame=firstFrame + round((sceneFrames - 1) * ratio) + 1,
    cuts=decimate(firstFrame, sceneFrames, ratio),
    width=clipWidth,
    height=clipHeight,
)
# zIndex(0): the shot is the background, the title plates go above it.
clip.position(0, 0).zIndex(0)


for index, (name, description, effect, needsReframe) in enumerate(shots):
    at = index * SHOT              # each shot starts at its rank * SHOT
    title(name, description, at)
    # at= (the film's clock) and not start= (the element's clock, cumulative).
    # at + LEAD, not at: the short effects (flash, glitchBurst, scope) were
    # over before their own label could be read — in a reel whose only purpose
    # is to NAME the effects, that is the most expensive flaw.
    clip.apply(effect, at=at + LEAD)
    if needsReframe:
        # The reframe goes in the tail of the shot: after the end of the effect
        # (which lasts EFFECT at most) and before the next shot. at= refuses to
        # write in the element's past, hence this strict order.
        clip.apply(reframe(), at=at + SHOT - 0.15)

# scope is the only look that must be undone by hand: the bars stay. We undo it
# after scope has ended, otherwise the two writes fight over the Crop channel
# on the same frames (the engine reports it, and the last one wins). From the
# SAME instant as the `scope` of the last shot (its `at=`), shifted by
# SCOPE_TO_OPEN — that is what guarantees the hold above lands exactly.
clip.apply(unscope(ratio=2.39, duration=0.5),
           at=(len(shots) - 1) * SHOT + LEAD + SCOPE_TO_OPEN)

# --- retiming ---------------------------------------------------------------
# slowMotion / fastForward / freezeFrame / rewind are NOT effects: they change
# which SOURCE frame is decoded, which Video decides once and for all at
# construction. See videocode/template/effect/other/retime.py. The reel above
# cannot show them without rebuilding the clip, so they play on a separate
# pass:
#
#   Video(SOURCE, speedRamps=[
#       slowMotion(at=2, duration=3, rate=0.35),
#       fastForward(at=8, duration=20, rate=6),
#       freezeFrame(at=30, duration=1.5),
#   ])
#
# Sampling is nearest-frame, with no interpolation: the slow motion is a real
# slow motion, not one smoothed optical-flow style — that does not exist in
# the engine.
