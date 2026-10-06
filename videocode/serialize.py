#!/usr/bin/env python3

from __future__ import annotations

import contextlib
import io
import json
import math
import os
import sys


sys.path.append(".")


from videocode.context import *
from videocode import *
import videocode.constants as constants
from videocode import params


def _resetContext():
    Context.stack = {}
    Context.events = []
    Context.badValues = []
    Context.inputCounter = 0
    Context.lastEverAffectedFrame = 0
    Context.cursor = 0
    Context.waitOffset = 0
    Context.backgroundColor = None
    Context.origin = {}
    # The side table too. The editor runs a scene on every gesture, and
    # statements that outlive their run pile up in it — a hundred a frame for a
    # group — until an effect is attributed to a line that moved three edits ago.
    Context.statements = []

    # Et ce que S1 en a retenu : quel appel a écrit quoi, et ce que valait
    # chaque canal avant qu'un verbe n'y touche.
    Context.calls = {}
    Context.starts = {}

    # And the register of every input's metadata, with the counter that breaks
    # ties between equal z-indices.
    #
    # `Context.metas` is what `bringToFront()` and friends read to answer "what
    # is the highest layer in this scene". Left standing between runs it grew by
    # one entry per input per execution — the editor runs a scene on every
    # gesture — and, worse, it answered from scenes that no longer exist:
    # deleting the line that said `zIndex(50)` did not stop `maxZIndex()` from
    # replying 50, so the next `bringToFront()` jumped over a layer nobody could
    # see any more.
    Context.metas = []
    Context.zOrderCounter = 0

    # And the flag a Group raises while it emits toward its members — a run that
    # died mid-emission must not leave the next one marking everything derived.
    Context.deriving = False
    Context.derivingGroup = None

    # The three counters that live on classes rather than on Context, and were
    # forgotten here for exactly that reason. They are not cosmetic: a shader
    # that unions on an auto-assigned group id gets a DIFFERENT id on the second
    # bake of the same file, so the editor — one process, one bake per gesture —
    # renders the same scene two different ways, and every incremental reload
    # sees that input as changed. Measured on video.py: input 288 goes from
    # group -1 to group -2 with not a character of the scene touched.
    from videocode.input.interface.Group import Group as _Group
    from videocode.shader.fragmentShader.lightSweep import lightSweep as _lightSweep
    from videocode.shader.fragmentShader.glitch import glitch as _glitch
    from videocode.shader.fragmentShader.mathShader import mathShader as _mathShader

    _Group._serial = 0
    _lightSweep._nextGroup = 0
    _mathShader._nextGroup = 0
    # The fourth counter, and the only one that changes PIXELS rather than an
    # id: glitch derives its slice noise from the seed, so two bakes of one
    # unchanged scene rendered differently. The editor bakes on every gesture.
    _glitch._nextSeed = 0

    # And the scene's camera, which is a singleton for the same reason and
    # would otherwise start the next run wherever the last one left it.
    from videocode.input.Camera import camera as _camera

    _camera._reset()

    # And the parameters it asked for, which are checked against those it was
    # given once the run is over.
    params.startRun()


def _oneLine(hit: dict) -> str:
    """The gutter has one line, not a paragraph — the paragraph stays on stderr."""
    a, b = hit["a"], hit["b"]
    return (
        f"{b['call']}() and {a['call']}() (line {a['line']}) both write {hit['key']} over "
        f"{hit['frames']} shared frames — the later call wins them."
    )


def _reportContendedKeys() -> list[dict]:
    """
    Say it out loud when two statements write the same key over the same frames.

    Printed rather than raised: the strict rule would refuse to render a scene
    that renders today, and a scene being written is broken most of the time —
    the editor runs this on every keystroke. On the 52 scenes of the repository
    it says nothing at all, which is the point: it is silent until the ambiguity
    is real.
    """
    out: list[dict] = []
    for hit in Context.contendedKeys():
        a, b = hit["a"], hit["b"]
        origin = Context.origin.get(hit["input"])
        who = f"the {origin[2]} from {os.path.basename(origin[0])}:{origin[1]}" if origin else f"input {hit['input']}"
        print(
            f"[videocode] {os.path.basename(a['file'])}:{a['line']} {a['call']}() and "
            f"{os.path.basename(b['file'])}:{b['line']} {b['call']}() both write {hit['key']} on "
            f"{who}, over {hit['frames']} frames from frame {hit['from']}.\n"
            f"            Two claims on one channel cannot both hold, so the later call WINS the "
            f"frames they share — swapping the two lines gives a different video. Separate them "
            f"with flush() or a start=, or write the one thing you mean. (Different channels — x "
            f"against y, fillColor against strokeColor — compose, and are never reported here.)",
            file=sys.stderr,
        )
        # `line` is what the code pane needs (LSP counts from zero); `sourceLine`
        # and `input` are what the timeline and the effect tree need, so that the
        # bar and the row carrying the fault are found by identity rather than by
        # comparing numbers that count from different places.
        out.append({"line": b["line"] - 1, "sourceLine": b["line"], "input": hit["input"],
                    "file": b["file"], "message": _oneLine(hit), "rule": "contended-key"})
    return out

def _reportBadValues() -> list[dict]:
    """
    An argument a type refuses — `opacity(300)` on a uint8 — as a red line in
    the code and a hazard on the clip. Found by `Context._callSite()`, on the
    person's own frame, so an expression is judged by what it was worth.
    """
    return [{"line": b["line"] - 1, "sourceLine": b["line"], "input": b["input"],
             "file": b["file"], "message": b["message"], "severity": 1, "rule": "bad-value"}
            for b in Context.badValues]


