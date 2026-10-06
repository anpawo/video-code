#!/usr/bin/env python3

from __future__ import annotations

import os
import re
import inspect
import sys
from abc import abstractmethod
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Callable, Iterable
from videocode.constants import *

if TYPE_CHECKING:
    from videocode.shader.ishader import IShader
    from videocode.input.input import Input


class Metadata:
    def __init__(self, *, interface: bool = False) -> None:
        # --- Index
        """
        Index of the `Input`.

        Groups do not have an index (they are just python wrapper)
        """
        noRegister = Context._noRegister
        noHiding = Context._noHiding

        self.index: int = cast(int, None) if (interface or noRegister) else Context.getIndex()

        # --- Position ---
        self.position: v2[wnumber, wnumber] = v2(0, 0)

        # --- Align ---
        self.align: v2[wnumber, wnumber] = v2(0.5, 0.5)

        # --- Scale ---
        self.scale: v2[wnumber, wnumber] = v2(1, 1)

        # --- Rotation ---
        self.rotation: number = 0

        # --- Opacity ---
        self.opacity: number = 255

        # --- Hidden ---
        self.hidden: bool = False

        # --- ZIndex ---
        # Defaults to creation order (no ties unless explicitly set).
        self.zIndex: int = self.index if self.index is not None else 0

        # Bumped via Context.nextZOrderSeq() every time zIndex is explicitly
        # set. Ties in zIndex are broken by this: the most recently changed
        # one wins (renders on top), regardless of creation order.
        self.zOrderSeq: int = 0

        # --- Blend mode ---
        # Compositing mode index (see shader/vertexShader/blendMode.py):
        # 0=normal, 1=multiply, 2=screen, 3=add. Default is normal.
        self.blendMode: int = 0

        # --- Track matte / mask ---
        # Index of another Input whose alpha masks this one (see
        # shader/vertexShader/matte.py). None = no matte. Travels to C++ as a
        # plain int (Metadata.matteSource, -1 = none).
        self.matteSource: int | None = None

        # --- Pinned to the frame ---
        # When True the scene camera never moves this input: it is drawn where
        # the frame says, not where the world does (see
        # shader/vertexShader/pinToFrame.py). Subtitles, watermarks.
        self.pinnedToFrame: bool = False

        # --- Adjustment layer ---
        # When True this input is never drawn on its own; its fragment effects
        # grade the flattened composite of everything below its zIndex (see
        # shader/vertexShader/adjustmentLayer.py and input/AdjustmentLayer.py).
        self.isAdjustmentLayer: bool = False

        # --- Composition ---
        # When True this input is never drawn on its own: its members are
        # flattened into one layer and that layer carries this input's opacity,
        # effects and matte (see shader/vertexShader/composition.py,
        # input/interface/Composition.py). `compositionIndex` is the other end —
        # the layer this input is a member OF, travelling to C++ as a plain int
        # (-1 = none).
        self.isComposition: bool = False
        self.compositionIndex: int | None = None

        if not interface and not noRegister:
            Context.metas.append(self)

        # --- Offset ---
        self.lastAffectedFrame: frame = Context.waitOffset
        """
        Last frame affected by a `Transformation` from the last applied `Transformation`

        Starts at waitOffset because any waits should consume all previous effects.
        """
        self.transformationOffset: frame = self.lastAffectedFrame
        """
        Increased by `lastAffectedFrame` when flushed.

        Also starts at Global.waitOffset
        """

        # --- Delay ---
        self.pendingStart: sec = 0
        """
        Keep start through setattr.
        """
        self.pendingDuration: sec = SINGLE_FRAME
        """
        Keep duration through setattr.
        """
        self.pendingOffset: maybe[frame] = None
        """
        Keep transformation offset through setattr.
        """

        # --- Callbacks ---
        # preCallbacks: called before a shader is applied. Signature: (shader, start, duration, offset) -> bool.
        #   - Mutate the shader's fields to rewrite its values (e.g. wrap a position modulo a tile size).
        #   - Return True to drop the shader entirely (it never reaches the stack).
        #   - Return False to let the (possibly mutated) shader through as normal.
        # postCallbacks: called after a shader is applied. Signature: (shader, start, duration, offset) -> None.
        self.preCallbacks: dict[type[IShader], list[Callable[..., bool]]] = {}
        self.postCallbacks: dict[type[IShader], list[Callable[..., None]]] = {}

    def __str__(self) -> str:
        s = "\n"
        for k, v in self.__dict__.items():
            s += f"\t\t{k}={v}\n"
        return s


class StackAction:

    @abstractmethod
    def __init__(self): ...

    def __str__(self) -> str:
        return str(vars(self))

    def jsonSerialization(self):
        return vars(self)


class Wait(StackAction):
    def __init__(self, startFrame: int, numberOfFrame: int, stop: list[str], line: int = 0):
        self.action = self.__class__.__name__
        self.start = startFrame
        self.n = numberOfFrame
        # Which ambient clocks pause during the gap (Clock values; [] = none).
        self.stop = stop
        # The line it was written on. A wait is where the scene's time actually
        # joins — everything before it has ended, everything after starts from
        # there — so the editor draws it across the timeline, and a gesture that
        # lengthens something knows what will move because of it.
        self.line = line


