#!/usr/bin/env python3

from __future__ import annotations

import math
from copy import copy as _shallow_copy
from typing import Any
from typing_extensions import TypeVar
from videocode.input.input import *
from videocode.input.interface.Interface import Interface
from videocode.shader.ishader import Effect, GroupEffect

_GROUP_T = TypeVar("_GROUP_T", bound=Input, default=Input)


def _derivedPositionFrames() -> dict[int, set[int]]:
    """
    Which frames of which input hold a position a GROUP worked out.

    `Context.statements` already records, per statement, whether it was derived
    and what it covered — the editor needs that — so telling a member's own
    animation from a parent's working-out costs a pass over a table that is
    already kept, and nothing new has to be written down.
    """
    out: dict[int, set[int]] = {}
    for st in Context.statements:
        if not st["derived"]:
            continue
        for name, span in st["keys"].items():
            if name.startswith("Position"):
                out.setdefault(st["input"], set()).update(range(span[0], span[1] + 1))
    return out


def _ownPositions(member: Input, derived: dict[int, set[int]]) -> dict[int, v2]:
    """
    Every position a member wrote for ITSELF, by frame.

    An axis absent from a frame is a hole meaning "leave that channel alone",
    so it carries from the frame before — the same rule C++ reads the stack by.
    """
    if member.composite:
        return {}
    index = member.meta.index
    skip = derived.get(index, set())
    frames = Context.stack.get(index, {})
    track: dict[int, v2] = {}
    x = y = None
    for f in sorted(frames):
        # -1 is the creation entry, not a moment.
        if f < 0 or f in skip:
            continue
        entry = frames[f].get("Position")
        if entry is None:
            continue
        args = entry["args"]
        x = args["x"] if args.get("x") is not None else x
        y = args["y"] if args.get("y") is not None else y
        if x is not None and y is not None:
            track[f] = v2(float(x), float(y))
    return track


class _MemberBase:
    """
    A member as it stood when the group was formed.

    `width` and `height` are frozen here for the same reason the position is:
    the pivot is measured from them, and a pivot measured from LIVE members is a
    pivot that moves while it is being used. `Group.width` reads
    `inp.meta.position` of its members, so once a rotation has started moving
    them, the box the pivot is sampled from is the box the rotation has already
    produced — the transform derives its centre from its own result.

    Measured on `Group(Group(a, b), c).rotateBy(90)`: the outer pivot went from
    (0.25, 0) before the animation to (0.50, 0) after, and `_emitRigid` asks for
    it on every emission.
    """

    #: Blender's `matrix_parent_inverse`: the standing correction between where
    #: the parent wants this member and what the member reads as its position.
    #: Zero for a leaf, whose position IS a location.
    #:
    #: A group is not AT its `meta.position`: that field is a displacement it
    #: adds to members it holds around its own pivot, so zero means "wherever
    #: they already are", not the origin. Reading it as a location made a
    #: parent turn a point its child's content was not at, and the formation
    #: came apart — `Group(Group(a, b), c).rotateBy(90)` left the squares
    #: 1 / 0.707 / 1.581 apart when they had started 1 / 1 / 2.
    #:
    #: So the base position of a member group is its pivot plus that
    #: displacement, and `_emitRigid` hands the correction back. As a stored
    #: number rather than a branch: "leaf or group?" was asked at every
    #: emission to answer a question whose answer never changes, and a zero
    #: subtracts as correctly as a skipped subtraction.
    parentInverse: v2

    def __init__(self, member: Input, derived: maybe[dict[int, set[int]]] = None) -> None:
        meta = member.meta
        #: The member's OWN position, frame by frame, as it stood when the group
        #: was formed. A group transform used to write over it — measured at 29
        #: frames of 30 — because it only ever knew the member's final position
        #: and orbited that. Composing means orbiting where the member had put
        #: ITSELF at that frame.
        self.ownTrack = _ownPositions(member, derived if derived is not None else {})
        self.ownFrames = sorted(self.ownTrack)
        pivotOf = getattr(member, "_pivot", None)
        self.parentInverse = cast(v2, pivotOf()) if callable(pivotOf) else v2(0.0, 0.0)
        #: A leaf spins and scales about its aligned point, not about its ink,
        #: so its correction turns with it — see `_emitRigid`.
        self.leaf = not isinstance(member, Group)
        self.position = self.parentInverse + v2(*meta.position)
        self.rotation = meta.rotation
        self.scale = v2(*meta.scale)
        self.width = member.width
        self.height = member.height

    def at(self, frame: int) -> v2:
        """Where the member had put itself by this frame; its frozen base if never."""
        held = None
        for f in self.ownFrames:
            if f > frame:
                break
            held = f
        return self.ownTrack[held] if held is not None else self.position