def _reportLint(model: dict) -> list[dict]:
    """
    The mistakes no line refuses, read off the model the timeline is drawn from:

    - a Sound that starts on or after the last frame — the mix is cut at the
      film's end (AudioMix.cpp), and a Sound does not make the film longer;
    - a write before frame 0, which the renderer skips, or a Sound delayed by a
      negative time, which ffmpeg refuses;
    - an element on screen on no frame at all, by the renderer's own test;
    - one that first appears on the last frame: made after the final wait().

    One finding per call site, not per element: a Text is one line and many glyphs.
    """
    frames, fps = model["frames"], model["fps"]
    out: list[dict] = []

    def say(rule: str, severity: int, file: str, line: int, index: int, message: str) -> None:
        out.append({"line": line - 1, "sourceLine": line, "input": index, "file": file,
                    "message": message, "severity": severity, "rule": rule})

    # A line the bounds check already refused says so once.
    refused = {(b["file"], b["line"]) for b in Context.badValues}
    # ponytail: the film's length here ignores speed ramps, which the C++ follows (Core.cpp),
    # so the end rules stand down on a ramped Video rather than guess. An unreadable nb_frames
    # (mkv, webm) leaves the same gap: stand down on any Video if one shows up.
    ramped = any(entry[-1]["type"] == "Video" and entry[-1]["args"].get("speedRamps") for entry in Context.stack.values())
    early: dict[tuple[str, int, str], tuple[int, int]] = {}
    groups: dict[tuple[str, int], list[dict]] = {}
    for element in model["elements"]:
        made = Context.stack[element["index"]][-1]
        for effect in element["effects"]:
            at = (effect["file"], effect["line"], effect["call"])
            if effect["start"] < 0 and at[:2] not in refused and (at not in early or effect["start"] < early[at][0]):
                early[at] = (effect["start"], element["index"])
        if made["type"] == "Sound":
            delay = made["args"].get("delay", 0)
            where = (element["file"], element["line"], element["index"])
            if where[:2] in refused:
                continue
            # AudioMix.cpp rounds the same way before handing the delay to ffmpeg.
            if round(delay * 1000) < 0:
                say("before-start", 1, *where, f"Sound starts at {delay:.2f} s, before the film does — ffmpeg refuses "
                    f"a negative delay. Start it at 0 or later; trimStart= skips the head of the file.")
            elif not ramped and round(delay * fps) >= max(frames - 1, 1):
                say("sound-after-end", 1, *where, f"Sound starts at {delay:.2f} s but the film is {frames / fps:.2f} s "
                    f"long, so at most one frame of it is heard — a Sound does not make the film longer. "
                    f"Add a wait() after it.")
        elif made["type"] != "Camera" and element["line"] > 0:
            groups.setdefault((element["file"], element["line"]), []).append(element)

    for (file, line, call), (start, index) in early.items():
        say("before-start", 1, file, line, index, f"{call}() starts at frame {start}, before the film's first frame — "
            f"the renderer skips every frame below 0, so that part never plays.")
    for (file, line), group in groups.items():
        name = group[0]["kind"] + (f" ({len(group)} elements)" if len(group) > 1 else "")
        seen = [element for element in group if element["seen"]]
        if not seen:
            say("never-visible", 2, file, line, group[0]["index"],
                f"{name} is never on screen — hidden or at opacity 0 on every frame.")
        # The signature of an element made after the last wait(): its placement
        # shows it on the frame that the making itself added to the film.
        elif not ramped and frames > 1 and all(element["first"] == frames - 1 for element in seen):
            say("last-frame-only", 2, file, line, seen[0]["index"],
                f"{name} first appears on the film's last frame ({frames - 1}), so it is on screen for one "
                f"frame — add a wait() after it.")
    return out


# Title safe is the inner 80 % of the frame: 10 % kept clear on each side. The
# preview draws the same rectangle (PreviewPanel.qml) — the two must agree, or
# the lint warns about a title the overlay shows inside.
_TITLE_SAFE = 0.8


def _textKinds() -> set[str]:
    """`Text` and every class built on it, by the name `Context.origin` records."""
    from videocode.input.shape.text.Text import Text

    kinds: set[str] = set()
    todo: list[type] = [Text]
    while todo:
        cls = todo.pop()
        kinds.add(cls.__name__)
        todo += cls.__subclasses__()
    return kinds


def _glyphBoxes(entry: dict, total: int):
    """
    Where one glyph is drawn, in pixels (y down), span by span: yields
    `(first, last, box, seen)` for each run of frames its state holds still.

    The renderer's own arithmetic, redone from the stack it reads: the state a
    key sets is carried until another key changes it (Core.cpp), the box is
    the control points' bounding box (BezierPath.cpp), and it is placed by
    `getTransformationMatrixFromMetadata` — the align point lands on the
    position, scaled and turned about it. Frames below 0 are skipped, as the
    renderer skips them.
    """
    made = entry[-1]["args"]
    points = made.get("points") or []
    x, y = SW / 2, SH / 2
    ax, ay, sx, sy, turn = 0.5, 0.5, 1.0, 1.0, 0.0
    opacity, hidden = 255.0, False
    keyed = sorted({0, *(f for f in entry if f != -1 and 0 <= f < total)})
    for at, frame in enumerate(keyed):
        for key, shader in entry.get(frame, {}).items():
            args = shader.get("args", {})
            kind = key.split(":")[0]
            if kind == "Position":
                x = x if args.get("x") is None else SW / 2 + args["x"] * WORLD_TO_SCREEN_RATIO
                y = y if args.get("y") is None else SH / 2 - args["y"] * WORLD_TO_SCREEN_RATIO
            elif kind == "Translate":
                x, y = x + args["x"] * WORLD_TO_SCREEN_RATIO, y - args["y"] * WORLD_TO_SCREEN_RATIO
            elif kind == "Align":
                ax = ax if args.get("x") is None else args["x"]
                ay = ay if args.get("y") is None else args["y"]
            elif kind == "Scale":
                sx, sy = args["x"], args["y"]
            elif kind == "Rotation":
                turn = args["degree"]
            elif kind == "Opacity":
                opacity = args["opacity"]
            elif kind == "Hide":
                hidden = True
            elif kind == "Show":
                hidden = False
            elif key == "Args:points":
                points = args.get("value") or []
        if not points:
            continue
        w = (max(p[0] for p in points) - min(p[0] for p in points)) * WORLD_TO_SCREEN_RATIO
        h = (max(p[1] for p in points) - min(p[1] for p in points)) * WORLD_TO_SCREEN_RATIO
        px, py = w * ax, h * (1 - ay)
        c, s = math.cos(math.radians(turn)), math.sin(math.radians(turn))
        corners = []
        for cx, cy in ((0, 0), (w, 0), (0, h), (w, h)):
            dx, dy = (cx - px) * sx, (cy - py) * sy
            corners.append((x + c * dx - s * dy, y + s * dx + c * dy))
        box = (min(p[0] for p in corners), min(p[1] for p in corners),
               max(p[0] for p in corners), max(p[1] for p in corners))
        last = keyed[at + 1] - 1 if at + 1 < len(keyed) else total - 1
        yield frame, last, box, not hidden and opacity != 0