class Timestamp(StackAction):
    def __init__(self, name: str, time: int, file: str = "", line: int = 0):
        self.action = self.__class__.__name__
        self.name = name
        self.time = time
        # Where it was written, so the caret on a `timestamp()` line has
        # something on the timeline to light and to play from.
        self.file = file
        self.line = line


# The library's own directory, with the trailing separator. Recomputed on every
# `_callSite()` before it was hoisted: 28580 `dirname`, 14288 `abspath` and
# 14316 `join` calls per bake of the text benchmark, all for one constant.
_LIBRARY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "videocode") + os.sep


# What a type in ty.py promises about a number: the closed ranges the editor
# can refuse before writing, and the run can refuse after.
_BOUNDS: dict[str, tuple[float | None, float | None]] = {
    "uint8": (0, 255), "percent": (0, 100),
    "uint": (0, None), "ufloat": (0, None), "unumber": (0, None),
    "wuint": (0, None), "wufloat": (0, None), "wunumber": (0, None),
    "sec": (0, None), "frame": (0, None),
}


def _kindName(annotation: Any) -> str:
    text = getattr(annotation, "__name__", None) or str(annotation)
    hit = re.search(r"\b(" + "|".join(_BOUNDS) + r")\b", text)
    return hit.group(1) if hit else ""


def _outOfBounds(cls: type, func: str, given: dict[str, Any]) -> str:
    method = getattr(cls, func, None) if func else None
    if method is None:
        return ""
    try:
        params = inspect.signature(method).parameters
    except (TypeError, ValueError):
        return ""
    for name, param in params.items():
        value = given.get(name)
        if name == "self" or isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        kind = _kindName(param.annotation)
        if not kind:
            continue
        low, high = _BOUNDS[kind]
        if (low is not None and value < low) or (high is not None and value > high):
            said = f"{low}–{high}" if high is not None else f"≥ {low}"
            who = cls.__name__ if func == "__init__" else func
            return f"{who}({name}={value}): {kind} is {said}"
    return ""


