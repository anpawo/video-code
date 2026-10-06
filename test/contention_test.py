#!/usr/bin/env python3

"""
Assertion-based tests for `Context.contendedKeys()`: two statements writing the
same key over the same frames, where the order the lines were typed in is what
decides the video.
Run directly: `python3 test/contention_test.py`
"""

import contextlib
import io
import json
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "test")
from helpers import check, section, summary

from videocode import Context, Square
from videocode.serialize import execSource


def contentions(body: str) -> list[dict]:
    # The run PRINTS what it finds; this reads the same finding as data.
    with contextlib.redirect_stderr(io.StringIO()):
        execSource("from videocode import *\n\ns = Square(side=1)\n" + body + "\nwait(3)\n", "contention_test_scene.py")
    return Context.contendedKeys()


def stateOf(body: str, index: int, at: int) -> dict:
    """The same scene shape, read at one frame through `Context.stateAt`."""
    with contextlib.redirect_stderr(io.StringIO()):
        execSource("from videocode import *\n\ns = Square(side=1)\n" + body + "\nwait(3)\n", "state_test_scene.py")
    return Context.stateAt(index, at)


# ── Where an element IS, at one frame ───────────────────────────────────────
# The card's chips say what the CALL takes — `side`, `fillColor`. They never say
# where the thing is, because that is not an argument: it is what every line
# above has done to it by that frame. This is the only answer, and the editor's
# read-out is the only place it is shown.
section("stateAt — the element's own channels, resolved at a frame")

# One second of travel from wherever the square starts to x = 4: at the frame it
# opens the base still holds, halfway it is between, at the end it has arrived.
opening = stateOf("s.moveTo(x=4, duration=1)", 0, 0)
midway = stateOf("s.moveTo(x=4, duration=1)", 0, 15)
landed = stateOf("s.moveTo(x=4, duration=1)", 0, 30)

check("it answers with the channels, not with arguments",
      "Position:x" in landed and "side" not in landed)
check("at the end of the move it has arrived", abs(landed["Position:x"] - 4) < 0.01)
check("halfway it is between the two", opening["Position:x"] < midway["Position:x"] < 4)
check("an element nobody has moved still reads its placement",
      abs(stateOf("s.position(2, 0)", 0, 30)["Position:x"] - 2) < 0.01)
check("a frame before anything was written reads the placement too",
      abs(stateOf("s.position(2, 0)\ns.moveTo(x=4, start=1, duration=1)", 0, 5)["Position:x"] - 2) < 0.01)
check("an index no scene made answers with nothing", Context.stateAt(9999, 0) == {})

# An ARGUMENT that something animates is in there too, under its own name: a
# `fill()` writes the colour it has reached, frame by frame. Without it the card
# would go on showing the colour the line was written with while the shape has
# changed — and nothing else in the editor knows the difference.
fading = "s.fill(BLUE, duration=1)"
landedColor = stateOf(fading, 0, 30)["Args:fillColor"]
check("an animated argument reads its value at that frame",
      (landedColor.r, landedColor.g, landedColor.b) == (0, 0, 255))
check("and halfway through it is between the two",
      0 < stateOf(fading, 0, 15)["Args:fillColor"].b < 255)
check("an argument nobody animates is not claimed at all",
      "Args:side" not in stateOf(fading, 0, 30))


# ── What it must catch ──────────────────────────────────────────────────────
# Two animations over the same frames on one key do not blend: a frame holds
# one entry per key, so the later call erases the earlier one wherever they
# meet, and swapping the two lines gives a different video.
section("contendedKeys — two animations fighting over one key")

# The example is two moves on the SAME axis. It used to be x against y — until
# an effect began claiming only the axis it was given, which made those two
# compose. Two claims on one axis is what is left, and it is the real case.
fight = contentions("s.moveTo(x=2, duration=1)\ns.moveBy(x=1, duration=1)")
check("the pair is reported", len(fight) == 1)
check("named by channel, axis included", fight and fight[0]["key"] == "Position:x")
check("both call sites are named", fight and {fight[0]["a"]["call"], fight[0]["b"]["call"]} == {"moveTo", "moveBy"})
check("with the frames they share", fight and fight[0]["frames"] == 30)

check(
    "reported whichever order the two lines are in",
    len(contentions("s.moveBy(x=1, duration=1)\ns.moveTo(x=2, duration=1)")) == 1,
)
check(
    "partial overlap counts too",
    len(contentions("s.moveTo(x=2, duration=1)\ns.moveBy(x=1, start=0.5, duration=1)")) == 1,
)