def _reportTitleSafe(model: dict, shape: str) -> list[dict]:
    """
    A `Text` that stays outside title safe — the inner 80 % of the frame — on a
    frame where it is on screen: cut by a TV's overscan, under a phone app's
    buttons. A warning, never an error: an edge can be the design.

    "Stays", because a title sliding in from off-screen crosses the margin on
    purpose: a frame counts when the glyph holds that box into the next frame,
    or it is the film's last. A glyph wholly off the frame is not this rule's
    business either — it is being kept there. One finding per call site, at
    the first frame it happens, naming the shape it was checked in.
    """
    frames, fps = model["frames"], model["fps"]
    kinds = _textKinds()
    left, top = SW * (1 - _TITLE_SAFE) / 2, SH * (1 - _TITLE_SAFE) / 2
    right, bottom = SW - left, SH - top
    # ponytail: a moving camera moves everything not pinned to the frame, and
    # its transform is not redone here; the rule stands down for those rather
    # than guess. A composition member is drawn into its layer's space: same.
    filmed = any(entry[-1]["type"] == "Camera" for entry in Context.stack.values())
    worst: dict[tuple[str, int], tuple[int, str, float, int]] = {}
    for element in model["elements"]:
        entry = Context.stack[element["index"]]
        if element["kind"] not in kinds or entry[-1]["args"].get("open"):
            continue
        keys = {key for frame, shaders in entry.items() if frame != -1 for key in shaders}
        if "CompositionMember" in keys or (filmed and "PinToFrame" not in keys):
            continue
        spans = list(_glyphBoxes(entry, frames))
        for at, (first, last, box, seen) in enumerate(spans):
            if not seen:
                continue
            following = spans[at + 1][2] if at + 1 < len(spans) else box
            rests = last > first or last == frames - 1 or all(abs(a - b) < 1e-6 for a, b in zip(box, following))
            onFrame = box[0] < SW and box[2] > 0 and box[1] < SH and box[3] > 0
            if not rests or not onFrame:
                continue
            # How far inside the margin each side reaches, in pixels; half a
            # pixel of slack for the arithmetic, which is float on both sides.
            past = {"left": left - box[0], "right": box[2] - right, "top": top - box[1], "bottom": box[3] - bottom}
            edge = max(past, key=lambda side: past[side])
            if past[edge] <= 0.5:
                continue
            where = (element["file"], element["line"])
            if where not in worst or first < worst[where][0]:
                worst[where] = (first, edge, past[edge], element["index"])
            break

    out: list[dict] = []
    for (file, line), (first, edge, depth, index) in worst.items():
        keep = round(left if edge in ("left", "right") else top)
        gap = round(keep - depth)
        reach = f"comes within {gap} px of the {edge} edge" if gap >= 0 else f"runs {-gap} px past the {edge} edge"
        out.append({"line": line - 1, "sourceLine": line, "input": index, "file": file, "severity": 2, "rule": "title-safe",
                    "message": f"Text leaves title safe in the {shape} frame from frame {first} ({first / fps:.2f} s): it "
                               f"{reach}, and title safe keeps {keep} px clear there — a TV may crop it, a phone app "
                               f"may cover it."})
    return out

def _applyBackground(scope: dict) -> None:
    """
    Resolve the scene's optional script-global `BG` — the scene's
    background, COLOR-ONLY (any `rgba`, gradients included — never an
    `Input`: animated backgrounds stay explicit, e.g. `Plane().drift()` at
    the end of the script):

        BG = WHITE                        # anywhere in the script
        BG = LinearGradient(RED, BLUE)

    - A plain `rgba` becomes the renderer's clear color
      (`Context.backgroundColor`, read by C++ like lastEverAffectedFrame) —
      zero extra draw cost. Alpha is ignored (transparent backgrounds come
      from `--generate out.mov/.webm` instead).
    - A gradient can't be a clear value (a Vulkan clear is one RGBA
      constant), so it becomes one static full-frame background `Rectangle`
      — visible from frame 0 (`noHiding`) and layered behind everything
      (`background(offset=0)`, exactly like `Plane`'s own backdrop).
    """
    bg = scope.get("BG")
    if bg is None:
        return

    if isinstance(bg, (LinearGradient, RadialGradient, ConicGradient)):
        with Context.noHiding():
            Rectangle(
                width=WORLD_WIDTH, height=WORLD_HEIGHT, fillColor=bg, strokeColor=TRANSPARENT
            ).background(offset=0)
    elif isinstance(bg, rgba):
        Context.backgroundColor = (bg.r / 255, bg.g / 255, bg.b / 255)
    else:
        raise TypeError(f"BG must be an rgba color or a gradient, got {type(bg).__name__}")



def _besideScene(filepath: str) -> None:
    """
    Put the scene's own folder on `sys.path`, so `from card import card` finds
    the helper written beside it wherever the engine was started from. The
    examples used to spell their folder into `sys.path` themselves, relative
    to the repository root, and broke as soon as they were copied anywhere
    else.

    Last, not first — unlike `python scene.py`. First, a scene called
    `chess.py` shadowed the `chess` package it imports, and the whole visual
    corpus fell over on the one scene named after a library.
    """
    import os

    folder = os.path.dirname(os.path.abspath(filepath))
    if folder and folder not in sys.path:
        sys.path.append(folder)

def _sceneScope(_=None) -> dict:
    """Un décor neuf pour une exécution : ce que les deux entrées se donnaient déjà."""
    scope = dict(globals())
    scope["__name__"] = "Scene"
    return scope


def _runOnce(code, scope) -> None:
    exec(code, scope)


def _pileup() -> str:
    """L'empreinte de la pile, pour dire si une passe de plus change encore le film."""
    return repr(sorted((index, sorted(entry.items())) for index, entry in Context.stack.items()))


def _runUntilStable(code, scope, fresh, limit: int = 8) -> Any:
    """
    Exécuter la scène, et la rejouer tant que sa base bouge encore.

    La première passe donne la vérité image par image. Si une ligne ouvre
    derrière une ligne déjà écrite — ce que `backdatedWrites()` sait dire — sa
    base a été lue sur un curseur déjà emporté plus loin, et une passe de plus
    rejoue la scène en donnant à chaque animation la valeur qu'elle a vraiment
    à l'image où elle s'ouvre.

    Une seule reprise ne suffit pas pour une CHAÎNE écrite à l'envers : le
    deuxième maillon lit sa base dans une passe où le troisième était lui-même
    mal basé, et chaque passe n'en corrige donc qu'un. On rejoue jusqu'à ce que
    la pile ne bouge plus ; `limit` est là pour qu'une scène pathologique
    s'arrête au lieu de tourner.

    Aucune des 50 scènes du corpus ne déclenche la moindre reprise : la barrière
    de l'empreinte prouve elle-même que rien ne bouge. C'est ce qui permet de
    livrer S1 sans drapeau.

    `fresh` refait un décor vierge — une reprise doit repartir de zéro, pas
    s'ajouter à la précédente.
    """
    _runOnce(code, scope)
    if not Context.backdatedWrites():
        return scope

    before = _pileup()
    for _ in range(limit):
        told = Context.baseline()
        scope = fresh()
        Context.replaying = told
        try:
            _runOnce(code, scope)
        finally:
            Context.replaying = None
        after = _pileup()
        if after == before:
            break
        before = after
    return scope


