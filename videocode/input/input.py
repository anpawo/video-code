#!/usr/bin/env python3


from __future__ import annotations

import functools
from copy import copy as _shallow_copy
from abc import ABC, abstractmethod
from typing import Any, Callable, Self, cast
from videocode.template.effect.core.alignTo import alignTo
from videocode.template.effect.core.fadeTo import fadeTo
from videocode.template.effect.core.moveAlong import moveAlong
from videocode.template.effect.core.moveTo import moveTo, moveBy
from videocode.template.effect.core.rotateTo import rotateBy, rotateTo
from videocode.template.effect.core.scaleTo import scaleBy, scaleTo
from videocode.shader.ishader import Effect, GroupEffect, IShader, Paint, VertexShader
from videocode.context import *
from videocode.constants import *
from videocode.utils.funcutils import *
from videocode.shader.vertexShader.align import align
from videocode.shader.vertexShader.args import args
from videocode.shader.vertexShader.hide import hide
from videocode.shader.vertexShader.rotate import rotation
from videocode.shader.vertexShader.scale import scale
from videocode.shader.vertexShader.position import position
from videocode.shader.vertexShader.translate import translate
from videocode.shader.vertexShader.show import show
from videocode.shader.vertexShader.opacity import opacity
from videocode.shader.vertexShader.zIndex import zIndex
from videocode.shader.vertexShader.blendMode import blendMode as _blendModeShader, BlendMode
from videocode.shader.vertexShader.matte import matte as _matteShader
from videocode.shader.vertexShader.pinToFrame import pinToFrame as _pinToFrameShader
from videocode.input.media.TrackedPath import TrackedPath
from videocode.utils.bezier import animate, Easing, easing
from videocode.utils.logger import *
from videocode.utils.classutils import At, AttributeNameReference, EaseAttributeSimplifier, _Over



def _rebasing(method):
    """
    Donner sa vraie base au verbe, juste avant qu'il ne la lise.

    Le modèle lit `input.meta` dès qu'il est appelé — avant `apply`, puisque le
    générateur est déballé par le `*`. Le seul moment où l'on peut corriger la
    base est donc l'entrée du verbe, et c'est tout ce que fait ce décorateur.
    Sans effet hors de la seconde passe de S1 : `Context.rebase` sort tout de
    suite quand `Context.replaying` est None, ce qui est le cas de toutes les
    scènes du corpus.
    """

    @functools.wraps(method)
    def inner(self, *args, **kwargs):
        Context.rebase(self)
        mark = len(Context.statements)
        try:
            return method(self, *args, **kwargs)
        finally:
            Context.record(self, mark)

    return inner