# ── What it must NOT catch ──────────────────────────────────────────────────
# The repository's 52 scenes report nothing, and these are the shapes that is
# made of. A rule that cries wolf on how every scene is written is a rule
# nobody reads.
section("contendedKeys — silent on how a scene is normally written")

check("different keys never contend", not contentions("s.moveTo(x=2, duration=1)\ns.fadeIn(duration=1)"))
check(
    "a construction call is the animation's starting value, not a rival",
    not contentions("s.position(x=-2)\ns.moveTo(x=2, duration=1)"),
)
check(
    "flush() puts them in separate windows",
    not contentions("s.moveTo(x=2, duration=1)\ns.flush()\ns.moveBy(x=1, duration=1)"),
)
check(
    "back to back, sharing only the handover frame",
    not contentions("s.moveTo(x=2, duration=1)\ns.moveBy(x=1, start=1, duration=1)"),
)
check("one statement is never its own rival", not contentions("s.moveTo(x=2, duration=1)"))

# ── One emitter call is one statement ───────────────────────────────────────
# The bug this guards: `ease()` — and `over()`, `easeTogether`, `fillIn` on top
# of it — writes a frame at a time, so a ramp arrives as N statements one frame
# long. Counting those raw made the whole of paint animation invisible here:
# every span was a single frame, and a single frame is rightly never contended.
# Two `over().fillColor` overlapping by half a second reported nothing at all.
section("contendedKeys — a frame-by-frame emitter is still one statement")


def painted(body: str) -> list[dict]:
    with contextlib.redirect_stderr(io.StringIO()):
        execSource(
            "from videocode import *\n\nr = Rectangle(width=2, height=2, fillColor=BLUE_B)\n" + body + "\nwait(3)\n",
            "contention_test_paint.py",
        )
    return Context.contendedKeys()


check("two overlapping fillColor ramps are reported", len(painted("r.over(duration=0.5).fillColor = RED_B\nr.over(duration=0.5).fillColor = WHITE")) == 1)
check("named by the channel, not by the shader class", painted("r.over(duration=0.5).fillColor = RED_B\nr.over(duration=0.5).fillColor = WHITE")[0]["key"] == "Args:fillColor")
check("fillColor and strokeColor are different channels", not painted("r.over(duration=0.5).fillColor = RED_B\nr.over(duration=0.5).strokeColor = WHITE"))

# ── An axis is a channel ────────────────────────────────────────────────────
# Since an effect claims only the axis it was given, two effects on different
# axes compose — so calling them a conflict would be crying wolf on the very
# thing the claim model exists to allow.
section("contendedKeys — x and y are different channels")

check("moveTo(x) and moveBy(y) do not contend", not contentions("s.moveTo(x=2, duration=1)\ns.moveBy(y=3, duration=1)"))
check("moveTo(x) twice does", len(contentions("s.moveTo(x=2, duration=1)\ns.moveTo(x=5, duration=1)")) == 1)
check("and it is named by the axis", contentions("s.moveTo(x=2, duration=1)\ns.moveTo(x=5, duration=1)")[0]["key"] == "Position:x")

# ── What a group works out is not a statement about a member ────────────────
# A group re-emits its whole window on every apply, so two chained animations
# look from the outside like two statements fighting over one key — when
# `_rigidTimeline` has already composed them per channel. But a member written
# BY HAND during a group's window is a real conflict, and must still be said.
section("contendedKeys — a group's own working-out is not a rival")


def grouped(body: str) -> list[dict]:
    with contextlib.redirect_stderr(io.StringIO()):
        execSource(
            "from videocode import *\n\na = Square(side=0.4).position(x=-1)\nb = Square(side=0.4).position(x=1)\ng = Group(a, b)\n" + body + "\nwait(3)\n",
            "contention_test_group.py",
        )
    return Context.contendedKeys()


check("chained group animations are not a conflict", not grouped("g.scaleTo(2, duration=1).rotateBy(90, duration=1)"))
check("a member written by hand during a group window IS", len(grouped("g.rotateBy(90, duration=1)\nb.moveBy(y=1, duration=1)")) == 1)

# ── A line that reaches back behind one written above it ────────────────────
# An animation reads where to start from the CURSOR, which is the right answer
# as long as the lines are written in the order they play. Give a `start=` that
# opens behind a line already written and the cursor has been carried past it:
# `moveTo(x=5, start=2)` then `moveTo(x=2)` USED TO send x from 4.99 DOWN to 2
# over the first second, where the same two lines the other way round sent it
# from 0 up to 2. Same intent, two videos, and nothing said so.
#
# `backdatedWrites()` is what sees it, and it is now also what TRIGGERS the
# repair: a run that reports one replays itself, giving every animation the
# value it really has at the frame it opens (S1). So the detector still fires
# on exactly the same shapes — what changed is that the film no longer depends
# on the order the two lines were typed in.
section("backdatedWrites — a start= that opens behind a line written above it")