class Group(Interface, Generic[_GROUP_T]):
    # fmt: off
    """
    A `Group` contains many inputs. Position, rotation and scale transforms
    applied to the group use orbital rigid-body math — members pivot together
    around the group's `align` anchor — while other shaders (color, opacity,
    etc.) broadcast as-is to all members.

    Also used to create bigger things that link many Inputs.
    You create a class that inherits from `Group`, setup your things and then super().__init__().

    Member states are frozen at the moment the group is created. Call
    `_regroup()` to re-snapshot after members have been individually repositioned.
    """
    # fmt: on

    #: Tells one group's derivations from another's in `Context.statements`.
    #: A subclass that never calls `super().__init__()` keeps 0 and behaves as
    #: before — all such groups share an identity, which is what the old
    #: boolean did for every group.
    _serial: int = 0
    _groupId: int = 0

    def __init__(self, *inputs: Input):
        Group._serial += 1
        self._groupId = Group._serial
        self.inputs: list[_GROUP_T] = cast(list[_GROUP_T], list(inputs))
        self._snapshot()

    # ------------------------------------------------------------------
    # Snapshot / pivot helpers

    def _snapshot(self) -> None:
        """Snapshot current member position/rotation/scale as the rigid-body base."""
        derived = _derivedPositionFrames()
        self._memberBases: list[tuple[Input, _MemberBase]] = [(m, _MemberBase(m, derived)) for m in self.inputs]
        # Per-frame rigid state recorded during the current time window, keyed by
        # relative frame (round(start * FRAMERATE)). It is what lets concurrent
        # chained rigid animations — `g.rotateBy(...).scaleTo(...)` — combine:
        # a member's position at a frame depends on the group's position AND
        # rotation AND scale at that frame, and the passes are written one after
        # another while the frames they cover overlap.
        #
        # Nothing is emitted while a pass runs. The whole timeline is emitted
        # once the call is over, because a pass can change frames an earlier pass
        # already answered for: `rotateBy(180, duration=1.5)` writes 45 frames of
        # orbit at scale 1, then `scaleTo(0.5, duration=0.5)` halves the group for
        # every frame from its 15th onwards — including the 30 the rotation had
        # already emitted. Emitting as we went left those 30 on the old orbit, so
        # the members shrank for half a second and then jumped back out to twice
        # the radius in one frame.
        self._rigidTimeline: dict[int, dict[str, Any]] = {}
        # What the last emission wrote, so an identical repeat costs nothing.
        self._rigidWritten: tuple = ()

    def _regroup(self) -> None:
        """Re-snapshot member bases from their current meta (call after layout changes)."""
        self._snapshot()

    #: The channels a group's rigid state is made of — one per independent
    #: number, exactly like a leaf's. `pos` and `scl` carry two axes each and an
    #: effect may claim one without the other, and `align` is here because it
    #: decides the PIVOT: a pivot is what every emission was computed from, so a
    #: later `align` must not reach back and change frames already written.
    #:
    #: `about` is the author's answer to the same question `align` asks: it
    #: names the pivot outright instead of deriving it from the bounding box.
    #: On the timeline for the same reason `align` is — a pivot is what every
    #: emission was computed from, so placing one must not reach back into
    #: frames already written.
    _RIGID_CHANNELS = ("pos.x", "pos.y", "rot", "scl.x", "scl.y", "align.x", "align.y", "about.x", "about.y", "pivot.x", "pivot.y")

    def _rigidDefaults(self) -> dict[str, Any]:
        """Where each channel stands when the timeline says nothing about it."""
        return {
            "pos.x": self.meta.position.x, "pos.y": self.meta.position.y,
            "rot": self.meta.rotation,
            "scl.x": self.meta.scale.x, "scl.y": self.meta.scale.y,
            "align.x": self.meta.align.x, "align.y": self.meta.align.y,
            # No author-placed pivot until one is asked for; the group falls
            # back to the point `align` derives.
            "about.x": None, "about.y": None,
            # Resolved when the frame is RECORDED, not when it is emitted — see
            # `_recordPivot`. None means no record ever carried one, and the
            # emission falls back to asking.
            "pivot.x": None, "pivot.y": None,
        }

    @staticmethod
    def _assemble(channels: dict[str, Any]) -> dict[str, Any]:
        """Channels back into the shape `_emitRigid` reads."""
        return {
            "pos": v2(channels["pos.x"], channels["pos.y"]),
            "rot": channels["rot"],
            "scl": v2(channels["scl.x"], channels["scl.y"]),
            "align": v2(channels["align.x"], channels["align.y"]),
            "about": None if channels["about.x"] is None else v2(channels["about.x"], channels["about.y"]),
            "pivot": None if channels["pivot.x"] is None else v2(channels["pivot.x"], channels["pivot.y"]),
        }

    def _pivot(self, align: maybe[v2] = None, about: maybe[v2] = None) -> v2:
        """
        Pivot point in member-base space.

        `about` is the point the author placed, and it wins outright: it is a
        location, not a question about the content, so an empty group has one
        just as much as a full one.

        Otherwise the group's alignment answers — default align (0.5, 0.5) =
        center of the bounding box. This is the point that stays fixed when the
        group is rotated or scaled.

        `align` is the alignment for the frame being emitted, which is not always
        the group's current one — see `_RIGID_CHANNELS`.
        """
        if about is not None:
            return v2(about.x, about.y)
        if not self._memberBases:
            return v2(0.0, 0.0)
        ax, ay = align if align is not None else self.meta.align
        # Frozen extents, not live ones — see `_MemberBase`.
        lefts = [base.position.x - base.width / 2 for _, base in self._memberBases]
        rights = [base.position.x + base.width / 2 for _, base in self._memberBases]
        bots = [base.position.y - base.height / 2 for _, base in self._memberBases]
        tops = [base.position.y + base.height / 2 for _, base in self._memberBases]
        return v2(
            min(lefts) + ax * (max(rights) - min(lefts)),
            min(bots) + ay * (max(tops) - min(bots)),
        )

    # ------------------------------------------------------------------
    # Rigid-body emission

    def _recordPivot(self, rec: dict[str, Any], align: v2, about: maybe[v2]) -> None:
        """
        Write the pivot this frame was computed with, as a number.

        `_pivot` is a function of the member bases, and the bases move: every
        `_regroup()` re-measures them, and `_emitTimeline` re-emits the whole
        window on each pass. Asking again at emission meant a frame written
        before a re-snapshot could be re-written afterwards around a different
        point — the transform deriving its centre from its own result, one pass
        removed. A resolved number cannot drift.
        """
        point = self._pivot(align, about)
        rec["pivot.x"], rec["pivot.y"] = point.x, point.y

    def _memberPivots(self, pivot: v2) -> maybe[list[v2]]:
        """
        One pivot per member, or None to turn the whole group around `pivot`.

        None is the answer for every group but a `Text` asked for a finer
        anchor grouping, and it is not the same as a list of identical pivots:
        it says the question was never split.
        """
        return None

    def _stateAt(self, at: int) -> dict[str, Any]:
        """
        The group's position, rotation and scale at a frame.

        Each component is the last value it was given at or before that frame;
        before its first, the value the animation started from; and with nothing
        recorded at all, whatever the group's meta says.
        """
        channels = self._rigidDefaults()
        seen: set[str] = set()

        for f in sorted(self._rigidTimeline):
            rec = self._rigidTimeline[f]
            for key in Group._RIGID_CHANNELS:
                if key not in rec:
                    continue
                # Before its first record, a channel is whatever that first
                # record says: an animation starts from where the group already
                # was.
                if f > at and key in seen:
                    continue
                channels[key] = rec[key]
                seen.add(key)

        return Group._assemble(channels)

    def _emitRigid(
        self,
        start: sec,
        duration: sec,
        offset: maybe[frame],
        *,
        pos: bool = False,
        rot: bool = False,
        scl: bool = False,
        state: maybe[dict[str, Any]] = None,
    ) -> None:
        """
        Emit concrete position/rotation/scale shaders to each member, applying the
        group transform on top of each member's frozen base.

        `state` is the transform to use; without one the group's state at that
        frame is worked out from the timeline, which is what a caller outside the
        rigid passes — `Text.alignLetters` — wants.
        """
        if state is None:
            state = self._stateAt(round(start * FRAMERATE))
        if not self._memberBases:
            return

        gx, gy = state["pos"]
        grot_deg = state["rot"]
        gscale = state["scl"]

        C = self._pivot(state.get("align"), state.get("about"))
        # One pivot for the whole group is the default and the only thing this
        # engine could express; a subclass may hand back one per member instead
        # — see `Text.anchor`, where a letter has no downstream identity to
        # parent to and its pivot has to be a rule resolved here, at emission.
        # The frame carries its own pivot when one was recorded with it; asking
        # again is the fallback for a caller outside the rigid passes.
        recorded = state.get("pivot")
        C = C if recorded is None else recorded
        groupPivot = C
        # A point the author placed is an answer, and it is the whole answer:
        # it outranks any per-member rule a subclass would otherwise apply.
        pivots = None if state.get("about") is not None else self._memberPivots(C)
        # C++ renders a positive degree as a clockwise spin on screen (the
        # rotation matrix is applied in pixel space, which is Y-flipped vs
        # world space) — the orbit must turn the same way or members shear
        # apart from their own spin.
        rad = math.radians(-grot_deg)
        cos_r = math.cos(rad)
        sin_r = math.sin(rad)

        for index, (m, base) in enumerate(self._memberBases):
            shaders: list[IShader] = []
            C = pivots[index] if pivots is not None else groupPivot

            if pos or scl:
                # Member offsets scale with the group (rigid scaling) and
                # rotate with it — a scale change moves off-pivot members too.
                # The member's own timeline, composed with the group's rather
                # than replaced by it: `at` gives where the member had put
                # itself on this frame, and the group turns THAT.
                local = base.at(round(start * FRAMERATE) + (offset if offset is not None else m.meta.transformationOffset))
                rx = (local.x - C.x) * gscale.x
                ry = (local.y - C.y) * gscale.y
                wx = rx * cos_r - ry * sin_r + C.x + gx
                wy = rx * sin_r + ry * cos_r + C.y + gy
                # A member group reads a position as a displacement from its own
                # pivot; a leaf reads it as a location — see
                # `_MemberBase.parentInverse`. A leaf whose ink is off its
                # aligned point (a letter: align (0, 0), the pen at the corner)
                # then spins and scales about that point, so the correction
                # handed back is the offset AS IT WILL STAND after the leaf's
                # own turn, or the ink ends up a glyph away from the orbit.
                px, py = base.parentInverse.x, base.parentInverse.y
                if base.leaf and (px or py):
                    px *= (base.scale.x + gscale.x - 1) / base.scale.x if base.scale.x else 1
                    py *= (base.scale.y + gscale.y - 1) / base.scale.y if base.scale.y else 1
                    lrad = math.radians(-(base.rotation + grot_deg))
                    px, py = px * math.cos(lrad) - py * math.sin(lrad), px * math.sin(lrad) + py * math.cos(lrad)
                shaders.append(position(wx - px, wy - py))

            if rot:
                shaders.append(rotation(base.rotation + grot_deg))

            if scl:
                shaders.append(scale(*(base.scale + gscale - v2(1.0, 1.0))))

            if shaders:
                # Marked as the group's own working-out, not as a line about this
                # member — see `Context.deriving`.
                wasDeriving, wasGroup = Context.deriving, Context.derivingGroup
                Context.deriving, Context.derivingGroup = True, self._groupId
                try:
                    m.apply(*shaders, start=start, duration=duration, offset=offset)
                finally:
                    Context.deriving, Context.derivingGroup = wasDeriving, wasGroup

    # ------------------------------------------------------------------
    # Interface

    # A group has no slot of its own, so what `fadeIn` asks before hiding is
    # asked of the members: a `Text` the author dimmed is five letters that were.
    def _opacityWritten(self) -> bool:
        return any(i._opacityWritten() for i in self.inputs)

    def _opacityNow(self) -> float:
        return min((i._opacityNow() for i in self.inputs), default=255)

    def __iter__(self):
        for i in self.inputs:
            yield i

    def broadcast(self, func: Callable[[Input], Any]):
        for child in self.inputs:
            child.broadcast(func)

    def apply(self, *shaders: IShader | Effect | GroupEffect, start: sec = 0, duration: sec = SINGLE_FRAME, offset: maybe[frame] = None, at: maybe[sec] = None) -> Self:
        # A group built empty and filled afterwards — `Text.find` does exactly
        # that: `Group()` then `.inputs.append(...)` — never got its bases, so
        # `_emitRigid` returned at once and `find("12").moveBy(y=1)` did nothing
        # at all, without an error. Seven groups in the corpus are in that state.
        # Count, not emptiness. `not self._memberBases` only caught the group
        # built empty and filled later; a group built with three members and
        # then appended to kept its three bases, and the appended member was
        # invisible to every rigid transform — it did not move, did not turn,
        # and nothing said so. `videocode/template/misc/example/marius.py:55`
        # is in exactly that state.
        # ponytail: a member REPLACED one-for-one keeps the count and is still
        # missed; compare identities if that ever happens.
        if len(self.inputs) != len(self._memberBases):
            self._snapshot()

        # `at=` never reached a rigid transform: `Group(a, b).scaleTo(1.1, at=5)`
        # landed on the members' cursor, where a plain shape lands on second 5.
        offset, at = self._when(at, offset), None

        # Members at DIFFERENT cursors are not at the same instant, and a rigid
        # transform is only rigid if they are: `a.fadeIn(); a.flush()` then
        # `Group(a, b).moveBy(x=5)` moved `a` over frames 30-59 and `b` over 0-29,
        # stretching the pair from 2.0 to 7.0 apart for a whole second before it
        # snapped back. A group has no cursor of its own — `meta.transformationOffset`
        # is never read — so it takes the latest of its members'.
        #
        # Two conditions, both learnt the hard way. Only when they disagree:
        # taking `max()` unconditionally breaks the order-independence of chained
        # rigid transforms, and four of `group_test.py`'s invariants fail. And
        # read THROUGH `Context.waitOffset`: a global `wait()` is applied inside
        # `Input.apply`, after this runs, so comparing the raw cursors saw a
        # disagreement the wait was about to settle — pinning `offset` here then
        # overrode the wait, and `scene.py`'s group landed on frame 36 instead
        # of 57, fighting the circle's own `moveBy`.
        if offset is None and len(self.inputs) > 1:
            lo = hi = -1

            def seen(i: Input) -> None:
                nonlocal lo, hi
                o = max(i.meta.transformationOffset, Context.waitOffset)
                lo, hi = (o, o) if lo < 0 else (min(lo, o), max(hi, o))

            self.broadcast(seen)
            if lo != hi:
                offset = hi

        rigid = False
        for s in shaders:
            if isinstance(s, GroupEffect):
                # Group-scoped effect: gets the group itself. What it does only
                # means something across the members — a fill sweeping a Text
                # travels over the WORD, and a letter has no idea where it sits
                # in one. e.g. g.apply(fillIn(GOLD))
                self.apply(*s(self), start=start, duration=duration, offset=offset, at=at)
                continue

            if not isinstance(s, IShader):
                # Member-aware effect: Group dispatches it per-child, letting the
                # effect read each member's own state (scale, fillColor, …).
                # e.g. g.apply(highlight(color=YELLOW))
                for child in self.inputs:
                    child.apply(*s(child), start=start, duration=duration, offset=offset, at=at)
                continue

            # Keep group.meta current even though groups never push to C++.
            # Subclasses and external code read group.meta.* directly —
            # e.g. Text.alignLetters reads self.meta.align.x, or user code
            # inspects text.meta.position to query the group's current logical state.
            # Groups are otherwise stateless — children own the rendering state.
            # Read before `modify` moves it: an `align` that lands mid-window
            # needs to put the alignment it REPLACES on the timeline, or the
            # frames before it would be repainted with the new pivot.
            previousAlign = v2(*self.meta.align)
            if isinstance(s, VertexShader):
                _shallow_copy(s).modify(self)

            k = s._rigidKind
            if k:
                # Resolve the shader's own timing (.at(start=t) per animation frame)
                # before recording — each frame in a moveTo animation carries its own t.
                ts, td, to = s.resolve(start, duration, offset)
                # Read before the record for this frame exists: a pivot placed
                # after frames have already been written must not be handed back
                # to them. The fold carries a channel backward from its FIRST
                # record, so the opening frame has to say "no placed pivot here"
                # out loud — the same rewrite `align` had to be taught about.
                about = getattr(s, "about", None)
                if about is not None and self._rigidTimeline and not any(k.startswith("about.") for f in self._rigidTimeline for k in self._rigidTimeline[f]):
                    opening = self._rigidTimeline[sorted(self._rigidTimeline)[0]]
                    opening.setdefault("about.x", None)
                    opening.setdefault("about.y", None)
                    if "pivot.x" not in opening:
                        self._recordPivot(opening, v2(*self.meta.align), None)

                rec = self._rigidTimeline.setdefault(round(ts * FRAMERATE), {})
                rec["t"] = (ts, td, to)
                if about is not None:
                    rec["about.x"] = float(about.x)
                    rec["about.y"] = float(about.y)
                self._recordPivot(rec, v2(*self.meta.align), about)
                # Only the components the shader CLAIMED, for the same reason a
                # leaf records only those: `g.moveTo(x=2)` followed by
                # `g.moveBy(y=3, start=0.5)` used to make x jump to its
                # destination the instant the y animation began writing —
                # the bug of the leaves, one level up.
                claimsX = getattr(s, "x", None) is not None
                claimsY = getattr(s, "y", None) is not None
                if k == 1:
                    if claimsX:
                        rec["pos.x"] = self.meta.position.x
                    if claimsY:
                        rec["pos.y"] = self.meta.position.y
                elif k == 2:
                    rec["rot"] = self.meta.rotation
                else:
                    if claimsX:
                        rec["scl.x"] = self.meta.scale.x
                    if claimsY:
                        rec["scl.y"] = self.meta.scale.y
                rigid = True
            else:
                # `align` is not a rigid transform — it broadcasts to the members
                # like any other shader, and that stays. But it ALSO moves the
                # group's pivot, and a pivot is what every emission was computed
                # from: applied between two rotations, it used to reach back and
                # rewrite frames that had already been written. Recorded on the
                # timeline, each frame keeps the pivot it was emitted with.
                #
                # Only while a timeline exists — a lone `align` on an unanimated
                # group has nothing to reach back into, and should stay the plain
                # broadcast it has always been.
                if isinstance(s, align) and self._rigidTimeline:
                    ts, td, to = s.resolve(start, duration, offset)
                    written = sorted(self._rigidTimeline)

                    # The alignment this one REPLACES belongs on the timeline
                    # first. The fold carries a channel backward from its first
                    # record — that is how an animation starts from where the
                    # group already was — so without this, an `align` written at
                    # frame 15 would hand its pivot to frames 0 through 14 as
                    # well, which is the retroactive rewrite being fixed.
                    if not any(k.startswith("align.") for f in written for k in self._rigidTimeline[f]):
                        opening = self._rigidTimeline[written[0]]
                        opening.setdefault("align.x", previousAlign.x)
                        opening.setdefault("align.y", previousAlign.y)
                        if "pivot.x" not in opening:
                            self._recordPivot(opening, previousAlign, None)

                    rec = self._rigidTimeline.setdefault(round(ts * FRAMERATE), {})
                    rec.setdefault("t", (ts, td, to))
                    if s.x is not None:
                        rec["align.x"] = float(s.x)
                    if s.y is not None:
                        rec["align.y"] = float(s.y)
                    self._recordPivot(rec, v2(rec.get("align.x", self.meta.align.x), rec.get("align.y", self.meta.align.y)), None)
                    rigid = True
                # All other shaders (color, opacity, args, translate, hide, …) broadcast
                # as-is to every member. i.apply() makes its own shallow copy for
                # VertexShaders before calling modify(), so passing s directly is safe.
                for i in self.inputs:
                    i.apply(s, start=start, duration=duration, offset=offset, at=at)

        if rigid:
            self._emitTimeline()

        return self

    def _emitTimeline(self) -> None:
        """
        Write every frame the timeline knows about, with the group's state AT that
        frame — the last value each component was given at or before it.

        Carried FORWARD because a transform holds until the next one: the scale a
        half-second animation lands on is the scale of every frame after it, and
        the members' orbit has to keep using it. Carried BACKWARD from the first
        record for frames an animation has not reached yet, since an animation
        starts from the value the group already had.

        Re-emitting is safe by construction: the stack keys a frame's entry by
        shader name, so writing frame 30's position twice replaces it rather than
        stacking two.
        """
        if not self._rigidTimeline:
            return

        frames = sorted(self._rigidTimeline)

        def firstOf(key: str, fallback: Any) -> Any:
            for f in frames:
                if key in self._rigidTimeline[f]:
                    return self._rigidTimeline[f][key]
            return fallback

        defaults = self._rigidDefaults()
        channels = {key: firstOf(key, defaults[key]) for key in Group._RIGID_CHANNELS}

        # Walk it once to know what would be written, and say nothing if that is
        # what was written last time.
        #
        # A group's `apply` runs far more often than a scene has animations — a
        # Text dispatches one per letter, 42 calls for two transforms — and
        # rewriting the whole window on each of them turned a two-transform Text
        # from 9 ms into 140. Skipping an IDENTICAL repeat is safe in a way that
        # skipping individual frames is not: a member's `autodestroy` drops a
        # shader that matches the member's current meta, so the meta trajectory
        # has to stay exactly what it would have been. A repeat re-walks the same
        # values in the same order and ends where it started; dropping it changes
        # nothing at all.
        plan: list[tuple[int, dict[str, Any], bool, bool]] = []
        for f in frames:
            rec = self._rigidTimeline[f]
            for key in Group._RIGID_CHANNELS:
                if key in rec:
                    channels[key] = rec[key]
            plan.append((f, Group._assemble(channels), "rot" in rec, "scl.x" in rec or "scl.y" in rec))

        signature = tuple(
            (f, float(st["pos"].x), float(st["pos"].y), float(st["rot"]),
             float(st["scl"].x), float(st["scl"].y),
             float(st["align"].x), float(st["align"].y), r, sc)
            for f, st, r, sc in plan
        )
        if signature == self._rigidWritten:
            return
        self._rigidWritten = signature

        for f, st, withRot, withScl in plan:
            ts, td, to = self._rigidTimeline[f]["t"]
            # Position is emitted for every frame — it is the one thing that
            # depends on all three — while rotation and scale are only written
            # where they actually change.
            self._emitRigid(ts, td, to, pos=True, rot=withRot, scl=withScl, state=st)

    # Advancing the time window (flush / wait / waitTo / waitFor) invalidates the
    # rigid timeline: its keys are frames relative to the members' transformation
    # offset, so a new window would collide with (and wrongly reuse) old entries.

    def flush(self) -> Self:
        self._rigidTimeline.clear()
        self._rigidWritten = ()
        return super().flush()

    def waitTo(self, n: frame) -> Self:
        self._rigidTimeline.clear()
        self._rigidWritten = ()
        return super().waitTo(n)

    def wait(self, n: sec) -> Self:
        self._rigidTimeline.clear()
        self._rigidWritten = ()
        return super().wait(n)

    def waitFor(self, i: Input) -> Self:
        self._rigidTimeline.clear()
        self._rigidWritten = ()
        return super().waitFor(i)

    def waitForOthers(self) -> Self:
        """Advance this group to the latest `lastAffectedFrame` among all members."""
        frames: list[int] = []

        def collect(i: Input) -> None:
            if isinstance(i, Interface):
                i.broadcast(collect)
            else:
                frames.append(i.meta.lastAffectedFrame)

        self.broadcast(collect)
        if not frames:
            return self
        return self.waitTo(max(frames))

    @staticmethod
    def _anchorOf(inp: Input) -> v2:
        """Where an input's content sits — for a group, not its `meta.position`."""
        p = v2(inp.meta.position.x or 0, inp.meta.position.y or 0)
        pivotOf = getattr(inp, "_pivot", None)
        return (p + cast(v2, pivotOf())) if callable(pivotOf) else p

    @property
    def width(self) -> wnumber:
        if not self.inputs:
            return 0
        anchors = [Group._anchorOf(inp).x for inp in self.inputs]
        rights = [a + inp.width / 2 for a, inp in zip(anchors, self.inputs)]
        lefts = [a - inp.width / 2 for a, inp in zip(anchors, self.inputs)]
        return max(rights) - min(lefts)

    @property
    def height(self) -> wnumber:
        if not self.inputs:
            return 0
        anchors = [Group._anchorOf(inp).y for inp in self.inputs]
        tops = [a + inp.height / 2 for a, inp in zip(anchors, self.inputs)]
        bots = [a - inp.height / 2 for a, inp in zip(anchors, self.inputs)]
        return max(tops) - min(bots)

    def __str__(self) -> str:
        return f"{self.__class__.__name__}"

    def __repr__(self) -> str:
        return self.__str__()