class Input(ABC):
    """
    An `Input` is a source that you want to add to the timeline of the video.

    It can be an `Image`, a `Video`, a `Shape`, some `Text` etc...
    """

    cppName: str = "Input"
    """
    Cpp Name of the Input.
    """

    cppAttrs: set[str] = set()
    """
    Attributes to pass to the cpp.
    """

    meta: Metadata = cast(Metadata, None)
    """
    Metadata of the `Input`.
    """

    def __new__(cls, *args, **kwargs) -> Self:
        instance = super().__new__(cls)
        instance.meta = Metadata()
        return instance

    @abstractmethod
    def __init__(self) -> None: ...

    @property
    def placed(self) -> bool:
        """
        Whether this input has a slot of its own in the stack C++ renders.

        The axis the codebase kept asking about sideways. A `Group` is not a
        different kind of thing because it has a pivot — a `Text` letter has
        one too — but because it never reaches `Context.stack`: no index, no
        slot, nothing of it is drawn. What is drawn are the members it moves.
        A leaf built inside `Context.noRegister()` is on the same side of the
        line for the same reason, which is why the question is asked about the
        slot and not about the class.
        """
        return self.meta.index is not None

    @property
    def composite(self) -> bool:
        """The other end of `placed`: worked out from what it holds, never drawn itself."""
        return self.meta.index is None

    def flush(self) -> Self:
        """
        Advance the transformation index offset to the latest frame ever modified.
        """
        self.meta.transformationOffset = self.meta.lastAffectedFrame
        return self

    def waitTo(self, n: frame) -> Self:
        if n < 0:
            raise ValueError(f"waitTo({n}) — there is no frame before the first one.")
        if n < self.meta.lastAffectedFrame:
            raise ValueError(
                f"waitTo({n}) is behind this element's clock (frame {self.meta.lastAffectedFrame}) — "
                f"waiting moves it forward or leaves it where it stands, never back."
            )
        return self._clockTo(n)

    # What the ENGINE means by waiting an element to a frame: put its clock
    # THERE, forwards or back. Catching up a global `wait()` before an effect,
    # carrying a group's members, laying out the letters of a text — every one of
    # them sets the clock, and the shape of an animation's frames depends on it
    # (measured: routing them through the refusal above stretched a 0.4 s ease
    # from frames 1–11 to 1, then 4–13). A person who writes `waitTo` means the
    # other thing, so that one refuses; this is the one the library calls.
    def _clockTo(self, n: frame) -> Self:
        self.meta.lastAffectedFrame = n
        return self.flush()

    def wait(self, n: sec) -> Self:
        if n < 0:
            raise ValueError(
                f"wait({n}) — a wait is a gap, and a gap cannot be negative: this element's "
                f"clock would step back over what it has already done."
            )
        self.meta.lastAffectedFrame += int(n * FRAMERATE)
        return self.flush()

    def waitFor(self, i: Input | sec) -> Self:
        """
        Set this element's clock to the moment `i` is done — an element's last
        effect, or a moment in seconds of the film such as a clip's `end`:

            merci = Text("Merci").opacity(0)
            merci.waitFor(marius.end).fadeIn()    # once the clip has played out
        """
        if isinstance(i, (int, float)):
            return self._clockTo(max(int(round(i * FRAMERATE)), self.meta.lastAffectedFrame))
        frames: list[frame] = []
        i.broadcast(lambda m: frames.append(m.meta.lastAffectedFrame))
        # "Until that one is done" — an element already past it has nothing left
        # to wait for, and walking its clock back is what wrote in the past.
        return self._clockTo(max(max(frames), self.meta.lastAffectedFrame))

    def apply(self, *shaders: IShader | Effect | GroupEffect, start: sec = 0, duration: sec = SINGLE_FRAME, offset: maybe[frame] = None, at: maybe[sec] = None) -> Self:
        """
        Applies some `Transformations` to the `Input`.

        The `duration` is in `seconds`, so it will affect `duration * framerate` frames of the video.
        Effects (e.g. `highlight()`) are callables — pass them directly: `input.apply(highlight())`.

        `at=` is the film's clock; `start=` is the element's. `start=2` means two
        seconds after everything already written for this element, which is what
        one wants while writing a shot in order. `at=2` means the second second
        of the film, whatever has been written — the sentence a person says out
        loud when the voice-over is already recorded.

        It is `offset=` in seconds, and nothing more: one conversion, in the one
        place that already turns seconds into frames.
        """

        offset = self._when(at, offset)

        # If a `wait()` happens, any input should be flushed before applying any new effect.
        if Context.waitOffset >= self.meta.transformationOffset:
            self._clockTo(Context.waitOffset)

        touched: dict[str, list[int]] = {}

        flatten: list[IShader] = []
        for s in shaders:
            # Checked BEFORE the IShader test, and that ordering is the point: a
            # paint is a VALUE, not a shader, so it falls into the `Effect`
            # branch below and gets CALLED. The author would see "object is not
            # callable" instead of being told what to do.
            if isinstance(s, Paint):
                raise TypeError(
                    f"{type(s).__name__} is a PAINT and can't be applied as an "
                    f"effect — set it as the fill instead: fillColor={type(s).__name__}(...)"
                )
            if not isinstance(s, IShader):
                flatten.extend(s(self))
            else:
                flatten.append(s)

        for s in flatten:

            # Pre-callbacks: fire before resolve/modify/stack-push. Mutate shader fields to rewrite
            # values, or return True to drop the shader entirely. Return False to let it through.
            if any(
                cb(s, start, duration, offset if offset is not None else self.meta.transformationOffset)
                for cb in self.meta.preCallbacks.get(type(s), [])
            ):
                continue

            _s, _d, _o = s.resolve(start, duration, offset)

            __start = round(_s * FRAMERATE) + (_o if _o is not None else self.meta.transformationOffset)
            __duration = round(_d * FRAMERATE)
            __end = __start + __duration

            # A composite has no slot of its own — a group, or a member built
            # inside `Context.noRegister()`. Still run modify() so meta.position
            # etc. get updated, but skip the stack.
            registered = self.placed

            # Update lastEverAffectedFrame
            if registered and Context.lastEverAffectedFrame < __end:
                Context.lastEverAffectedFrame = __end

            # Update our lastAffectedFrame
            if __end > self.meta.lastAffectedFrame:
                self.meta.lastAffectedFrame = __end

            # Transformations affect the Input's Metadata.
            # VertexShader.modify() writes resolved values back to self.* (e.g. position.modify
            # sets self.x = current x when x=None) so vars(s) contains the right args.
            # Shallow copy is sufficient: only primitive attributes are reassigned, never mutated.
            if not registered:
                if isinstance(s, VertexShader) and not s.autodestroy(self):
                    _shallow_copy(s).modify(self)
                continue

            key = upperFirst(s.__class__.__name__)

            # What is being written is the CHANNEL, not the shader class — and a
            # statement can claim several at once.
            #
            # `args(name, value)` is one class for every attribute there is, so
            # counting it as one key made `fillColor` and `strokeColor` look like
            # the same thing. And `position`, `scale`, `align` and `translate`
            # each carry two independent axes: since an effect may now claim one
            # without the other, `moveTo(x=2)` and `moveBy(y=3)` must not look
            # like rivals — they are not, and the whole point of the claim model
            # is that they compose.
            argName = getattr(s, "name", None) if key == "Args" else None
            if argName is not None:
                channels: tuple[str, ...] = (Context.channelKey(key, argName),)
            elif hasattr(s, "x") and hasattr(s, "y"):
                channels = tuple(f"{key}:{c}" for c in ("x", "y") if getattr(s, c) is not None) or (key,)
            else:
                channels = (key,)

            # What this STATEMENT covers, for the editor.
            #
            # A shader on the stack says what happens on a frame; it does not say
            # which line asked for it, and the editor needs that to let you move,
            # shorten or delete an effect by its bar rather than by finding the
            # call yourself. Gathered per apply() — one call is one statement —
            # and the source line is read once at the end, because the walk out
            # of the library costs 2 µs and an animation is hundreds of shaders.
            #
            # Recorded BEFORE `autodestroy`, and that is the whole point. A
            # rotation has not turned by anything on its first frame, so the
            # shader for that frame changes nothing and is dropped — rightly, it
            # would be a write with no effect. But the CALL still covers that
            # frame: `rotateBy(180, duration=1.2)` starts where it says it
            # starts. Counting only what reached the stack drew it one frame
            # late, beside a `scaleTo` of the same length that started on time,
            # and made two things written to happen together look as if they did
            # not.
            for channel in channels:
                span = touched.get(channel)
                if span is None:
                    touched[channel] = [__start, __end]
                else:
                    span[0] = min(span[0], __start)
                    span[1] = max(span[1], __end)

            # FragmentShaders never mutate self, so no copy is needed there.
            # autodestroy() only reads from self (the Input), never mutates s — safe to check
            # before copying so no-op shaders skip the allocation entirely.
            if isinstance(s, VertexShader):
                if s.autodestroy(self):
                    continue
                s = _shallow_copy(s)
                s.modify(self)

            # Args w/ Start & Duration
            #
            # `about` is excluded for the same reason the timing fields are: it
            # is read by the engine, not by C++. Where a turn happens is
            # resolved here — a group orbits its members, a leaf orbits itself —
            # and what crosses is the rotation and the position it produced.
            # Left in, every rotation and scale on the stack grew an `about:
            # null` it had never had, and nine scenes changed the work they ask
            # for without changing a pixel.
            args = {k: v for k, v in vars(s).items() if k not in ("start", "duration", "offset", "about")} | {"start": __start, "duration": __duration}

            # Add step to the stack
            Context.apply(self.meta.index, key, s._type, args)

            # Post-callbacks
            for callback in self.meta.postCallbacks.get(type(s), []):
                callback(s, start, duration, offset if offset is not None else self.meta.transformationOffset)

        if touched:
            # Judged per STATEMENT, not per shader: an animation is n one-frame
            # writes whose last already shows the arrival, so shader by shader
            # every write would look like an instant and a 30-frame fade would
            # settle on 29. A statement that spans one frame takes no time and
            # leaves the cursor on that frame; one that spans more ends at its end.
            first = min(span[0] for span in touched.values())
            last = max(span[1] for span in touched.values())
            Context.cursor = max(Context.cursor, first if last - first <= 1 else last)

            # The cursor this statement counted from, so the editor can write a
            # `start=` for a statement it inserts NEXT to this one: `start` is
            # seconds after the element's own cursor, and nothing in the buffer
            # says where that is.
            Context.noteStatement(
                self.meta.index,
                touched,
                offset if offset is not None else self.meta.transformationOffset,
                self.meta.transformationOffset,
            )

        return self

    def _when(self, at: maybe[sec], offset: maybe[frame]) -> maybe[frame]:
        """`at=`, in seconds of the film, as the `offset=` in frames every verb ends up scheduling with."""
        if at is None:
            return offset
        if offset is not None:
            raise TypeError(
                "at= and offset= both say WHEN, in two units — pass one: "
                "at= in seconds of the film, offset= in frames"
            )
        offset = round(at * FRAMERATE)
        # Vers l'avant, oui ; vers l'arrière, non — pas tant que S1 n'est
        # pas là.
        #
        # Une animation lit sa valeur de départ au moment où la LIGNE est
        # exécutée, pas au moment où elle joue (`moveTo.py:24`). Écrire à une
        # image déjà dépassée par l'horloge de l'élément donne donc une base
        # qui appartient à un instant pas encore arrivé : `moveTo(x=5, at=2)`
        # puis `moveTo(x=2)` mesure 4,99 → 2 dans un ordre et 0 → 2 dans
        # l'autre. `Context.backdatedWrites()` sait le nommer après coup ;
        # ici on peut refuser avant.
        #
        # Backwards `at=` is the backdated write S1 exists to fix: an
        # animation reads its base when the line runs, not when it plays.
        if offset < self.meta.transformationOffset:
            raise ValueError(
                f"at={at}s lands on frame {offset}, behind this element's clock "
                f"(frame {self.meta.transformationOffset}) — the animation would read a "
                f"starting value from a moment that has not happened yet. "
                f"Write it in film order, or wait for S1 (deferred base resolution, "
                f"docs/FEATURES_TODO.md §S1), which is what makes reaching back safe."
            )
        return offset

    def __setattr__(self, name: str, value: Any) -> None:
        """
        Handles attributes updates.

        __setattr__ has priority over __set__.
        """
        # Use object.__getattribute__ to bypass Intefaces's broadcast mechanism — # Old comment to keep for information purpose.

        if type(value) == At:
            value, start, duration, offset = value.unpack()

            if hasattr(self, name) and name in self.cppAttrs:
                if not getattr(self, name) == value:
                    self.apply(args(name, value).at(start=start, duration=duration, offset=offset))
            else:
                # property side effects
                old = self.meta.pendingStart, self.meta.pendingDuration, self.meta.pendingOffset
                new = start, duration, offset

                def pendingOn(i: Input):
                    i.meta.pendingStart, i.meta.pendingDuration, i.meta.pendingOffset = new

                def pendingOff(i: Input):
                    i.meta.pendingStart, i.meta.pendingDuration, i.meta.pendingOffset = old

                self.broadcast(pendingOn)
                try:
                    setattr(self, name, value)
                finally:
                    self.broadcast(pendingOff)
        elif hasattr(self, name) and name in self.cppAttrs:
            if not getattr(self, name) == value:
                self.apply(args(name, value).at(start=self.meta.pendingStart, duration=self.meta.pendingDuration, offset=self.meta.pendingOffset))
        else:
            object.__setattr__(self, name, value)

    def broadcast(self, func: Callable[[Input], Any]):
        """
        Broadcast a method through potential children that the Input might have or itself.

        Will be overriden by Interfaces.
        """
        func(self)

    def __call__(self) -> EaseAttributeSimplifier[Self]:
        return EaseAttributeSimplifier(self)

    def ease(
        self,
        attr: attrName,
        to: Any,
        *,
        easing: easing = Easing.InOut,
        start: sec = 0,
        at: maybe[sec] = None,
        duration: sec = 0.4,
        offset: maybe[frame] = None,
    ) -> Self:
        src = self.__getattribute__(attr)
        offset = self._when(at, offset)

        def _apply(m: number, i: int):
            setattr(self, attr, At(start=start + i * SF, duration=SINGLE_FRAME, offset=offset) | (src + (to - src) * m))

        animate(duration, easing, _apply)
        return self

    def over(
        self,
        *,
        easing: easing = Easing.InOut,
        start: sec = 0,
        at: maybe[sec] = None,
        duration: sec = 0.4,
        offset: maybe[frame] = None,
    ) -> Self:
        """
        Return a proxy for eased attribute animation via assignment — no strings, full autocomplete.

            rect.over(duration=0.6).fillColor = RED_B
            rect.over(start=0.2, duration=0.4).strokeColor = WHITE

        Pyright sees this as returning Self so it validates the assigned value
        against the real property type and provides autocomplete on all attributes.
        Internally fires ``ease()`` per assignment.
        """
        return cast(Self, _Over(self, easing=easing, start=start, duration=duration, offset=self._when(at, offset)))

    def easeTogether(
        self,
        *anims: tuple[attrName, Any] | tuple[attrName, Any, easing],
        easing=Easing.InOut,
        start: sec = 0,
        at: maybe[sec] = None,
        duration: sec = 0.4,
        offset: maybe[frame] = None,
    ) -> Self:
        # Same arrival rule as `rangeIdx`: one frame at least, carrying the destination.
        n = max(1, int(duration * FRAMERATE))
        offset = self._when(at, offset)

        # Snapshot all sources before scheduling anything
        snapshot = {attr: getattr(self, attr) for (attr, _, *_) in anims}

        for i in range(n):
            t = i / (n - 1) if n > 1 else 1.0

            for anim in anims:
                attr, to, *rest = anim
                easingFunc = rest[0] if rest else easing
                src = snapshot[attr]
                m = easingFunc(t)
                setattr(self, attr, At(start=start + i * SF, duration=SINGLE_FRAME, offset=offset) | (src + (to - src) * m))

        return self

    @property
    def ref(self) -> Self:
        """
        Reference to prevent string missmatch
        """
        return cast(Self, AttributeNameReference())

    def addPreCallback[T: IShader](self, shaderType: type[T], callback: Callable[[T, sec, sec, frame], bool]) -> None:
        """
        Register a pre-callback for a shader type. Called before Context.apply; return True to skip the shader.
        """
        cb = cast(Callable[[IShader, sec, sec, frame], bool], callback)
        self.meta.preCallbacks.setdefault(shaderType, []).append(cb)

    def addPostCallback[T: IShader](self, shaderType: type[T], callback: Callable[[T, sec, sec, frame], None]) -> None:
        """
        Track an Input's Shaders and react by doing something else.
        """
        cb = cast(Callable[[IShader, sec, sec, frame], None], callback)
        self.meta.postCallbacks.setdefault(shaderType, []).append(cb)

    def __str__(self) -> str:
        s = f"{self.__class__.__name__}"
        return s

    def __repr__(self) -> str:
        return self.__str__()

    @property
    @abstractmethod
    def width(self) -> wnumber: ...

    @property
    @abstractmethod
    def height(self) -> wnumber: ...

    def _pivot(self) -> v2:
        """
        Where the centre of what is drawn sits, relative to `meta.position`.

        `align` says which point of the box sits AT the position — (0.5, 0.5)
        by default, so zero for nearly everything. A `Letter` is aligned
        (0, 0): its position is the pen, its ink lies right of it and above.
        `_MemberBase` and `Group._anchorOf` read this the way they read a
        group's pivot, so a Text is measured, pivoted and placed on its ink
        rather than on its pens — `Text("LEFT").rotation(180)` used to land
        0.27 right and 0.40 below where it started.
        """
        ax, ay = self.meta.align
        return v2((0.5 - (0.5 if ax is None else ax)) * (self.width or 0), (0.5 - (0.5 if ay is None else ay)) * (self.height or 0))

    def animateIn(self) -> Self:
        return self

    ### Transformations ###

    def position(self, x: maybe[wnumber] = None, y: maybe[wnumber] = None, *, offset: maybe[frame] = None) -> Self:
        return self.apply(position(x, y), offset=offset)

    def translate(self, x: maybe[number] = None, y: maybe[number] = None, *, offset: maybe[frame] = None) -> Self:
        return self.apply(translate(x, y), offset=offset)

    def align(self, x: maybe[wnumber] = None, y: maybe[wnumber] = None) -> Self:
        return self.apply(align(x, y))

    def nextTo(self, other: Input, direction: v2 = RIGHT, *, gap: wnumber = 0.25, follow: bool = False) -> Self:
        """
        Put this beside `other`, `gap` world units apart EDGE TO EDGE and
        centred on it across the other axis::

            label.nextTo(ball, UP, gap=0.2)

        `direction` is `UP`, `DOWN`, `LEFT` or `RIGHT`; a corner (`UR`, `DL`,
        …) applies the gap on both axes. Sizes are the DRAWN ones, so a scaled
        shape is measured as it appears — the same rule as `Row`.

        Placed once, from where `other` is AT THIS LINE: it is a layout, not a
        link. `follow=True`, the label that tracks a moving ball, needs the
        deferred-base pass (S1) and refuses until that lands.
        """
        if follow:
            raise NotImplementedError("nextTo(follow=True) needs S1, the deferred-base pass: until then an input only sees what is written above it")
        from videocode.input.interface.Group import Group
        from videocode.template.input.Layout import _place

        at = Group._anchorOf(other)
        dx, dy = direction.x or 0, direction.y or 0
        _place(self, at.x + dx * ((other.width + self.width) / 2 + gap), at.y + dy * ((other.height + self.height) / 2 + gap))
        return self

    def rotation(self, degree: number) -> Self:
        return self.apply(rotation(degree))

    def scale(self, factor: maybe[number] = None, *, x: maybe[number] = None, y: maybe[number] = None) -> Self:
        if factor is not None:
            x = factor
            y = factor
        return self.apply(scale(x, y))

    def opacity(self, o: uint8) -> Self:
        """
        Set how opaque this `Input` is, 0 (invisible) to 255 (solid):

            square.opacity(0)      # placed, but not yet seen
            square.opacity(128)    # half-transparent
        """
        return self.apply(opacity(o))

    def zIndex(self, z: int, offset: maybe[frame] = None) -> Self:
        return self.apply(zIndex(z), offset=offset)

    def blendMode(self, mode: BlendMode, offset: maybe[frame] = None) -> Self:
        """
        Set how this `Input` composites over what is drawn behind it:
        `BlendMode.NORMAL` (default), `BlendMode.MULTIPLY` (darken),
        `BlendMode.SCREEN` (lighten) or `BlendMode.ADD` (linear dodge, clips
        toward white).

            Rectangle(...).blendMode(BlendMode.MULTIPLY)
        """
        return self.apply(_blendModeShader(mode), offset=offset)

    def matte(self, source: Input, offset: maybe[frame] = None) -> Self:
        """
        Mask this `Input` with `source`'s alpha (track matte): this input is
        only visible where `source` has coverage. `source` is consumed as a
        mask and is NOT drawn separately — e.g. `video.matte(text)` clips the
        video to the text silhouette.
        """
        return self.apply(_matteShader(source), offset=offset)

    def pinToFrame(self, offset: maybe[frame] = None) -> Self:
        """
        Draw this `Input` in FRAME space: the scene `camera` never moves it.

        A caption that zooms with the picture is unreadable, so subtitles, a
        watermark or a lower third opt out of the camera and stay where the
        frame puts them:

            camera.over(duration=1).zoom = 2
            subtitle.pinToFrame()

        Reaches a `Group`'s members, like `background()` does — a group has no
        mesh of its own to excuse.
        """
        self.broadcast(lambda i: i.apply(_pinToFrameShader(), offset=offset))
        return self

    def attachTo(self, path: TrackedPath, offset: maybe[frame] = None) -> Self:
        """
        Follow a `TrackedPath`'s per-frame world position — see
        `Video.track()`.

            text.attachTo(video.track(120, 80))

        Replays the path as one `.position(x, y, offset=trackedFrame +
        (offset or 0))` call per tracked frame — reusing `position()`'s
        existing step-function stack mechanism (each call is an absolute,
        instantaneous override at its frame), so no new C++/Metadata
        plumbing is needed: the per-frame position array `AInput::_metas`
        already indexes by frame.

        `offset` shifts every tracked frame by a constant amount — e.g. if
        the tracked footage's `startFrame` should land at a later point in
        this input's own timeline, pass that frame here.
        """
        base = offset or 0
        for trackedFrame, (x, y) in path:
            self.position(x, y, offset=trackedFrame + base)
        return self

    def inFrontOf(self, other: Input) -> Self:
        """
        Render directly in front of `other`.
        """
        return self.zIndex(other.meta.zIndex)

    def behind(self, other: Input) -> Self:
        """
        Render directly behind `other`.
        """
        return self.zIndex(other.meta.zIndex - 1)

    def bringToFront(self) -> Self:
        """
        Render in front of every other `Input` in the scene.
        """
        return self.zIndex(Context.maxZIndex())

    def sendToBack(self) -> Self:
        """
        Render behind every other `Input` in the scene.
        """
        # Clamped to 0: zIndex -1 is reserved for the background
        # (see BACKGROUND_Z_INDEX / Input.background()).
        return self.zIndex(max(0, Context.minZIndex() - 1))

    def bringForward(self) -> Self:
        """
        Move one layer towards the front, swapping places with whatever is
        directly in front. No-op if already frontmost.
        """
        above = Context.zIndexAbove(self.meta.zIndex)
        if above is None:
            return self
        return self.zIndex(above)

    def sendBackward(self) -> Self:
        """
        Move one layer towards the back, swapping places with whatever is
        directly behind. No-op if already backmost.
        """
        below = Context.zIndexBelow(self.meta.zIndex)
        if below is None:
            return self
        # Clamped to 0: zIndex -1 is reserved for the background
        # (see BACKGROUND_Z_INDEX / Input.background()).
        return self.zIndex(max(0, below - 1))

    def background(self, offset: maybe[frame] = None) -> Self:
        """
        Mark this `Input` (and any children) as part of the scene background:
        sets `zIndex` to `BACKGROUND_Z_INDEX` (-1).

        Excluded from relative layer-order queries (bringToFront, sendToBack,
        bringForward, sendBackward), so they never get pushed behind/in front
        of the background by accident. Relative order between background
        elements (e.g. Plane's grid lines on top of its backdrop rectangle)
        is preserved by zOrderSeq, since they all tie at -1.
        """
        self.broadcast(lambda i: i.zIndex(BACKGROUND_Z_INDEX, offset=offset))
        return self

    def hide(self, start: sec = 0, at: maybe[sec] = None):
        return self.apply(hide().at(start=start), at=at)

    def show(self, start: sec = 0, at: maybe[sec] = None):
        return self.apply(show().at(start=start), at=at)

    ### Template ###

    @_rebasing
    def moveTo(self, x: maybe[number] = None, y: maybe[number] = None, easing: easing = Easing.InOut, start: sec = 0, at: maybe[sec] = None, duration: sec = 0.4) -> Self:
        return self.apply(*moveTo(self, x=x, y=y, easing=easing, start=start, duration=duration), at=at)

    def moveAlong(self, path: Any, *, easing: easing = Easing.InOut, start: sec = 0, at: maybe[sec] = None, duration: sec = 1.2, face: bool = False) -> Self:
        """
        Travel a path at an even speed — `face=True` also turns along it.

            ball.moveAlong(Curve([(-6, -2), (0, 2), (6, -2)]), duration=2)

        Measured by LENGTH, not by the path's points: they are dense where a
        curve bends and sparse where it runs straight, and stepping from one to
        the next crawls through the corners. See
        `videocode.template.effect.core.moveAlong`.
        """
        return self.apply(*moveAlong(self, path, easing=easing, start=start, duration=duration, face=face), at=at)

    @_rebasing
    def moveBy(self, x: maybe[number] = None, y: maybe[number] = None, easing: easing = Easing.InOut, start: sec = 0, at: maybe[sec] = None, duration: sec = 0.4) -> Self:
        return self.apply(*moveBy(self, x=x, y=y, easing=easing, start=start, duration=duration), at=at)

    @_rebasing
    def fadeIn(self, *, easing: easing = Easing.InOut, start: sec = 0, at: maybe[sec] = None, duration: sec = 0.4, from0: maybe[bool] = True, hidden: bool = True) -> Self:
        """
        Fade this element in over `duration` seconds.

        `hidden` keeps it invisible for the whole time BEFORE the fade, so the
        `.opacity(0)` every scene used to open with is no longer needed:

            title = Text("Hello")
            title.fadeIn(start=1)        # nothing on screen until second 1

        It stands down by itself unless the element is still fully opaque and
        nothing ever touched its opacity — an element the author dimmed, or
        that faded out earlier, keeps what it had. `hidden=False` never hides.
        """
        if hidden and not self._opacityWritten() and self._opacityNow() == 255:
            # From the first frame of the film, not from this element's clock:
            # after a `waitFor()` the clock is already at the fade, and the
            # element stood fully opaque for the whole wait it was meant to be
            # hidden. An element made after a `wait()` is hidden until then
            # anyway, so frame 0 is never too early.
            mark = len(Context.statements)
            self.apply(opacity(0), offset=0)
            # The library's hiding, not the author's fade: left in, the bar of
            # this `fadeIn` would start where the element was made.
            for statement in Context.statements[mark:]:
                statement["placement"] = True
        return self.apply(*fadeTo(self, src=0 if from0 else None, dst=255, easing=easing, start=start, duration=duration), at=at)

    def _opacityWritten(self) -> bool:
        return self.placed and any(st["input"] == self.meta.index and "Opacity" in st["keys"] for st in Context.statements)

    def _opacityNow(self) -> float:
        if not self.placed:
            return 255
        return float(Context.stateAt(self.meta.index, self.meta.lastAffectedFrame).get("Opacity", 255))

    @_rebasing
    def fadeOut(self, *, easing: easing = Easing.InOut, start: sec = 0, at: maybe[sec] = None, duration: sec = 0.4, hide: bool = False, from255: maybe[bool] = True) -> Self:
        """
        Fade this element out over `duration` seconds.

            title.fadeOut()                      # now, on this element's clock
            clip.fadeOut(at=clip.end - 0.4)      # so the fade ENDS with the clip

        `start=` counts from the element's own clock, `at=` from the start of
        the film. `hide=True` also hides it once the fade is over, which ends
        its clip on the timeline instead of leaving it there at opacity 0.
        """
        self.apply(*fadeTo(self, src=255 if from255 else None, dst=0, easing=easing, start=start, duration=duration), at=at)
        if hide:
            return self.hide(start=start + duration, at=at)
        return self

    @_rebasing
    def fadeTo(self, o: uint8, *, easing: easing = Easing.InOut, start: sec = 0, at: maybe[sec] = None, duration: sec = 0.4) -> Self:
        """
        Fade to an opacity, 0–255, from wherever it stands.

            photo.fadeTo(80)             # dimmed, not gone
            photo.fadeTo(255, at=4.2)    # back, starting at 4.2 s of the film
        """
        return self.apply(*fadeTo(self, dst=o, easing=easing, start=start, duration=duration), at=at)

    @_rebasing
    def scaleTo(
        self,
        factor: maybe[number] = None,
        *,
        x: maybe[number] = None,
        y: maybe[number] = None,
        easing: easing = Easing.InOut,
        start: sec = 0,
        at: maybe[sec] = None,
        duration: sec = 0.4,
        about: maybe[v2] = None,
    ) -> Self:
        if factor is not None:
            x = factor
            y = factor
        return self.apply(*scaleTo(self, x=x, y=y, easing=easing, start=start, duration=duration, about=about), at=at)

    @_rebasing
    def scaleBy(
        self,
        factor: maybe[number] = None,
        *,
        x: maybe[number] = None,
        y: maybe[number] = None,
        easing: easing = Easing.InOut,
        start: sec = 0,
        at: maybe[sec] = None,
        duration: sec = 0.4,
        about: maybe[v2] = None,
    ) -> Self:
        if factor is not None:
            x = factor
            y = factor
        return self.apply(*scaleBy(self, x=x, y=y, easing=easing, start=start, duration=duration, about=about), at=at)

    @_rebasing
    def rotateTo(self, degree: number, *, easing: easing = Easing.InOut, start: sec = 0, at: maybe[sec] = None, duration: sec = 0.4, about: maybe[v2] = None) -> Self:
        """
        Turn to an absolute angle. `about` places the pivot in world units;
        without one a group turns around the point its `align` derives.
        """
        return self.apply(*rotateTo(self, dst=degree, easing=easing, start=start, duration=duration, about=about), at=at)

    @_rebasing
    def rotateBy(self, degree: number, *, easing: easing = Easing.InOut, start: sec = 0, at: maybe[sec] = None, duration: sec = 0.4, about: maybe[v2] = None) -> Self:
        """
        Turn by an angle relative to the current one — see `rotateTo` for `about`.
        """
        return self.apply(*rotateBy(self, dst=degree, easing=easing, start=start, duration=duration, about=about), at=at)

    @_rebasing
    def alignTo(self, x: maybe[number] = None, y: maybe[number] = None, easing: easing = Easing.InOut, start: sec = 0, at: maybe[sec] = None, duration: sec = 0.4) -> Self:
        return self.apply(*alignTo(self, x=x, y=y, easing=easing, start=start, duration=duration), at=at)