class Context:
    """
    Context containing the `Metadata` of the `Scene`.
    """

    # stack[inputIdx][-1]            = {"type": str, "args": dict}          — Create
    # stack[inputIdx][frameIdx][key] = {"type": shaderType, **shaderArgs}   — Apply
    # "Args" shaders use key "Args:{argName}" to allow multiple per frame.
    stack: dict[int, dict] = {}

    # Where each input came from: (file, line, python class). A SIDE TABLE, never
    # part of `stack` — C++ hands `stack[i]["args"]` straight into shader parsing
    # and diffs the dicts to decide what to rebuild, so a new key there would
    # both travel somewhere it does not belong and defeat the incremental reload.
    origin: dict[int, tuple[str, int, str]] = {}

    # Wait and Timestamp actions; C++ consumes these separately.
    events: list[StackAction] = []

    # Index of the next `Input`
    inputCounter: int = 0

    # Last ever affected frame
    lastEverAffectedFrame: frame = 0

    # Where the scene's time stands: the frame after the last one still
    # changing anything. `lastEverAffectedFrame` cannot answer that — it is the
    # exclusive end of the last WRITE, and an instant (`hide()`, `fillColor =`,
    # a creation's `show`) is a one-frame write, so it sits one past the frame
    # it lands on. `wait()` used to start from there, and every instant after a
    # `wait()` stretched the scene by a frame: `wait(1); Circle(); wait(1)`
    # measured 61. An instant takes no time, so it leaves the cursor where it
    # was written; only a span moves it to its end.
    cursor: frame = 0

    # Wait creates an offset affecting the start of any transformation
    waitOffset: frame = 0

    # Clear color of the frame, normalized 0..1 RGB — set by assigning a
    # plain `rgba` to the script-global `BG` (resolved by serialize.py after
    # the scene runs; C++ reads this attribute like lastEverAffectedFrame).
    # None = the renderer's default dark gray.
    backgroundColor: tuple[float, float, float] | None = None

    # Monotonic counter for zIndex tiebreaks — see Metadata.zOrderSeq
    zOrderCounter: int = 0

    # Stack keys that are two names for one state — writing one on a frame
    # removes the other. See Context.apply().
    _EXCLUSIVE: dict[str, str] = {"Hide": "Show", "Show": "Hide"}

    # True while a Group is emitting toward its members.
    #
    # What reaches a member then is not an instruction someone wrote about that
    # member — it is the group's transform, worked out for that frame. A group
    # re-emits its whole window on every `apply`, so two chained animations look
    # from the outside like two statements fighting over the same key, when
    # `_rigidTimeline` has in fact already composed them per channel. Telling the
    # two apart is what keeps `contendedKeys()` from crying wolf on
    # `g.scaleTo(...).rotateBy(...)` — and what keeps it ABLE to speak up when a
    # member is written directly during a group's window, which is a real
    # conflict (council of 2026-08-26: warn, do not compose).
    deriving: bool = False

    # WHICH group is deriving, when one is. Two emissions the same group worked
    # out are not rivals; two DIFFERENT groups writing one member's channel are —
    # `Text.find` hands the same `Letter` to two groups, and the second silently
    # overwrote thirty frames of the first (measured: formation 2.000 -> 1.750,
    # 1.114 of jump in a single frame, and `contendedKeys()` said nothing,
    # because the `derived and derived` test could not tell the two cases apart).
    derivingGroup: maybe[int] = None

    # Every non-interface Metadata ever created — used to resolve relative
    # layer-order operations (bringToFront, sendToBack, bringForward, sendBackward).
    metas: list[Metadata] = []

    # When True, Input.__new__ skips index assignment and @inputCreation skips
    # Context.create().  Used by MergeGroup to build member geometry without
    # registering each member as a C++ input.
    _noRegister: bool = False

    # When True, Input@inputCreation skips the hiding until waitOffset.
    _noHiding: bool = False

    @staticmethod
    @contextmanager
    def noRegister():
        prev = Context._noRegister
        Context._noRegister = True
        try:
            yield
        finally:
            Context._noRegister = prev

    @staticmethod
    @contextmanager
    def noHiding():
        prev = Context._noHiding
        Context._noHiding = True
        try:
            yield
        finally:
            Context._noHiding = prev

    @staticmethod
    def getIndex() -> int:
        Context.inputCounter += 1
        return Context.inputCounter - 1

    @staticmethod
    def nextZOrderSeq() -> int:
        Context.zOrderCounter += 1
        return Context.zOrderCounter

    @staticmethod
    def maxZIndex() -> int:
        return max((m.zIndex for m in Context.metas if m.zIndex != BACKGROUND_Z_INDEX), default=0)

    @staticmethod
    def minZIndex() -> int:
        return min((m.zIndex for m in Context.metas if m.zIndex != BACKGROUND_Z_INDEX), default=0)

    @staticmethod
    def zIndexAbove(z: int) -> maybe[int]:
        """Smallest zIndex among all non-background inputs strictly greater than `z`, or None."""
        candidates = [m.zIndex for m in Context.metas if m.zIndex != BACKGROUND_Z_INDEX and m.zIndex > z]
        return min(candidates) if candidates else None

    @staticmethod
    def zIndexBelow(z: int) -> maybe[int]:
        """Largest zIndex among all non-background inputs strictly less than `z`, or None."""
        candidates = [m.zIndex for m in Context.metas if m.zIndex != BACKGROUND_Z_INDEX and m.zIndex < z]
        return max(candidates) if candidates else None

    @staticmethod
    def create(inputIndex: int, inputType: str, inputArgs: dict[str, Any]):
        Context.stack.setdefault(inputIndex, {})[-1] = {"type": inputType, "args": inputArgs}
        Context.origin[inputIndex] = Context._callSite()

    @staticmethod
    def _callSite() -> tuple[str, int, str]:
        """
        Where in the USER's file this input was made, and what class made it.

        `inputType` is the C++ factory key, so every shape in a scene comes back
        as "Polygon" and a `Text` arrives as one input per glyph — the stack
        cannot say what a person wrote. This walks out of the library to the
        first frame that is not ours, which is the right answer whether the call
        was written there directly or three levels down inside `Text.__init__`,
        and it is honest under `from videocode import *` by construction.

        The innermost library frame's `self` recovers the class the stack
        destroys: `Text`, `Square`, `Circle`.
        """
        frame = sys._getframe(2)
        cls = ""
        # The last library function crossed on the way out — `moveBy`,
        # `scaleTo`, `fadeIn`. The stack knows which method a person called; the
        # shaders it produced do not, and the editor needs it to offer "remove
        # this" on the right call of a chain rather than on the whole line.
        func = ""
        # The OUTERMOST library frame's `self`, not the innermost: a `Text`
        # builds `Letter`s, and the letter is an implementation detail of the
        # word. So the frames are kept and read from the outside in, taking the
        # first that has one — reading `self` on the way out instead asked every
        # frame for it and threw all but the last answer away, 57k
        # FrameLocalsProxy lookups per bake of the text benchmark.
        crossed = []
        while frame is not None:
            name = frame.f_code.co_filename
            if not name.startswith(_LIBRARY):
                break
            if not frame.f_code.co_name.startswith("_") and frame.f_code.co_name not in (
                "apply", "broadcast", "noteStatement", "wrapper", "inner",
            ):
                func = frame.f_code.co_name
            crossed.append(frame)
            frame = frame.f_back

        Context.lastBad = ""
        owner = None
        for outer in reversed(crossed):
            owner = outer.f_locals.get("self")
            if owner is not None:
                cls = type(owner).__name__
                # The person's own arguments are in this frame: a value a type
                # forbids is caught here, once, whichever verb it came through.
                Context.lastBad = _outOfBounds(
                    type(owner), outer.f_code.co_name if outer.f_code.co_name == "__init__" else func,
                    outer.f_locals)
                break

        Context.lastCallFunction = func
        where = ("", 0, cls) if frame is None else (frame.f_code.co_filename, frame.f_lineno, cls)
        # Recorded here rather than by the statement, since a constructor
        # records none: `Square(cornerRadius=200)` has to reach the code pane too.
        if Context.lastBad and where[1] > 0:
            bad = {"file": where[0], "line": where[1],
                   "input": getattr(getattr(owner, "meta", None), "index", None), "message": Context.lastBad}
            if bad["input"] is None:
                bad["input"] = -1
            if bad not in Context.badValues:
                Context.badValues.append(bad)
        return where

    # One entry per apply() that reached the stack: which input, which line of
    # the person's file, which shader keys, and the frames it covers. A SIDE
    # TABLE like `origin` — the stack itself is handed to C++ and diffed, so
    # nothing that is only for the editor may live in it.
    statements: list[dict[str, Any]] = []

    # Filled by the last `_callSite()`: the library function the person called.
    lastCallFunction: str = ""
    # Filled by the last `_callSite()`: what its arguments broke, or "".
    lastBad: str = ""
    # Every argument a run refused: file, line, input, message. Reported with
    # the warnings, so the code pane underlines the line and the clip carries it.
    badValues: list[dict[str, Any]] = []

    # The `shot()` blocks open right now, outermost first. Everything made
    # while one is open belongs to it — and to the ones around it, because a
    # shot inside another shot is part of it.
    openShots: list[Any] = []

    @staticmethod
    def noteStatement(
        inputIndex: int, touched: dict[str, list[int]], offset: int = 0, cursor: int = 0
    ) -> None:
        """
        Record where a statement was written, and what it covers.

        The line is read here rather than per shader: the walk out of the library
        costs about 2 µs, an animation is hundreds of shaders, and every one of
        them came from the same line anyway.
        """
        file, line, _ = Context._callSite()
        Context.statements.append({
            "file": file,
            "line": line,
            "call": Context.lastCallFunction,
            "input": inputIndex,
            "keys": {name: (span[0], span[1]) for name, span in touched.items()},
            # An emission a Group worked out, rather than a line someone wrote.
            "derived": Context.deriving,
            "derivedBy": Context.derivingGroup,
            "offset": offset,
            # Where the element's cursor stands once this statement is done —
            # which is what a statement written on the NEXT line would count its
            # `start` from. The editor needs it to write a `hide` at a chosen
            # moment: `hide(start=…)` is seconds after the cursor, and the
            # cursor is nowhere in the buffer.
            "cursor": cursor,
        })

    @staticmethod
    def _callSpans() -> list[dict[str, Any]]:
        """
        One span per (emitter call, channel), in the order the calls were WRITTEN.

        `ease()`, and everything built on it, writes a frame at a time: a
        47-frame ramp is 47 statements one frame long. Counting those raw makes
        every span a single frame and hides the whole of paint animation. The
        editor already groups the same way, by (line, call) — see
        `serialize.sceneModel`.

        Grouping by LINE was the approximation, and it swallowed a loop: three
        `moveTo` written by the same `for` are three calls on one line, so they
        merged into a single span reaching from the first to the last — and a
        loop that writes its steps backwards became invisible to
        `backdatedWrites()`. Since S1, a verb call knows which statements it
        wrote (`Context.calls`), so the ones it claims are grouped by CALL and
        the rest — placements, effects, what a group emits — keep the old key.
        """
        owner: dict[int, tuple[int, int]] = {}
        for index, written in Context.calls.items():
            for rank, statements in enumerate(written):
                for i in statements:
                    owner[i] = (index, rank)

        calls: dict[tuple[Any, ...], dict[str, list[int]]] = {}
        for i, st in enumerate(Context.statements):
            mine = owner.get(i)
            spans = calls.setdefault((st["input"], st["file"], st["line"], st["call"],
                                      st.get("derived", False), st.get("derivedBy"), mine), {})
            for key, (first, last) in st["keys"].items():
                held = spans.get(key)
                if held is None:
                    spans[key] = [first, last]
                else:
                    held[0] = min(held[0], first)
                    held[1] = max(held[1], last)

        out: list[dict[str, Any]] = []
        for (inputIndex, file, line, call, derived, derivedBy, _), spans in calls.items():
            for key, (first, last) in spans.items():
                out.append({"key": key, "input": inputIndex, "first": first, "last": last,
                            "file": file, "line": line, "call": call, "derived": derived,
                            "derivedBy": derivedBy})
        return out

    # ── S1 : la résolution différée de la base ────────────────────────────
    #
    # Une animation lit sa valeur de départ au moment où la LIGNE s'exécute, et
    # non au moment où elle JOUE. C'est juste tant que les lignes sont écrites
    # dans l'ordre du film ; `backdatedWrites()` dit quand ça ne l'est plus.
    #
    # Le remède est d'exécuter la scène DEUX FOIS : la première donne la vérité
    # image par image, la seconde rejoue en donnant à chaque animation la base
    # qu'elle a vraiment à l'image où elle s'ouvre. Écrire un marqueur à la
    # place de la valeur a été écarté à la conception : dix-neuf modèles font de
    # la trigonométrie sur cette base, et un marqueur ne survit pas à un cosinus.
    #
    # `replaying` porte la vérité de la première passe pendant la seconde ; il
    # est None le reste du temps, et le reste du temps est TOUT le temps pour
    # les 50 scènes du corpus, qui ne déclenchent jamais la seconde passe.
    replaying: maybe[dict[str, Any]] = None

    #: Les instructions qu'un verbe a écrites, par entrée et dans l'ordre des
    #: appels — la seule façon de dire, en relisant la pile, quelle revendication
    #: appartient à qui.
    calls: dict[int, list[list[int]]] = {}

    #: Ce que valait chaque canal avant que le premier verbe ne touche l'entrée.
    starts: dict[int, dict[str, Any]] = {}

    #: Les canaux qu'un modèle lit comme base, et le champ où la valeur d'un axe
    #: vit dans les arguments du shader.
    _BASE_KEYS = {
        "Position:x": "x", "Position:y": "y",
        "Scale:x": "x", "Scale:y": "y",
        "Align:x": "x", "Align:y": "y",
        "Rotation": "degree",
        "Opacity": "opacity",
    }

    @staticmethod
    def record(input: Any, mark: int) -> None:
        """Attribuer à l'appel qui vient de finir les instructions qu'il a écrites."""
        index = getattr(input.meta, "index", None)
        if index is None:
            return
        Context.calls.setdefault(index, []).append(list(range(mark, len(Context.statements))))

    @staticmethod
    def baseline() -> dict[str, Any]:
        """
        Ce que la première passe a prouvé, dans la forme où la seconde le lit :

        - `opens` : par entrée et par appel, l'image où chaque canal s'ouvre ;
        - `owned` : par entrée et par canal, les fenêtres écrites par chaque
          appel — c'est ce qui permet à une animation de ne PAS se rebaser sur
          sa propre sortie, faute de quoi la seconde passe rendrait la première ;
        - `values` : la pile relue, triée par image ;
        - `starts` : la valeur d'avant le premier verbe, le plancher quand rien
          d'autre n'a revendiqué le canal avant l'ouverture.

        La scène est déterministe : le n-ième appel de la seconde passe est le
        n-ième de la première, et c'est ce qui rend l'attribution par rang juste.
        """
        opens: dict[int, list[dict[str, frame]]] = {}
        owned: dict[tuple[int, str], list[tuple[frame, frame, int]]] = {}
        for index, calls in Context.calls.items():
            for rank, written in enumerate(calls):
                keys: dict[str, frame] = {}
                for i in written:
                    st = Context.statements[i]
                    if st["input"] != index:
                        continue
                    for key, (first, last) in st["keys"].items():
                        if key not in Context._BASE_KEYS:
                            continue
                        keys[key] = min(keys.get(key, first), first)
                        owned.setdefault((index, key), []).append((first, last, rank))
                opens.setdefault(index, []).append(keys)

        values: dict[tuple[int, str], list[tuple[frame, dict]]] = {}
        for index, entry in Context.stack.items():
            for f, claimed in entry.items():
                if f == -1:
                    continue
                for key, shader in claimed.items():
                    channel = key.split(":")[0]
                    values.setdefault((index, channel), []).append((f, shader["args"]))
        for series in values.values():
            series.sort(key=lambda pair: pair[0])

        return {
            "opens": opens,
            "owned": owned,
            "values": values,
            "starts": dict(Context.starts),
            "seen": {},
        }

    @staticmethod
    def rebase(input: Any) -> None:
        """
        Donner à l'appel qui va s'écrire la base qu'il a vraiment.

        Appelée juste avant qu'un verbe ne lise `meta`, et sans effet hors de la
        seconde passe — où elle ne touche que les canaux que cet appel écrit :
        remettre à sa valeur d'autrefois un canal auquel il ne touche pas
        casserait la ligne suivante.
        """
        index = getattr(input.meta, "index", None)
        if index is None:
            return
        if index not in Context.starts:
            Context.starts[index] = Context._readBase(input.meta)

        told = Context.replaying
        if told is None:
            return
        rank = told["seen"].get(index, 0)
        told["seen"][index] = rank + 1
        calls = told["opens"].get(index, [])
        if rank >= len(calls):
            return

        for key, at in calls[rank].items():
            value = Context._resolve(told, index, key, at, rank)
            if value is not None:
                Context._writeBase(input.meta, key, value)

    @staticmethod
    def _resolve(told: dict, index: int, key: str, at: frame, rank: int) -> Any:
        """
        Ce que valait `key` à l'image `at`, sans compter ce que l'appel y écrit.

        La règle « même image » tombe de là toute seule : un placement statique
        n'est pas un appel, donc il n'appartient à personne, donc l'image où il
        pose l'objet reste lisible — quatre scènes du corpus ouvrent une
        animation pile sur ce placement, à l'image zéro.
        """
        field = Context._BASE_KEYS[key]
        series = told["values"].get((index, key.split(":")[0])) or []
        windows = told["owned"].get((index, key)) or []

        found = None
        for f, args in series:
            if f > at:
                break
            owners = {r for first, last, r in windows if first <= f <= last}
            if owners and owners <= {rank}:
                continue
            if args.get(field) is not None:
                found = args[field]
        if found is None:
            found = told["starts"].get(index, {}).get(key)
        return found

    @staticmethod
    def stateAt(index: int, at: frame) -> dict[str, Any]:
        """
        Ce que l'entrée `index` vaut à l'image `at` — ses canaux, résolus.

        La même lecture que la seconde passe de S1, sans le filtre de propriété :
        elle, elle demande « sans compter ce que J'écris » ; ici on veut tout,
        puisque la question est ce que le film montre à cette image-là.

        C'est la seule réponse à « où est cet objet MAINTENANT ». Les arguments
        d'un appel disent avec quoi il a été fabriqué, jamais où il en est.
        """
        out: dict[str, Any] = dict(Context.starts.get(index, {}))
        entry = Context.stack.get(index, {})
        for f in sorted(f for f in entry if f != -1 and f <= at):
            for key, shader in entry[f].items():
                # `Args:fillColor` is a written argument that something animates
                # — a `fill()` writes one per frame with the colour it has
                # reached. It carries its value directly rather than through a
                # channel, because it IS the argument, not a transform of it.
                if key.startswith("Args:"):
                    out[key] = shader.get("args", {}).get("value")
                    continue
                channel = key.split(":")[0]
                for full, field in Context._BASE_KEYS.items():
                    if full.split(":")[0] != channel:
                        continue
                    value = shader.get("args", {}).get(field)
                    if value is not None:
                        out[full] = value
        return out

    @staticmethod
    def _readBase(meta: Any) -> dict[str, Any]:
        """La valeur de chaque canal, à plat, telle qu'un verbe la lirait."""
        return {
            "Position:x": meta.position.x, "Position:y": meta.position.y,
            "Scale:x": meta.scale.x, "Scale:y": meta.scale.y,
            "Align:x": meta.align.x, "Align:y": meta.align.y,
            "Rotation": meta.rotation,
            "Opacity": meta.opacity,
        }

    @staticmethod
    def _writeBase(meta: Any, key: str, value: Any) -> None:
        """La valeur relue, remise dans le meta — un axe à la fois."""
        channel, _, axis = key.partition(":")
        if channel == "Rotation":
            meta.rotation = value
        elif channel == "Opacity":
            meta.opacity = value
        else:
            setattr(getattr(meta, channel.lower()), axis, value)

    @staticmethod
    def backdatedWrites() -> list[dict[str, Any]]:
        """
        Statements that live EARLIER than one written before them.

        An animation reads its starting value from the CURSOR — where the element
        stands once everything written so far has been accounted for. That is the
        right answer as long as the lines are written in the order they play.
        Give a `start=` that reaches back behind a line already written, and the
        cursor has been carried past it already: the animation starts from a value
        that belongs to a moment which has not happened yet.

        Measured: `moveTo(x=5, start=2)` followed by `moveTo(x=2)` sends x from
        **4.99 down to 2** over the first second, where the same two lines the
        other way round send it from 0 up to 2. Same intent, two videos, and
        nothing said so.

        That was before S1. Which statement opens first cannot be known until
        every line has run, so a run that finds one of these is run again with
        each base read at the frame its window opens (`_runUntilStable`): this
        is what asks for that second pass, and no longer something to warn of.

        A group re-emitting its own window reaches back all the time and is
        supposed to: derived spans are ignored.
        """
        byKey: dict[tuple[int, str], list[dict[str, Any]]] = {}
        for span in Context._callSpans():
            if span["derived"]:
                continue
            byKey.setdefault((span["input"], span["key"]), []).append(span)

        found: list[dict[str, Any]] = []
        for spans in byKey.values():
            for i, earlier in enumerate(spans):
                for later in spans[i + 1:]:
                    # `later` was written after, and opens before: its base was
                    # read off a cursor `earlier` had already carried forward.
                    if later["first"] < earlier["first"]:
                        found.append({"key": later["key"], "input": later["input"],
                                      "a": earlier, "b": later})
        return found

    @staticmethod
    def contendedKeys() -> list[dict[str, Any]]:
        """
        Statements that claim the same CHANNEL, on the same input, over frames
        that overlap — the one case where the order the two lines were TYPED in
        decides what the video looks like.

        Two claims on one channel cannot both hold: the later call wins the
        frames they share. `moveTo(x=2)` against `moveTo(x=5)` over the same
        second is not a compromise between the two, and swapping the lines gives
        a different video.

        A channel is finer than a shader class — `Position:x`, `Args:fillColor` —
        because an effect claims only what it was given. Two effects on different
        channels COMPOSE, whatever their windows, and reporting those would be
        crying wolf on the very thing the claim model exists to allow.

        Four things are deliberately NOT reported, because they are how a scene
        is written rather than a mistake:

        - Different channels. x against y, `fillColor` against `strokeColor`.
        - A construction call. `position(x=-4)` covers the single instant it
          lands on; `moveTo(x=4, duration=1)` starting there is the animation
          reading its own starting value, not fighting it. Both statements must
          cover more than one frame.
        - A single frame in common. Two animations that meet end-to-start touch
          on the frame they hand over, and the later one is meant to win it.
        - Two emissions a GROUP worked out. A group re-emits its whole window on
          every `apply`, so `g.scaleTo(...).rotateBy(...)` looks from outside like
          two statements fighting — when `_rigidTimeline` has already composed
          them per channel. A member written by hand during a group's window is
          still reported: there the two really do disagree.

        Nothing here is sent to C++ and nothing is prevented — it is a reading
        of `statements`, which the editor already keeps.
        """
        # ── One emitter call is ONE statement ─────────────────────────────
        # `ease()`, and everything built on it — `over()`, `easeTogether`,
        # `fillIn` — writes a frame at a time, so a 47-frame ramp arrives here as
        # 47 statements one frame long. Counting those raw made the whole of
        # paint animation invisible: every span was a single frame, and a single
        # frame is rightly never contended. Two `over().fillColor` overlapping by
        # 15 frames reported nothing at all.
        #
        # Grouped by (input, file, line, call) — the same grouping the editor
        # already uses to draw one bar per call (see `serialize.sceneModel`).
        byKey: dict[tuple[int, str], list[dict[str, Any]]] = {}
        for span in Context._callSpans():
            if span["last"] - span["first"] <= 1:
                continue
            byKey.setdefault((span["input"], span["key"]), []).append(span)

        found: list[dict[str, Any]] = []
        for spans in byKey.values():
            for i, a in enumerate(spans):
                for b in spans[i + 1:]:
                    # Two emissions a group worked out are not rivals: they are
                    # the same transform, composed per channel by `_rigidTimeline`
                    # before being sent. One derived and one written by hand IS a
                    # rival — that is the group-versus-member case, and it must
                    # still be said (council of 2026-08-26: warn, do not compose).
                    if a["derived"] and b["derived"] and a["derivedBy"] == b["derivedBy"]:
                        continue
                    shared = min(a["last"], b["last"]) - max(a["first"], b["first"])
                    if shared > 1:
                        found.append({"key": a["key"], "input": a["input"], "frames": shared,
                                      "from": max(a["first"], b["first"]), "a": a, "b": b})
        return found

    @staticmethod
    def channelKey(shaderName: str, argName: maybe[str]) -> str:
        """
        The name one piece of state answers to.

        `args(name, value)` is a single class for every attribute there is, so
        its class name alone made `fillColor` and `strokeColor` look like the
        same thing. Its channel is therefore `Args:<name>`; everything else is
        its own class.

        Written once because it was written twice: `Input.apply` used it to
        decide which statements are rivals, and `Context.apply` used it as the
        key a frame is stored under. They agreed by coincidence, and nothing
        would have said so if an edit to one had not been made to the other.
        """
        return f"Args:{argName}" if argName is not None else shaderName

    @staticmethod
    def apply(inputIndex: int, shaderName: str, shaderType: str, shaderArgs: dict[str, Any]):
        frameIdx = shaderArgs["start"]
        argName = shaderArgs.get("name") if shaderName == "Args" else None
        dictKey = Context.channelKey(shaderName, argName)
        onFrame = Context.stack.setdefault(inputIndex, {}).setdefault(frameIdx, {})
        # One piece of state, two names. Left side by side on a frame, both
        # travelled to C++ and the dict's INSERTION order — the order the two
        # calls happened to be typed in — decided which one held. Dropping the
        # one being contradicted makes the frame single-valued, which is what
        # it already meant; the survivor is the same one C++ was picking.
        opposite = Context._EXCLUSIVE.get(dictKey)
        if opposite is not None:
            onFrame.pop(opposite, None)
        # A component this effect does not CLAIM is a hole, not a value — and the
        # frame already holds what belongs in it. Filling the hole from the entry
        # being replaced is what lets two effects share a frame: before this, the
        # second simply erased the first, whatever channel it had really changed.
        #
        # This settles the collision ON a frame. A frame that only one of them
        # covers has no neighbour to fill from, and its hole travels to C++, where
        # an absent component means "leave that channel alone" and the carry holds
        # the value — that is what settles it BETWEEN frames.
        held = onFrame.get(dictKey)
        if held is not None:
            heldArgs = held["args"]
            for name, value in shaderArgs.items():
                if value is None and heldArgs.get(name) is not None:
                    shaderArgs[name] = heldArgs[name]
        onFrame[dictKey] = {
            "type": shaderType,
            "args": shaderArgs,
        }