def execScene(filepath: str) -> None:
    """
    Execute the scene file and populate Context.stack.
    C++ reads the stack directly via pybind11 — no JSON serialization.
    """
    _resetContext()

    with open(filepath, "r") as file:
        content = file.read()

    _besideScene(filepath)
    code = compile(content, filepath, "exec")

    # A FRESH namespace per run, seeded from this module's own.
    #
    # The scene used to execute into `globals()` — this module's dict — so every
    # name it bound survived into the next run, along with anything a helper
    # mutated. Delete a line, run again, and the name it defined was still
    # there: the editor showed a scene that `--generate` (a fresh process) would
    # not produce, and the drift grew with the session. Measured cost of the
    # fresh dict: none — 2.5 vs 2.6 ms on scene.py, 12.4 vs 12.7 on eg.py, 231.8
    # vs 230.0 on the stress scene, all inside run-to-run noise.
    #
    # Seeded from this module rather than empty because a scene is written
    # against what `videocode/serialize.py` has already imported; `__name__` is
    # "Scene" so a script guarded by `if __name__ == "__main__"` behaves the way
    # it did.
    scope = dict(globals())
    scope["__name__"] = "Scene"

    import os

    if os.environ.get("VC_PROFILE"):
        import cProfile, pstats, io

        pr = cProfile.Profile()
        pr.enable()
        exec(code, scope)
        pr.disable()
        s = io.StringIO()
        ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
        ps.print_stats(30)
        print("[profile] Top 30 cumulative:\n" + s.getvalue(), flush=True)
    else:
        scope = _runUntilStable(code, scope, lambda: _sceneScope(_resetContext()))

    params.checkRun()
    _applyBackground(scope)
    _reportContendedKeys()


def sceneModel() -> dict:
    """
    What the last run made, in the terms a timeline needs.

    The stack is baked PER FRAME — `moveBy` is a `Position` shader on every frame
    it covers — so an "effect" here is a contiguous run of frames sharing one
    shader key. That is not a summary: it is the same data the renderer reads,
    read the other way round.

    Nothing is invented. An element's label and line come from `Context.origin`
    (the call site), its kind from the class that made it, and its span from the
    frames it actually has entries on, extended to the end of the scene because
    an input that exists keeps existing until the scene ends.
    """
    # The cursor IS the count.
    #
    # `lastEverAffectedFrame` is exclusive: `__end = start + duration`, so it
    # points at the frame after the last one carrying anything. Adding one
    # counted it twice, and the timeline drew a scene one frame longer than the
    # video the renderer writes — 2.733 s of editor for a 2.700 s file.
    #
    # The floor is the scene that animates nothing: everything lands on frame 0
    # with no duration, the cursor never leaves 0, and the one frame there is to
    # see still has to be counted. Without it a static scene renders an empty
    # file, which is what the C++ side did.
    total = max(Context.lastEverAffectedFrame, 1)
    elements = []

    for index in sorted(Context.stack):
        entry = Context.stack[index]
        frames = sorted(f for f in entry if f != -1)

        # One run per shader key: walk the frames it appears on and cut wherever
        # the sequence breaks.
        runs: dict[str, list[list[int]]] = {}
        for frame in frames:
            for key in entry[frame]:
                spans = runs.setdefault(key, [])
                if spans and spans[-1][1] == frame - 1:
                    spans[-1][1] = frame
                else:
                    spans.append([frame, frame])

        # ── One row per STATEMENT ─────────────────────────────────────────
        # A row is a CALL, not a shader run.
        #
        # It used to be the other way round: runs of consecutive frames were
        # found on the stack and then attributed back to whichever statement
        # overlapped them most. That answered a different question — "what
        # changed, and who is to blame" — and it got the two most visible things
        # wrong.
        #
        # It started late. A rotation has not turned by anything on its first
        # frame, so no shader is written there, and `rotateBy(180, duration=1.2)`
        # was drawn beginning one frame after the `scaleTo(0.5, duration=1.2)`
        # written to happen with it. Two calls of the same length, on the same
        # line, starting at different times: a display saying something the
        # scene does not.
        #
        # And it could not tell a call's own length from its side effects: a
        # group re-emits position for as long as ANYTHING in it moves, so
        # `scaleTo` looked as long as the group's whole activity.
        #
        # Each `apply()` now records the frames it COVERS — before no-op shaders
        # are dropped — so the frames a call is answerable for are known without
        # looking at what survived. A group emits per frame, which is why the
        # window is the union of every statement sharing a line and a call.
        windows: dict[tuple[int, str], dict] = {}
        for statement in Context.statements:
            if statement["input"] != index or statement["line"] <= 0:
                continue
            if not statement["keys"]:
                continue
            # The hiding an element gets until a wait lets it appear is written
            # by the library, not by the line that made it.
            if statement.get("placement"):
                continue

            first = min(span[0] for span in statement["keys"].values())
            # Exclusive on the stack, inclusive here: `__end = start + duration`
            # points at the frame after the last one carrying anything.
            last = max(span[1] for span in statement["keys"].values()) - 1
            if last < first:
                last = first

            at = (statement["line"], statement["call"])
            held = windows.get(at)
            if held is None:
                windows[at] = {
                    "name": statement["call"],
                    "call": statement["call"],
                    "line": statement["line"],
                    # Which file that line is in. An element imported from
                    # another module is animated by lines the open document
                    # does not have, and a gesture that wrote them by number
                    # would land on whatever the scene happens to say there.
                    "file": statement["file"],
                    "start": first,
                    "end": last,
                    "kinds": sorted(statement["keys"]),
                }
                continue

            held["start"] = min(held["start"], first)
            held["end"] = max(held["end"], last)
            held["kinds"] = sorted(set(held["kinds"]) | set(statement["keys"]))

        effects = sorted(windows.values(), key=lambda e: (e["start"], e["name"]))

        # ── Where a new statement about this element could go ─────────────
        # The lines that already say something about it, in the order they ran,
        # each with the cursor left standing after it. To write `hide` at a
        # chosen moment the editor puts it after the last of these whose cursor
        # is not already past that moment, and counts `start` from there.
        # Consecutive entries on one line are one point: a group re-emits its
        # members every frame, which is a hundred statements from one line.
        points: list[dict[str, Any]] = []
        for statement in Context.statements:
            if statement["input"] != index or statement["line"] <= 0:
                continue
            if points and points[-1]["line"] == statement["line"]:
                points[-1]["call"] = statement["call"]
                points[-1]["cursor"] = statement["cursor"]
                continue
            points.append({
                "line": statement["line"],
                "call": statement["call"],
                "cursor": statement["cursor"],
                "file": statement["file"],
            })

        # ── When it is actually on screen ─────────────────────────────────
        # NOT "the frames it has entries on". A typewriter writes
        # `opacity(0)` at frame 0 for every letter before ramping each one in,
        # so by key presence all eight glyphs start together and the stagger —
        # the whole point of the gesture — disappears. Visibility lives in the
        # VALUE, and the predicate is the renderer's own: not hidden, and
        # opacity not zero (src/core/Core.cpp).
        # A state, not a set of frames. What a key says holds until another key
        # says otherwise: a square that fades in at frame 1 and is hidden at
        # frame 45 is on screen for all of 1…44, and it has entries on none of
        # them. Counting only the frames carrying keys ended the clip at 11,
        # where the fade stopped writing.
        opacity = 255.0
        hidden = False
        firstSeen = -1
        lastSeen = total - 1
        wasVisible = False
        # Frame 0 is walked even with no key on it: an element made with nothing
        # applied is on screen from the start (one made later is hidden there by
        # its placement). Without it a music track began at its first fade.
        # Frames below 0 are skipped, as the renderer skips them (Core.cpp).
        for frame in sorted({0, *(f for f in frames if f >= 0)}):
            for key, shader in entry.get(frame, {}).items():
                args = shader.get("args", {})
                if "opacity" in args:
                    opacity = args["opacity"]
                # `hide()` carries no arguments — the KEY is the whole
                # statement, the way the renderer reads it. Asking for a
                # `hidden` value left every hidden element on the timeline until
                # the end of the scene, which is exactly the length nobody
                # wanted to see.
                if key == "Hide":
                    hidden = True
                elif key == "Show":
                    hidden = False
            nowVisible = not hidden and opacity != 0
            if nowVisible and firstSeen < 0:
                firstSeen = frame
            if wasVisible and not nowVisible:
                lastSeen = frame - 1
            elif nowVisible and not wasVisible:
                # On again — and on until something turns it off, which is what
                # the scene ending is.
                lastSeen = total - 1
            wasVisible = nowVisible

        # Never on screen at all: drawn where its keys are, rather than not at
        # all, because a clip you cannot see is still a clip you have to find.
        seen = firstSeen >= 0
        if firstSeen < 0:
            firstSeen = frames[0] if frames else 0

        file, line, cls = Context.origin.get(index, ("", 0, ""))
        elements.append(
            {
                "index": index,
                "kind": cls or entry[-1]["type"],
                "file": file,
                "line": line,
                "first": firstSeen,
                "last": lastSeen,
                "seen": seen,
                "effects": effects,
                "points": points,
            }
        )

    # ── Where the scene's time joins ──────────────────────────────────────
    # A `wait()` is the one place the language lets time propagate: everything
    # before it has ended, everything after starts from there. The editor draws
    # them across the tracks, because "will this push what follows?" is answered
    # by whether there is one — not by a rule the timeline invented.
    waits = [
        {"start": event.start, "frames": event.n, "line": event.line}
        for event in Context.events
        if isinstance(event, Wait)
    ]

    # A `timestamp()` is a moment the author named on purpose. Kept as the frame
    # it was written at: the preview already jumps between them, and the ruler
    # is where the name is read.
    markers = [
        {"name": event.name, "frame": event.time, "file": event.file, "line": event.line}
        for event in Context.events
        if isinstance(event, Timestamp)
    ]

    return {"fps": FRAMERATE, "frames": total, "elements": elements, "waits": waits, "markers": markers}