def backdated(body: str) -> list[dict]:
    with contextlib.redirect_stderr(io.StringIO()):
        execSource("from videocode import *\n\ns = Square(side=1)\n" + body + "\nwait(4)\n", "contention_test_order.py")
    return Context.backdatedWrites()


check("written in the order they play: nothing to say", not backdated("s.moveTo(x=2, duration=1)\ns.moveTo(x=5, start=2, duration=1)"))
check("written the other way round: reported", len(backdated("s.moveTo(x=5, start=2, duration=1)\ns.moveTo(x=2, duration=1)")) == 1)
check(
    "and it names the line that reaches back",
    backdated("s.moveTo(x=5, start=2, duration=1)\ns.moveTo(x=2, duration=1)")[0]["b"]["line"] == 5,
)
check(
    "a different channel is not affected by it",
    not backdated("s.moveTo(x=5, start=2, duration=1)\ns.moveTo(y=2, duration=1)"),
)

# What the two orders actually produce — the point of the whole thing.
def xAt(body: str, which: int) -> float:
    with contextlib.redirect_stderr(io.StringIO()):
        execSource("from videocode import *\n" + body + "\nwait(4)\n", "contention_test_order.py")
    frames = [f for f in sorted(Context.stack[0]) if f != -1 and "Position" in Context.stack[0][f]]
    written = [Context.stack[0][f]["Position"]["args"]["x"] for f in frames]
    written = [x for x in written if x is not None]
    return written[which]


PLAYED = "\ns = Square(side=1)\ns.moveTo(x=2, duration=1)\ns.moveTo(x=5, start=2, duration=1)"
TYPED = "\ns = Square(side=1)\ns.moveTo(x=5, start=2, duration=1)\ns.moveTo(x=2, duration=1)"

check(
    "the two orders now open on the same frame — that is the whole point",
    abs(xAt(PLAYED, 0) - xAt(TYPED, 0)) < 1e-9,
)
check(
    "and they end on the same frame",
    abs(xAt(PLAYED, -1) - xAt(TYPED, -1)) < 1e-9,
)
check(
    f"the backwards order starts from 0, not from 4.99 ({xAt(TYPED, 0):.3f})",
    xAt(TYPED, 0) < 0.1,
)

# So there is nothing left to warn about: the run that reaches back bakes the
# film the other order bakes. The warning outlived the repair for three weeks,
# on the run's stderr, under the line in the editor and in --lint — telling
# people to reorder lines whose order no longer changes anything.
said = io.StringIO()
with contextlib.redirect_stderr(said):
    told = execSource("from videocode import *\n" + TYPED + "\nwait(4)\n", "contention_test_order.py")
check(
    f"a line that reaches back is not warned about any more ({told['warnings']} · {said.getvalue()[:60]!r})",
    "backdated" not in told["warnings"] and "written above it" not in said.getvalue(),
)

# One reprise repairs one link, so a CHAIN written backwards needs the scene
# replayed until it stops moving: the second `moveBy` reads its base from a run
# where the third was itself mis-based. Three moves of +1 end at 3, whichever
# order the three lines are in; before S1 the backwards one ended at 2.
FORWARD = ("\ns = Square(side=1)\ns.moveBy(x=1, start=0, duration=1)"
           "\ns.moveBy(x=1, start=1, duration=1)\ns.moveBy(x=1, start=2, duration=1)")
BACKWARD = ("\ns = Square(side=1)\ns.moveBy(x=1, start=2, duration=1)"
            "\ns.moveBy(x=1, start=1, duration=1)\ns.moveBy(x=1, start=0, duration=1)")

check(f"a chain of three +1 ends at 3.0 written forwards ({xAt(FORWARD, -1):.3f})", abs(xAt(FORWARD, -1) - 3.0) < 1e-6)
check(f"and at 3.0 written backwards, where it used to end at 2.0 ({xAt(BACKWARD, -1):.3f})", abs(xAt(BACKWARD, -1) - 3.0) < 1e-6)
check("the chain agrees frame for frame both ways", abs(xAt(FORWARD, 12) - xAt(BACKWARD, 12)) < 1e-9)

# A loop is how a storyboard is actually written, and it used to be invisible:
# `_callSpans` grouped statements by SOURCE LINE, so three `moveTo` written by
# one `for` merged into a single span reaching from the first to the last —
# nothing to compare, nothing reported, no reprise. Since S1 the grouping is by
# CALL, and the three steps are three spans again.
LOOP = ("\ns = Square(side=1)\nfor x, when in reversed([(1, 0), (2, 1), (3, 2)]):"
        "\n    s.moveTo(x=x, start=when, duration=0.8)")