def wait(n: sec = 0, stop: Clock | Iterable[Clock] | None = None) -> None:
    """
    Wait for all animations to end, then leave `n` seconds where nothing new
    is scheduled. By default the world stays ALIVE during the gap — shader
    fills keep animating, videos keep playing; `stop` pauses selected
    ambient clocks for the span:

        wait(2)                        # gap, everything keeps living
        wait(2, stop=Clock.VIDEOS)     # gap, footage pauses, fills breathe
        wait(2, stop=[Clock.VIDEOS, Clock.PAINTS])
        freeze(2)                      # = wait(2, stop=<all clocks>)

    A paused clock RESUMES where it stopped (pause, not skip). Scheduled
    state (positions, colors, visibility) always simply holds — there is
    nothing to stop.
    """
    # A gap cannot be negative, and the arithmetic below would not say so: the
    # conversion drops the sign nowhere, the cursor simply steps BACK over
    # frames already written, and everything after that is scheduled in the
    # past without a word.
    if n < 0:
        raise ValueError(
            f"wait({n}) — a wait is a gap, and a gap cannot be negative: the scene's "
            f"clock would step back over frames that are already written."
        )

    n = int(n * FRAMERATE)

    if stop is None:
        stopped: list[str] = []
    elif isinstance(stop, Clock):
        stopped = [stop.value]
    else:
        stopped = sorted(c.value for c in stop)

    # Python
    startFrame = max(Context.cursor, Context.waitOffset)
    Context.waitOffset = Context.cursor = startFrame + n
    # The gap still has to be rendered — and `wait(0)` right after an instant
    # must not shorten the scene to before that instant's frame.
    Context.lastEverAffectedFrame = max(Context.lastEverAffectedFrame, startFrame + n)

    Context.events.append(Wait(startFrame, n, stopped, Context._callSite()[1]))