def effectCatalogue(root: str | None = None) -> list[dict]:
    """
    Every effect a scene can apply, by name, discovered rather than listed.

    A hand-written list is a list that is wrong the day someone adds a file —
    and the editor offering an effect the library does not have would be the
    worst kind of lie, since it writes it into your scene.

    The project's own presets come after the library's: a public function in
    `<root>/templates/*.py` — `def myPop(): return popIn(scale=0.3)` — is an
    effect like any other, applied with `.apply(myPop())`.
    """
    import importlib
    import inspect
    import pkgutil

    import videocode.template.effect as effects

    from videocode.input.input import Input

    found: dict[str, str] = {}
    signatures: dict[str, list[dict]] = {}
    forms: dict[str, str] = {}
    for module in pkgutil.walk_packages(effects.__path__, effects.__name__ + "."):
        try:
            loaded = importlib.import_module(module.name)
        except Exception:
            continue
        for name, value in vars(loaded).items():
            if inspect.isfunction(value) and value.__module__ == module.name and not name.startswith("_"):
                if name not in found:
                    found[name] = module.name
                    forms[name], signatures[name] = _effectForm(name, value, Input)

    for where, loaded, _ in _projectTemplates(root):
        if loaded is None:
            continue
        for name, value in vars(loaded).items():
            if inspect.isfunction(value) and value.__module__ == where and not name.startswith("_"):
                if name not in found:
                    found[name] = where
                    forms[name], signatures[name] = _effectForm(name, value, Input)

    # The module comes back with the name because effects are NOT part of
    # `from videocode import *` — `flash` lives in
    # videocode.template.effect.other.flash and has to be imported by name. An
    # editor that writes `flash()` without the import writes a scene that does
    # not run, which is a worse gift than no button at all.
    #
    # The parameters come with it for the same reason one step further on: an
    # editor that offers a field the effect does not take, or misses the one it
    # is really about, writes a call that fails. They are READ off the signature,
    # never listed here — a list beside the code is a list that is wrong the
    # first time a default changes.
    return [
        {
            "name": name,
            "module": where,
            "form": forms.get(name, "effect"),
            "params": signatures.get(name, []),
        }
        for name, where in sorted(found.items())
    ]


def _effectForm(name: str, fn, inputClass) -> tuple[str, list[dict]]:
    """
    How this effect is WRITTEN, and the fields that go with it.

    Two families live in `template/effect`, and they are not called the same way:

    - the core transformations — `moveBy`, `scaleTo`, `rotateTo` — are generator
      functions taking the target as their first argument, and `Input` wraps each
      one in a method. What a person writes is `square.scaleTo(x=2)`, so that is
      what the editor writes, with the METHOD's own fields (`factor`, not the
      internal `input`).
    - everything else is a factory returning an effect, applied with
      `square.apply(flash())`.

    Told apart by the signature rather than by a list of names: a new core
    transformation lands in the right family the day it is written.
    """
    import inspect

    if inspect.isgeneratorfunction(fn):
        method = getattr(inputClass, name, None)
        if method is not None and inspect.isfunction(method):
            # `self` is the element; the editor knows which one.
            return "method", [p for p in _effectParameters(method) if p["name"] != "self"]
        # No method to hide behind: the element is passed by hand, which is what
        # `Input` itself does with the star — the function yields shaders.
        return "generator", [p for p in _effectParameters(fn) if p["name"] != "input"]

    return "effect", _effectParameters(fn)