LOOP_FORWARD = ("\ns = Square(side=1)\nfor x, when in [(1, 0), (2, 1), (3, 2)]:"
                "\n    s.moveTo(x=x, start=when, duration=0.8)")

with contextlib.redirect_stderr(io.StringIO()):
    execSource("from videocode import *\n" + LOOP + "\nwait(4)\n", "contention_test_loop.py")
check("a loop that writes its steps backwards is reported", len(Context.backdatedWrites()) > 0)
check(f"and it plays like the same loop written forwards ({xAt(LOOP, -1):.3f})",
      abs(xAt(LOOP, -1) - xAt(LOOP_FORWARD, -1)) < 1e-9 and abs(xAt(LOOP, 0) - xAt(LOOP_FORWARD, 0)) < 1e-9)

# The same-frame rule: an animation that opens ON the frame the object was just
# placed takes that placement as its base, not the frame before — four scenes
# of the corpus do exactly that at frame zero, and a base read one frame early
# would move all four.
PLACED = "\ns = Square(side=1).position(3, 1)\ns.moveBy(x=1, duration=1)"
check(f"a placement on the opening frame is the base ({xAt(PLACED, 0):.3f})", abs(xAt(PLACED, 0) - 3.0) < 1e-6)
check(f"so +1 from there lands on 4 ({xAt(PLACED, -1):.3f})", abs(xAt(PLACED, -1) - 4.0) < 1e-6)

# The machinery underneath, named so the coverage gate sees it used: every verb
# call records the statements it wrote (`Context.record` via the decorator),
# `Context.baseline` freezes what the pass proved, and `Context.rebase` hands
# the next call its real base.
check("a verb call is attributed to the statements it wrote", bool(Context.calls) and bool(Context.starts))
frozen = Context.baseline()
check("the baseline carries the opening frames and the windows that own them",
      set(frozen) == {"opens", "owned", "values", "starts", "seen"})
check("rebase is a no-op outside a reprise", Context.replaying is None and Context.rebase(Square(side=1)) is None)
check("record is what fills that table", callable(Context.record))

# ---------------------------------------------------------------------------
section("channelKey — the name one piece of state answers to, spelled once")

check("an ordinary shader is its own class", Context.channelKey("Position", None) == "Position")
check("an args shader is named by its attribute", Context.channelKey("Args", "fillColor") == "Args:fillColor")
check("two attributes are two channels",
      Context.channelKey("Args", "fillColor") != Context.channelKey("Args", "strokeColor"))

# The reason this function exists rather than the rule being inlined twice: the
# key a frame is STORED under (Context.apply) and the key two statements are
# judged rivals by (Input.apply) must be the same string. They used to be two
# copies of one rule, agreeing by coincidence — so this asserts they agree, not
# that either is correct in isolation.
with contextlib.redirect_stderr(io.StringIO()):
    execSource(
        "from videocode import *\n\ns = Square(side=1)\n"
        "s.over(duration=0.5).fillColor = RED_B\ns.over(duration=0.5).strokeColor = BLUE_C\nwait(2)\n",
        "contention_test_channel.py",
    )
stored = {k for f, e in Context.stack[0].items() if f != -1 for k in e}
claimed = {c for st in Context.statements for c in st["keys"]}
check("stored keys and claimed channels agree on the args attributes",
      {k for k in stored if k.startswith("Args:")} == {c for c in claimed if c.startswith("Args:")})
check("and there are two of them, not one",
      len({k for k in stored if k.startswith("Args:")}) == 2)

# ---------------------------------------------------------------------------
section("what a warning carries — the editor joins on identity, not on a number")

# The timeline stripes the ELEMENT and the effect tree marks the CALL, so a
# warning has to name both. Line numbers alone could not do it: `line` counts
# from zero because the code pane speaks LSP, every other line in the editor
# counts from one, and one line can hold several elements.
with contextlib.redirect_stderr(io.StringIO()):
    answer = execSource(
        "from videocode import *\n\ns = Square(side=1)\n"
        "s.moveBy(x=1, duration=1)\ns.moveBy(x=-1, duration=1)\n",
        "contention_test_fields.py",
    )
flaws = json.loads(answer["warnings"])
check("the run reports exactly one", len(flaws) == 1)
check("it names the element it is about", flaws[0]["input"] == 0)
check("it lands on the later of the two calls", flaws[0]["sourceLine"] == 5)
check("and the code pane's copy counts from zero",
      flaws[0]["line"] == flaws[0]["sourceLine"] - 1)

# ---------------------------------------------------------------------------
summary()