def freeze(n: sec = 0) -> None:
    """
    A literal FREEZE-FRAME: `wait(n)` with every ambient clock stopped — the
    last rendered frame holds for `n` seconds (shader fills, videos and
    time-driven effects all pause, then resume where they stopped).
    """
    wait(n, stop=tuple(Clock))


def timestamp(name: str) -> None:
    caller = sys._getframe(1)
    Context.events.append(Timestamp(name, Context.cursor, caller.f_code.co_filename, caller.f_lineno))


class shot:
    """
    Name a stretch of the film, and everything made in it::

        with shot() as intro:
            title = Text("videocode")
            title.fadeIn()
            wait(2)

        with shot() as body:
            chart = BarChart(votes).grow()
            wait(3)

        cut(intro, body)

    A scene of several sections is written today as one long file where every
    element of every section stays on screen for the rest of the film unless
    each one is hidden by hand — the 27-variable pattern, and the reason a
    third section means going back to the first two. A shot is the block, so
    `cut` can put the whole of it away in one line.

    Nothing happens on `with` alone: a shot that is never cut from is just a
    name for a stretch, which is worth having on its own.
    """

    def __init__(self) -> None:
        self.first: frame = 0
        self.last: frame = 0
        self.inputs: list[Any] = []
        # Filled only by `asOneLayer()`, i.e. only by a crossfade.
        self._layer: Any = None

    def __enter__(self) -> "shot":
        self.first = max(Context.cursor, Context.waitOffset)
        self.inputs = []
        Context.openShots.append(self)
        return self

    def __exit__(self, *_: Any) -> None:
        Context.openShots.remove(self)
        self.last = max(Context.cursor, Context.waitOffset)

    def asOneLayer(self) -> Any:
        """
        The shot as a single layer — built once, and only if something asks.

        A crossfade cannot be n fades: two shots fading through each other
        member by member is not a dissolve, it is both scenes showing through
        each other's holes. `Composition` is what makes a group one picture, so
        a shot that has to dissolve becomes one — and stays one for the rest of
        the film, which is what a plan IS.

        Built under `noHiding` because a `Composition` made here is made LATE:
        the layer would otherwise hide itself back to frame 0 and take the shot
        with it.
        """
        from videocode.input.interface.Composition import Composition

        if self._layer is None:
            with Context.noHiding():
                self._layer = Composition(*self.inputs)
        return self._layer