def templateCatalogue(root: str | None = None) -> list[dict]:
    """
    Everything a scene can be given, by name: shapes, media, the composite
    templates the library builds out of them — and the project's own, from
    `<root>/templates/*.py`, in a group of their own so the panel can tell what
    shipped from what you wrote.

    Discovered, like the effects, and for the same reason — a hand-written list
    is wrong the day someone adds a file. The rule for what belongs here is the
    one the language already draws: an `Input` subclass reachable by name from
    `from videocode import *` is something a person could have typed, and
    nothing else is offered.

    The group is read from where the class lives — a shape, a piece of media, or
    a template assembled from them — because that is the only division a person
    browsing them cares about, and it is already true in the tree.
    """
    import importlib
    import inspect
    import pkgutil

    import videocode

    import videocode.template.input as templates

    from videocode.input.input import Input

    groups = {
        "videocode.input.shape": "shape",
        "videocode.input.media": "media",
        "videocode.input.interface": "interface",
    }

    def described(value) -> str:
        # The first line of the docstring, when there is one. Never a
        # description written here: what the class says about itself is what the
        # person reading the code will see, and two of them would drift apart.
        # Its OWN docstring, never an inherited one: `inspect.getdoc` walks up
        # to the base class, so eleven different shapes all introduced
        # themselves as "An `Input` is a source that you want to add to the
        # timeline of the video" — a sentence that tells you nothing about which
        # one to pick. A class that says nothing about itself says nothing here.
        told = value.__dict__.get("__doc__") or ""
        return told.strip().split("\n")[0][:120]

    def parameters(value) -> list[dict]:
        try:
            return [p for p in _effectParameters(value.__init__) if p["name"] != "self"]
        except (TypeError, ValueError):
            return []

    def required(value) -> list[str]:
        # What has no default. `Shadow(shape=…)` is about another input and
        # cannot be conjured on its own; `Video(filepath=…)` needs a file. The
        # editor asks before it writes rather than writing a call that raises.
        return [p["name"] for p in parameters(value) if not p["optional"]]

    found: list[dict] = []
    seen: set[str] = set()

    # What `from videocode import *` already gives a scene: no import to write.
    for name, value in vars(videocode).items():
        if name.startswith("_") or not inspect.isclass(value):
            continue
        if not issubclass(value, Input) or value is Input or inspect.isabstract(value):
            continue

        where = getattr(value, "__module__", "")
        group = next((tag for prefix, tag in groups.items() if where.startswith(prefix)), "")
        if not group:
            continue

        seen.add(name)
        found.append({
            "name": name, "group": group, "module": "",
            "says": described(value), "params": parameters(value),
            "required": required(value), "broken": False,
        })

    # And the composite ones, which are NOT in the star import — `Arrow` lives
    # in videocode.template.input.Arrow, so the module travels with the name the
    # way it does for effects: a button that writes a call without its import
    # writes a scene that does not run.
    def classesIn(where: str, loaded, group: str) -> None:
        for name, value in vars(loaded).items():
            if name.startswith("_") or name in seen or not inspect.isclass(value):
                continue
            if value.__module__ != where:
                continue
            if not issubclass(value, Input) or inspect.isabstract(value):
                continue

            seen.add(name)
            found.append({
                "name": name, "group": group, "module": where,
                "says": described(value), "params": parameters(value),
                "required": required(value), "broken": False,
            })

    for module in pkgutil.walk_packages(templates.__path__, templates.__name__ + "."):
        try:
            loaded = importlib.import_module(module.name)
        except Exception:
            continue
        classesIn(module.name, loaded, "template")

    # A file of yours that cannot be used gets a row of its own saying why. Left
    # out, it is indistinguishable from one you have not written yet — and the
    # place you look for it is the panel, not the terminal the editor was
    # launched from.
    for where, loaded, trouble in _projectTemplates(root):
        if loaded is not None:
            classesIn(where, loaded, "yours")
        if trouble:
            found.append({
                "name": where.split(".")[-1] + ".py", "group": "yours", "module": "",
                "says": trouble, "params": [], "required": [], "broken": True,
            })

    found.sort(key=lambda t: (t["group"], t["name"]))
    return found


def _projectTemplates(root: str | None) -> list[tuple[str, object | None, str]]:
    """
    The project's own pack: every `<root>/templates/*.py`, loaded, with the name
    the editor will write for it — and, when there is one, what is wrong with it.

    Named `templates.<file>` rather than by path because that is the import the
    scene resolves — the project root is `sys.path[0]` (Main.cpp puts it there),
    and a folder on the path is a package without an `__init__.py`. `root`
    defaults to the working directory for the same reason: it IS the project
    root the editor reports, so the panel and the scene agree on what
    `templates.LowerThird` means. Loaded by path here, not through the import
    system, so a test can point at any folder without touching `sys.path`.

    A file that does not import is said rather than raised: one broken template
    must not take the whole panel down with the others. Said, and not merely
    dropped — a file that vanishes without a word is one you go looking for in
    the folder, sure you wrote it. The complaint travels back with the module so
    the panel can show it where you were expecting the template; it is printed
    here as well, for the runs that have no panel.
    """
    import importlib.util
    import inspect
    import os

    from videocode.input.input import Input

    def offersSomething(where: str, loaded) -> bool:
        # What either catalogue could take from it: an `Input` to place, or a
        # public function to apply. Anything else is a file the panel will never
        # show, which is worth saying out loud — but `templates/presets.py`,
        # which is only effects, is NOT that, and must never be flagged.
        for name, value in vars(loaded).items():
            if name.startswith("_") or getattr(value, "__module__", "") != where:
                continue
            if inspect.isfunction(value):
                return True
            if inspect.isclass(value) and issubclass(value, Input) and not inspect.isabstract(value):
                return True
        return False

    folder = os.path.join(root or os.getcwd(), "templates")
    if not os.path.isdir(folder):
        return []

    out: list[tuple[str, object | None, str]] = []
    for entry in sorted(os.listdir(folder)):
        if not entry.endswith(".py") or entry.startswith("_"):
            continue
        where = "templates." + entry[:-3]
        spec = importlib.util.spec_from_file_location(where, os.path.join(folder, entry))
        if spec is None or spec.loader is None:
            continue
        loaded = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(loaded)
        except Exception as error:
            trouble = f"{type(error).__name__}: {error}"
            print(f"templates/{entry} is not listed: {trouble}", file=sys.stderr)
            out.append((where, None, trouble))
            continue
        trouble = "" if offersSomething(where, loaded) else "no Input subclass and no effect in it"
        if trouble:
            print(f"templates/{entry} is not listed: {trouble}", file=sys.stderr)
        out.append((where, loaded, trouble))
    return out