def cut(*shots: shot, crossfade: sec = 0, easing: Any = None) -> None:
    """
    Leave one shot for the next::

        cut(intro, body, credits)                  # coupe franche
        cut(intro, body, crossfade=0.6)            # fondu enchaîné

    Without `crossfade`, everything the first shot made goes off screen at the
    exact frame the second opens — one hard cut, nothing else touched.

    With one, the two shots dissolve through each other over that many seconds,
    starting at the cut. A dissolve cannot be n fades: two shots fading member
    by member show through each other's holes, which is a mess and not a
    dissolve. So each shot in a dissolve becomes ONE LAYER — a `Composition` —
    and stays one for the rest of the film, which is what a plan is anyway. The
    cost is that members of a dissolving shot no longer take part in the
    frame's z-order on their own.

    An element already hidden stays hidden; hiding it again costs one claim and
    says the same thing.
    """
    from videocode.shader.vertexShader.hide import hide
    from videocode.template.effect.core.fadeTo import fadeTo
    from videocode.utils.bezier import Easing

    if len(shots) < 2:
        raise ValueError("cut() needs at least two shots — it is what happens BETWEEN them")
    if crossfade < 0:
        raise ValueError(f"cut(crossfade={crossfade}) — a dissolve cannot last less than no time")

    ramp = easing if easing is not None else Easing.Linear

    for earlier, later in zip(shots, shots[1:]):
        if crossfade == 0:
            for made in earlier.inputs:
                # The claim is written at an ABSOLUTE frame, not from the
                # element's own cursor: `cut` is written after both blocks, and
                # by then every element's clock is at the end of the scene.
                # `apply(offset=…)` is the same door the creation of a
                # mid-timeline element uses to hide itself back at frame 0.
                made.apply(hide(), start=0, offset=later.first)
            continue

        # A dissolve, then: both shots become one layer each, one ramps down
        # while the other ramps up, over the same window, from the cut.
        going, coming = earlier.asOneLayer(), later.asOneLayer()
        span = int(crossfade * FRAMERATE)

        going.apply(*fadeTo(going, src=255, dst=0, duration=crossfade, easing=ramp), offset=later.first)
        # And off, so a layer at zero opacity is not still being flattened for
        # the rest of the film.
        going.apply(hide(), start=0, offset=later.first + span)

        coming.apply(*fadeTo(coming, src=0, dst=255, duration=crossfade, easing=ramp), offset=later.first)