def inputSignature(className: str) -> list[dict]:
    """
    What the call that makes an input takes, so the editor can offer its fields.

    Same rule as the effect catalogue: read off the class, never listed here. A
    `Video` answers with `cuts`, `startFrame`, `endFrame`, `speedRamps`… — which
    is how "trim this clip" becomes "write `endFrame`" without the editor
    knowing anything about video in particular.

    The class is found by name among the inputs the scene language exposes, so
    what the editor can edit is exactly what a person could have typed.
    """
    import inspect

    import videocode

    # `Video.position` answers for the setter: a value set on the element's line
    # is typed by the same signature a person calls to set it.
    className, _, method = className.partition(".")
    target = getattr(videocode, className, None)
    if target is None or not inspect.isclass(target):
        return []

    try:
        fn = getattr(target, method) if method else target.__init__
        return [p for p in _effectParameters(fn) if p["name"] != "self"]
    except (AttributeError, TypeError, ValueError):
        return []


def parameterSlot(owner: str, call: str, name: str) -> int:
    """
    Where `name` stands when a call passes it without its name, or -1.

    `Text("Merci")` and `rotateBy(180)` say `text` and `degree` by position,
    and an edit addressed by name has to find them there. Not `inputSignature`'s
    order: that one leaves out `start` and the `_` parameters, which still take
    a slot. -1 for a name that can only be given by keyword, and for a call
    this cannot find.

    `call` is a class (`Text`), a method of `owner` (`rotateBy` on `Circle`),
    or a function the scene language exposes (`wait`).
    """
    import inspect

    import videocode

    target = getattr(videocode, owner, None) if owner else None
    fn = getattr(target, call, None) if inspect.isclass(target) else None
    if fn is None:
        fn = getattr(videocode, call, None)
        if inspect.isclass(fn):
            fn = fn.__init__
    if not callable(fn):
        return -1

    try:
        parameters = list(inspect.signature(fn).parameters.values())
    except (TypeError, ValueError):
        return -1

    slot = 0
    for parameter in parameters:
        if parameter.kind not in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD):
            return -1
        if parameter.name == "self":
            continue
        if parameter.name == name:
            return slot
        slot += 1
    return -1


def enumValues(name: str) -> list[str]:
    """
    What an argument of this type accepts, spelled the way a scene writes it.

    The editor shows a field with a name and a value and no way to know what a
    value may BE. For anything the library states as an enum — `UVMapping`,
    `Align` — the answer is a closed list, and a closed list is a thing to pick
    from rather than to remember. Anything else answers nothing, and the field
    stays what it was: a place to type.
    """
    import enum

    import videocode

    target = getattr(videocode, name, None)
    if isinstance(target, type) and issubclass(target, enum.Enum):
        return [f"{name}.{member.name}" for member in target]
    return []


def _namedEasing(value) -> str:
    """
    What a default is CALLED, when the library gives it a name.

    `Easing.Out` for the curve behind it, `BLUE_C` for the colour: the editor
    shows and writes what a person would have typed, and an object's own repr is
    an address nobody can paste into a call. Found by identity in the namespaces
    that name them, so a new easing or a new colour needs no entry here.

    An empty string for anything else, which reads as "no default to show".
    """
    import videocode.constants as constants

    from videocode.utils.bezier import Easing

    if value is None:
        return "None"

    for name, candidate in vars(Easing).items():
        if not name.startswith("_") and candidate is value:
            return f"Easing.{name}"

    # Colours by VALUE, not by identity: a signature's `fillColor=rgba(77, 111,
    # 71, 255)` is the same green as `GREEN_E` without being the same object,
    # and the name is what a person would have typed.
    from videocode.color import rgba

    if isinstance(value, rgba):
        for name, candidate in vars(constants).items():
            if name.isupper() and isinstance(candidate, rgba) and candidate == value:
                return name

    for name, candidate in vars(constants).items():
        if not name.startswith("_") and candidate is value and name.isupper():
            return name
    return ""


def _effectParameters(fn) -> list[dict]:
    """
    An effect's keyword arguments, as the editor needs them: a name, the default
    written the way Python would write it, and enough of a kind to pick a field.

    `start` is left out on purpose. It is the one argument the editor does not
    ask for — you say when an effect happens by dropping it on the element, not
    by typing a number.
    """
    import inspect
    from enum import Enum

    out: list[dict] = []
    try:
        signature = inspect.signature(fn)
    except (TypeError, ValueError):
        return out

    for name, parameter in signature.parameters.items():
        if name.startswith("_") or name == "start":
            continue
        if parameter.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue

        default = parameter.default
        if default is inspect.Parameter.empty:
            written = ""
        elif isinstance(default, bool):
            written = "True" if default else "False"
        elif isinstance(default, (int, float)):
            written = repr(default)
        elif isinstance(default, Enum):
            # A StrEnum IS a str, so this has to come first: `repr()` on one
            # gives `<UVMapping.STRETCH: 'stretch'>`, which is the member, its
            # value and its address all at once. `UVMapping.STRETCH` is what a
            # person writes, and what the field can hand back to the line.
            written = f"{type(default).__name__}.{default.name}"
        elif isinstance(default, str):
            written = repr(default)
        elif isinstance(default, (list, tuple, dict)):
            # Un défaut vide se lit comme un défaut, pas comme un trou : `cuts`
            # sans rien dessous laissait croire à un argument obligatoire. `[]`
            # est ce que la signature dit, et ce qu'on retaperait.
            written = repr(default)
        else:
            # An easing is written in a scene as `Easing.Out`, and that spelling
            # is what has to come back: the object's own repr is an address, which
            # nobody can paste into a call. Found by identity in the namespace
            # that names them, so a new easing needs no entry anywhere here.
            written = _namedEasing(default)

        annotation = parameter.annotation
        kind = annotation if isinstance(annotation, str) else getattr(annotation, "__name__", "")

        # Whether the call can be made without it. NOT "the default came back
        # empty": a colour the library does not name has no spelling to show and
        # is still optional, and treating it as required made `Square` look like
        # something you cannot place without answering two questions.
        out.append({
            "name": name,
            "default": written,
            "kind": kind,
            "optional": parameter.default is not inspect.Parameter.empty,
        })

    return out


def execSource(source: str, filepath: str) -> dict:
    """
    Execute a scene held in MEMORY, and report what it made.

    The editor's buffer is the scene; it reaches disk only when you save. So the
    thing to execute is the text, and `filepath` is passed only so tracebacks and
    line numbers point at the file a person is looking at — `compile()` records
    it, and the frame walk that gives a clip its provenance reads it back.

    Returns, rather than raising: a scene that fails is the normal state of a
    scene being written, and the editor has somewhere to show the failure.
    Nothing is left half-applied — `Context` is reset before the run, and on a
    failure the caller keeps whatever it had.
    """
    _resetContext()

    scope = dict(globals())
    scope["__name__"] = "Scene"

    try:
        _besideScene(filepath)
        code = compile(source, filepath, "exec")
        scope = _runUntilStable(code, scope, lambda: _sceneScope(_resetContext()))
        params.checkRun()
        _applyBackground(scope)
        # Collected as well as printed. These two ran on every keystroke in the
        # editor and spoke only to stderr, which the editor does not read — the
        # one mechanism built to say "swapping these two lines gives a different
        # video" reached nobody who was editing. `Editor::executeScene` copies
        # every key of this dict through to QML, so returning them is the whole
        # of the wiring.
        warnings = _reportContendedKeys() + _reportBadValues()
        warnings = [w for w in warnings if w["file"] == filepath]
    except SyntaxError as error:
        return {
            "ok": False,
            "line": (error.lineno or 1) - 1,
            "column": max((error.offset or 1) - 1, 0),
            "message": error.msg or "syntax error",
        }
    except BaseException as error:
        # The innermost frame that is still the USER's — a traceback through the
        # library is true and useless; the line they can act on is the last one
        # inside the file they are editing.
        line = 0
        tb = error.__traceback__
        while tb is not None:
            if tb.tb_frame.f_code.co_filename == filepath:
                line = tb.tb_lineno - 1
            tb = tb.tb_next
        return {
            "ok": False,
            "line": line,
            "column": 0,
            "message": f"{type(error).__name__}: {error}",
        }

    model = sceneModel()
    # Outside the try, like the model itself: a bug in the lint raises rather
    # than posing as the scene failing on line 1. last-frame-only stays out of
    # the editor — it is what every line typed at the end of a scene is until
    # its wait() is.
    warnings += [w for w in _reportLint(model) if w["file"] == filepath and w["rule"] != "last-frame-only"]

    return {
        "ok": True,
        # JSON, like `scene` below, because the bridge to the editor stringifies
        # every value it is handed: a plain list arrived in QML as the TEXT
        # "[]", which is truthy and has no `.map`, so every single execution
        # raised a TypeError and the diagnostics were never assigned. The
        # warnings this collects — two lines writing the same channel over the
        # same frames — had therefore never once been shown to anyone.
        "warnings": json.dumps(warnings),
        "inputs": len(Context.stack),
        "frames": max(Context.lastEverAffectedFrame, 1),
        "fps": FRAMERATE,
        "scene": json.dumps(model),
    }


def _lintOnce(source: str, filepath: str, shape: str) -> set[tuple]:
    """One run's findings, as (file, line, severity, message, rule); `shape` is the frame's name, for title-safe."""
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        report = execSource(source, filepath)
        if not report["ok"]:
            message = report["message"]
            if message.startswith("ParamError: "):
                return {(filepath, report["line"] + 1, "error", message.removeprefix("ParamError: "), "param")}
            return {(filepath, report["line"] + 1, "error", message, "scene-error")}
        found = _reportContendedKeys() + _reportBadValues() + _reportLint(json.loads(report["scene"]))
        found += _reportTitleSafe(json.loads(report["scene"]), shape)
    return {(w["file"], w["sourceLine"], "error" if w.get("severity") == 1 else "warning", w["message"], w["rule"])
            for w in found}


@contextlib.contextmanager
def _inFrame(width: int, height: int):
    """
    Run the scene in another frame for as long as this lasts — the Python half
    of what `applyScreenSize` does before each `--for` render — and put the
    frame it found back after.
    """
    before = (SW, SH, os.environ.get("VC_SCREEN"))
    os.environ["VC_SCREEN"] = f"{width}x{height}"
    constants.setScreen(width, height)
    try:
        yield
    finally:
        constants.setScreen(before[0], before[1])
        if before[2] is None:
            os.environ.pop("VC_SCREEN", None)
        else:
            os.environ["VC_SCREEN"] = before[2]


def lintSource(source: str, filepath: str, sets: list[str] | None = None, data: str = "",
               shapes: list[tuple[str, int, int]] | None = None) -> tuple[str, int]:
    """
    `--lint`: run a scene without rendering it and say what is wrong with it, one
    `file:line: error|warning: message [rule]` per line, and 1 if any is an error.

    Findings only: the scene's own prints and the reporters' stderr paragraphs
    are swallowed, since the reporters run twice here — once in `execSource`,
    for the editor's filtered list, and once more unfiltered, which is cheap:
    they only read `Context`, which still holds this run.

    With `--set`/`--data` the scene runs once per row, given that row, so a
    required param() nobody gave, a --set key nothing reads and a cell that
    does not read as its parameter's type are all found without a frame being
    rendered. With `--for`, `shapes` — (name, width, height) — and the scene
    runs again in each frame, as the renders would: a title safe in 16:9 is
    not in 9:16. A finding every row and every shape shares is said once.
    """
    said: set[tuple] = set()
    rows: list[dict] = []
    if sets or data:
        try:
            rows = params.plan(sets or [], data, "lint.mp4")
        except params.ParamError as error:
            return f"{filepath}: error: {error} [param]\n", 1
    for name, width, height in shapes or [("", SW, SH)]:
        shape = f"{name} ({width}x{height})" if name else f"{width}x{height}"
        with _inFrame(width, height):
            if not rows:
                said |= _lintOnce(source, filepath, shape)
                continue
            before = os.environ.get("VC_PARAMS")
            try:
                for row in rows:
                    params.provide(row["params"])
                    said |= _lintOnce(source, filepath, shape)
            finally:
                if before is None:
                    os.environ.pop("VC_PARAMS", None)
                else:
                    os.environ["VC_PARAMS"] = before
    if rows:
        unread = params.unreadColumns().removeprefix("video-code: warning: ").strip()
        if unread:
            said.add((filepath, 1, "warning", unread, "unread-column"))
    lines = sorted(said)
    return "".join(f"{f}:{n}: {s}: {m} [{r}]\n" for f, n, s, m, r in lines), int(any(s == "error" for _, _, s, _, _ in lines))


def serializeScene(filepath: str) -> str:
    """
    Serialiaze a file representing a `Scene`.
    """
    _resetContext()

    # Read the content of the file
    with open(filepath, "r") as file:
        content = file.read()

    # Same fresh namespace as execScene, for the same reason: one run must not
    # inherit the names of the last.
    _besideScene(filepath)
    code = compile(content, filepath, "exec")
    scope = dict(globals())
    scope["__name__"] = "Scene"
    exec(code, scope)

    _applyBackground(scope)

    return json.dumps(
        {"stack": Context.stack, "events": [e.jsonSerialization() for e in Context.events]},
        default=lambda x: x.jsonSerialization(),
    )


if __name__ == "__main__":
    print(serializeScene("video.py"), file=sys.stderr)
