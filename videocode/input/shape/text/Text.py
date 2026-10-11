#!/usr/bin/env python3

from __future__ import annotations

import math
from copy import copy as _shallow_copy
import videocode.input.shape.text._TextHelper as _helper

from videocode.context import Context
from videocode.input.shape.Polygon import Polygon
from videocode.input.shape.Rectangle import Rectangle
from videocode.input.shape.Polygon import paint
from videocode.input.interface.Group import Group
from videocode.shader.ishader import FragmentShader, PaintShader
from videocode.input.shape.text.Letter import Letter
from videocode.shader.vertexShader.align import align
from videocode.shader.vertexShader.hide import hide
from videocode.shader.vertexShader.position import position
from videocode.shader.vertexShader.show import show
from videocode.shader.vertexShader.scale import scale
from videocode.utils.classutils import At
from videocode.utils.decorators import prop, propagate
from videocode.utils.bezier import Easing, easing as _easing
from videocode.ty import *
from videocode.constants import *
from videocode.utils.mixins import _hasFillStroke

__all__ = [
    "Letter",
    "MarkupText",
    "Text",
    "bold",
    "colored",
    "italic",
]


# Padding (world units) added around the glyph bbox when auto-sizing a shader
# fill's canvas — purely internal: just enough that antialiased glyph edges
# don't get clipped at the canvas border.
_SHADER_CANVAS_MARGIN = 0.3


class Text(Group[Letter], _hasFillStroke):
    #: Styled slices of `text`, or None for a text shaped in one piece — only
    #: `MarkupText` sets it, on the instance, before this `__init__` runs.
    _runs: maybe[tuple[_helper.run, ...]] = None

    def __init__(
        self,
        text: str,
        fontSize: wnumber = 0.5,
        fontFamily: str = "Inter",
        fillColor: paint = WHITE,
        strokeColor: rgba = TRANSPARENT,
        strokeWidth: wufloat = 0,
        bold: bool = False,
        italic: bool = False,
        letterSpacing: float = 0,
    ):
        """
        `letterSpacing` is added after every letter, in fontSizes — CSS's
        letter-spacing, After Effects' tracking.

        `fillColor` may be a fragment shader instead of a color — the glyphs
        are then FILLED BY THE SHADER, one continuous pattern spread across
        the whole word:

            Text("STAR NEST", fontSize=1.7, fillColor=starNest())

        The shader is persistent fill state: it paints every frame from
        creation until `text.fillColor` is reassigned (to a color or another
        shader) or the video ends. Hiding/fading the text does NOT end it —
        the fill is simply not rendered while invisible and is still there
        when the text comes back. (Mechanics live in `Polygon`'s shader-fill
        segments; the timeline span resolves after the script ends.)

        Shader mode changes the structure: instead of per-letter inputs the
        Text holds ONE merged glyph silhouette (matte source, never drawn) +
        ONE canvas auto-sized to the word bbox — it positions/animates/hides
        as a single unit, but per-letter APIs (`typewriter`, letter access)
        don't apply. The shader only marches the canvas' coverage, so this is also
        the cheap way to run heavy math shaders. A letters-mode Text cannot
        switch to a shader fill after creation (recreate it instead).
        """
        self._shaderMode = isinstance(fillColor, PaintShader)
        self.text = text
        self.fontSize = fontSize
        self.fontFamily = fontFamily
        self.fillColor = fillColor
        self.strokeColor = strokeColor
        self.strokeWidth = strokeWidth
        self.bold = bold
        self.italic = italic
        self.letterSpacing = letterSpacing

        if isinstance(fillColor, PaintShader):
            # Lazy import: CompoundPolygon star-imports videocode, so a
            # module-level import here would be circular.
            from videocode.template.input.CompoundPolygon import CompoundPolygon

            # The glyphs are never drawn themselves — they only exist merged
            # into the matte source — so they must not register as inputs.
            with Context.noRegister():
                letters = Text(text, fontSize, fontFamily, WHITE, strokeColor, strokeWidth, bold, italic, letterSpacing).inputs
            word = CompoundPolygon(*letters)

            # The canvas' fillColor IS the shader — Polygon's shader-fill
            # segments handle persistence and later reassignments.
            # Slightly larger than the glyph bbox so antialiased glyph edges
            # never get clipped at the canvas border.
            margin = _SHADER_CANVAS_MARGIN
            canvas = Rectangle(
                width=word.width + margin,
                height=word.height + margin,
                fillColor=fillColor,
                strokeColor=TRANSPARENT,
            )
            canvas.matte(word)

            # canvas + word grouped: the mask must travel with the pattern
            # (matte is screen-space) when the Text is moved/animated.
            super().__init__(canvas, word)
            return

        super().__init__(
            *(
                _helper.buildLetters(
                    text=text,
                    fontSize=fontSize,
                    fontFamily=fontFamily,
                    bold=bold,
                    italic=italic,
                    fillColor=fillColor,
                    strokeColor=strokeColor,
                    strokeWidth=strokeWidth,
                    runs=self._runs,
                )
                if len(text) != 0
                else []
            )
        )
        self.alignLetters()

    def _distributeGradientColor(self, attr: str) -> None:
        value = getattr(self, attr)
        # Shader mode holds [canvas, word], not letters: forward the fill to
        # the CANVAS only (colors, gradients or another shader — Polygon's
        # shader-fill segments take over from this frame). The word is a pure
        # mask, and applying a shader to it would waste a fullscreen pass.
        if getattr(self, "_shaderMode", False):
            setattr(self.inputs[0], attr, value)
            return
        if isinstance(value, PaintShader):
            raise TypeError(
                "a letters-mode Text can't switch to a shader fill — create it "
                "with Text(..., fillColor=<shader>) instead (shader fills need "
                "the merged-silhouette structure)"
            )

        letters = self.inputs[: len(self.text)]
        if not letters:
            return

        color = getattr(self, attr)
        if not isinstance(color, LinearGradient):
            for l in letters:
                setattr(l, attr, color)
            return

        data = _helper.buildLetterData(self.text, self.fontSize, self.fontFamily, self.bold, self.italic, runs=self._runs, letterSpacing=self.letterSpacing)

        angleRad = math.radians(color.angle)
        dx, dy = math.cos(angleRad), math.sin(angleRad)

        def projRange(x: float, y: float, w: float, h: float) -> tuple[float, float]:
            projs = (x * dx + y * dy, (x + w) * dx + y * dy, x * dx + (y + h) * dy, (x + w) * dx + (y + h) * dy)
            return min(projs), max(projs)

        ranges = [projRange(x, y, l.width, l.height) for l, (_, x, y, _s) in zip(letters, data)]
        globalMin = min(r[0] for r in ranges)
        globalMax = max(r[1] for r in ranges)
        globalRange = globalMax - globalMin

        for l, (letterMin, letterMax) in zip(letters, ranges):
            if globalRange < 1e-9:
                setattr(l, attr, color.colorAt(0))
            else:
                t0 = (letterMin - globalMin) / globalRange * 100
                t1 = (letterMax - globalMin) / globalRange * 100
                setattr(l, attr, color.slice(t0, t1))

    def _distributeFillColor(self) -> None:
        self._distributeGradientColor("fillColor")

    def _distributeStrokeColor(self) -> None:
        self._distributeGradientColor("strokeColor")

    @prop(onSet=_distributeFillColor)
    def fillColor() -> paint: ...

    @prop(onSet=_distributeStrokeColor)
    def strokeColor() -> rgba: ...

    @prop()
    def text() -> str: ...

    @text.setter
    def textSetter(self, value: str) -> None:
        # Whitespace makes no `Letter` (`find` and `_memberPivots` walk the text
        # the same way), so the members line up with the NON-SPACE characters,
        # never with `value` itself. Counting `value` handed the space to a
        # letter, which built an empty polygon, and the next alignLetters asked
        # it for a width: "max() iterable argument is empty" on `Text("ab cd")`.
        chars = [c for c in value if not c.isspace()]
        l = len(self.inputs)
        r = len(chars)
        if l > r:
            for i in range(l - r):
                self.inputs[-i - 1].hide()
        elif l < r:
            target = self.inputs[0].meta.transformationOffset if self.inputs else 0
            for i in range(r - l):
                newLetter = Letter(chars[l + i], *self.config())
                if target > newLetter.meta.transformationOffset:
                    newLetter.hide()
                    newLetter._clockTo(target)
                    newLetter.show()
                self.inputs.append(newLetter)

        for i in range(min(l, r)):
            self.inputs[i].show()
            self.inputs[i].char = chars[i]

        self.alignLetters()

    def config(self) -> tuple[wnumber, str, rgba, rgba, wnumber, bool, bool]:
        # Letters take a real color: in shader mode (fillColor is a shader,
        # painted on the canvas) hand them the opaque placeholder instead.
        fill = self.fillColor if isinstance(self.fillColor, rgba) else WHITE
        return (self.fontSize, self.fontFamily, fill, self.strokeColor, self.strokeWidth, self.bold, self.italic)


    #: What a per-letter transform turns around — see `Anchor`. Set on the
    #: text, the way After Effects sets it on the layer.
    anchor: Anchor = Anchor.ALL

    def _memberPivots(self, pivot: v2) -> maybe[list[v2]]:
        """
        A pivot per letter, per word or per line — resolved here because a
        `Letter` has nothing an author could hold and parent to.

        Only in letters mode: a shader-mode `Text` holds [canvas, word], not
        one member per character, and there is nothing to group.
        """
        # Whitespace makes no `Letter` — `find` walks the text the same way.
        if self.anchor is Anchor.ALL or len(self._memberBases) != sum(1 for c in self.text if not c.isspace()):
            return None

        # Which cluster each letter belongs to. CHARACTER opens one per letter,
        # WORD one per whitespace-separated run, LINE one per newline.
        cluster: list[int] = []
        key = 0
        for char in self.text:
            if char.isspace():
                if self.anchor is Anchor.WORD or char == "\n":
                    key += 1
                continue
            if self.anchor is Anchor.CHARACTER:
                key += 1
            cluster.append(key)

        ax, ay = self.meta.align
        boxes: dict[int, list[float]] = {}
        for k, (_, base) in zip(cluster, self._memberBases):
            left, right = base.position.x - base.width / 2, base.position.x + base.width / 2
            bottom, top = base.position.y - base.height / 2, base.position.y + base.height / 2
            box = boxes.get(k)
            if box is None:
                boxes[k] = [left, right, bottom, top]
            else:
                box[0], box[1] = min(box[0], left), max(box[1], right)
                box[2], box[3] = min(box[2], bottom), max(box[3], top)

        return [v2(boxes[k][0] + ax * (boxes[k][1] - boxes[k][0]), boxes[k][2] + ay * (boxes[k][3] - boxes[k][2])) for k in cluster]

    def apply(self, *shaders, start: sec = 0, duration: sec = SINGLE_FRAME, offset: maybe[frame] = None, at: maybe[sec] = None) -> Self:
        # Everything the group handles goes down in ONE call.
        #
        # An animation arrives here as one shader per frame — `rotateBy` over a
        # second is thirty of them — and forwarding them one at a time made the
        # group answer thirty separate questions about the same window. The group
        # writes its members' positions from the whole window at once (see
        # Group._emitTimeline), so thirty calls meant rewriting it thirty times:
        # a two-transform Text cost 140 ms instead of 9. The batch is flushed
        # before anything that must keep its place in the order.
        batch: list[Any] = []

        def flush() -> None:
            if batch:
                super(Text, self).apply(*batch, start=start, duration=duration, offset=offset)
                batch.clear()

        for s in shaders:
            if isinstance(s, align):
                flush()
                _s, _d, _o = s.resolve(start, duration, offset)
                _shallow_copy(s).modify(self)
                self.alignLetters(start=_s, duration=_d, offset=_o)
            elif getattr(self, "_shaderMode", False) and isinstance(s, FragmentShader):
                # Shader mode: a fragment shader POST-PROCESSES the filled
                # result — canvas only (touching the word would distort the
                # mask). Chain order is guaranteed: the fill is per-frame
                # state injected FIRST by the C++, timeline effects follow.
                flush()
                self.inputs[0].apply(s, start=start, duration=duration, offset=offset)
            else:
                batch.append(s)

        flush()
        return self

    def alignLetters(self, start: sec = 0, duration: sec = SINGLE_FRAME, offset: maybe[frame] = None) -> None:
        n = len(self.text)
        letters = self.inputs[:n]
        if not letters:
            return

        data = _helper.buildLetterData(
            text=self.text,
            fontSize=self.fontSize,
            fontFamily=self.fontFamily,
            bold=self.bold,
            italic=self.italic,
            runs=self._runs,
            letterSpacing=self.letterSpacing,
        )

        xMin = min(0.0, min(x for _, x, _, _s in data))
        xMax = max(x + l.width for (_, x, _, _s), l in zip(data, letters))
        ax = xMin + self.meta.align.x * (xMax - xMin)

        ay = _helper.lineAnchor(self.fontFamily, self.bold, self.italic, self.fontSize, self.meta.align.y)

        for letter, (_, x, y, _s) in zip(letters, data):
            letter.apply(align(0, 0))
            # Set text-local position directly on meta (no C++ push) so _regroup()
            # captures group-relative coords; _emitRigid below emits world positions.
            letter.meta.position = v2(x - ax, y - ay)

        # Re-snapshot member bases with the new text-local layout positions.
        self._regroup()

        # And then forget them again, because a position shader that matches
        # `meta.position` is dropped as a write with no effect (see
        # `position.autodestroy`). The meta above is only there for `_regroup`
        # to snapshot; leaving it means every letter of a text that was never
        # MOVED emits its layout and has it thrown away — and C++, which starts
        # every input at the origin and only learns from claims, draws the whole
        # word on one spot. Measured: `Text("Kate")` and `Text("Kate").position(0, 0)`
        # came out 25 px wide, all four letters stacked, while the same text
        # placed at 0.001 came out as a word.
        # Not under `noRegister`, where nothing reaches the stack and nothing
        # writes the meta back: `CompoundPolygon(*Text(...).inputs)` reads the
        # layout straight off the letters, and zeroing it there collapses the
        # word onto one spot — which is what the matte and silk scenes do.
        if not Context._noRegister:
            for letter in letters:
                letter.meta.position = v2(0, 0)

        # Emit world positions (group transform applied on top of text-local bases).
        self._emitRigid(start, duration, offset, pos=True)

        if isinstance(self.fillColor, LinearGradient):
            self._distributeFillColor()
        if isinstance(self.strokeColor, LinearGradient):
            self._distributeStrokeColor()

    @propagate(after=alignLetters)
    def fontSize() -> wnumber: ...
    @propagate(after=alignLetters)
    def fontFamily() -> str: ...
    @propagate(after=alignLetters)
    def bold() -> bool: ...
    @propagate(after=alignLetters)
    def italic() -> bool: ...
    @prop(onSet=alignLetters)
    def letterSpacing() -> float:
        """Added after every letter, in fontSizes — CSS's letter-spacing, After Effects' tracking."""
        ...

    @property
    def width(self) -> wunumber:
        if getattr(self, "_shaderMode", False):
            return self.inputs[0].width or 0  # the shader canvas
        return sum(l.width for l in self.inputs) if self.inputs else 0

    @property
    def height(self) -> wunumber:
        if getattr(self, "_shaderMode", False):
            return self.inputs[0].height or 0  # the shader canvas
        return max(l.height for l in self.inputs) if self.inputs else 0

    @classmethod
    def _fromLetters(cls, letters: list[Letter], src: Text) -> Text:
        """Wrap existing Letter objects in a Text — no letter rebuild, no alignLetters."""
        inst = object.__new__(cls)
        # Copy parent meta so zIndex/opacity/scale/rotation etc. are inherited;
        # clear index (virtual group, no C++ slot) and callbacks (not inherited).
        meta = _shallow_copy(src.meta)
        meta.index = cast(int, None)
        meta.preCallbacks = {}
        meta.postCallbacks = {}
        inst.meta = meta
        # prop init guard skips onSet on first assignment, so no side effects here
        inst.text = "".join(l.char for l in letters)
        inst.fontSize = src.fontSize
        inst.fontFamily = src.fontFamily
        inst.fillColor = src.fillColor
        inst.strokeColor = src.strokeColor
        inst.strokeWidth = src.strokeWidth
        inst.bold = src.bold
        inst.italic = src.italic
        inst.letterSpacing = src.letterSpacing
        inst.inputs = letters
        inst._snapshot()
        # Anchor group position at the leftmost letter; adjust member bases to stay relative.
        origin = v2(*letters[0].meta.position)
        meta.position = origin
        for _, base in inst._memberBases:
            base.position = base.position - origin
        return inst

    def find(self, pattern: str) -> Group[Text]:
        import re

        charToLetter: dict[int, int] = {}
        letterIdx = 0
        for charIdx, char in enumerate(self.text):
            if not char.isspace():
                charToLetter[charIdx] = letterIdx
                letterIdx += 1
        result: Group[Text] = Group()
        for match in re.finditer(pattern, self.text):
            letters = [self.inputs[charToLetter[i]] for i in range(match.start(), match.end()) if i in charToLetter]
            if letters:
                result.inputs.append(Text._fromLetters(letters, self))
        return result

    def typeIn(
        self,
        *,
        start: sec = 0,
        delay: sec = SINGLE_FRAME / 1.3,
        overshoot: float = 1.4,
        settle: sec = 3 * SINGLE_FRAME,
        easing: _easing = Easing.Out,
    ) -> Self:
        for i, letter in enumerate(self.inputs):
            tI = start + i * delay
            letter.apply(hide(), offset=0)
            letter.apply(show(), start=tI)
            if overshoot != 1.0:
                letter.apply(scale(overshoot, overshoot).at(start=tI))
                if settle < SINGLE_FRAME:
                    letter.apply(scale(1.0, 1.0).at(start=tI + SINGLE_FRAME))
                else:
                    letter.scaleTo(1.0, start=tI, duration=settle, easing=easing)
        return self

    def __str__(self) -> str:
        return f"Text({self.text})"


class MarkupText(Text):
    r"""
    A `Text` whose style CHANGES INSIDE THE LINE — the tags style the
    glyphs instead of being drawn as glyphs:

        MarkupText('Hello <b>world</b>, <font color="#FF6A00">on fire</font>')
        MarkupText(f"Hello {bold | 'world'}, {colored(RED_B) | 'on fire'}")

    The second line is the first one with the tags WRITTEN FOR YOU — see
    `bold`. `<b>`, `<i>`, `<font color="#hex">` and `<span color=…>` are honoured
    and nest, a run's bold/italic ORing with the `bold=`/`italic=` given
    here. Every other tag — `<u>`, a subtitle's `{\an8}`, an unknown name —
    is STRIPPED, never drawn.

    The members are `Letter`s like any other text's, and `.text` is the
    PLAIN text, so `find()`, `typeIn()`, `anchor` and gradients keep
    working on what the reader sees. Assigning `.fillColor` afterwards
    still repaints every letter, a coloured run included — the same rule
    an SVG's own fills follow.

    ponytail: each run is shaped on its own, so kerning ACROSS a run
    boundary is lost (and a tab inside one restarts its column there).
    Shaping the whole line once and re-running it per style would fix it;
    no subtitle or Markdown line has asked yet.
    """

    def __init__(
        self,
        markup: str,
        fontSize: wnumber = 0.5,
        fontFamily: str = "Inter",
        fillColor: paint = WHITE,
        strokeColor: rgba = TRANSPARENT,
        strokeWidth: wufloat = 0,
        bold: bool = False,
        italic: bool = False,
    ):
        plain, runs = _helper.parseMarkup(markup)
        # None, not (): a text with no run at all must take the shaping path a
        # plain `Text` takes, character for character.
        self._runs = runs or None
        super().__init__(plain, fontSize, fontFamily, fillColor, strokeColor, strokeWidth, bold, italic)


class _Markup:
    """
    One style of a `MarkupText`, waiting for the text it wraps — see `bold`.

    `bold | italic` is another style, so `bold | italic | "x"` wraps twice.
    `bold | "x" | italic` is a `str | _Markup`, which Python refuses out
    loud — better than a tag quietly landing outside its text.
    """

    def __init__(self, opening: str, closing: str):
        self._opening, self._closing = opening, closing

    @overload
    def __or__(self, other: _Markup) -> _Markup: ...
    @overload
    def __or__(self, other: str) -> str: ...
    def __or__(self, other: _Markup | str) -> _Markup | str:
        if isinstance(other, _Markup):
            return _Markup(self._opening + other._opening, other._closing + self._closing)
        if not isinstance(other, str):
            return NotImplemented
        # `<` and `&` are what `parseMarkup` reads as markup: the author's
        # `a < b` must reach the letters, not open a tag.
        return self._opening + other.replace("&", "&amp;").replace("<", "&lt;") + self._closing

    def __call__(self, text: str) -> str:
        return self | text


#: `bold | "x"` is `"<b>x</b>"` — the tag written for you, so a `MarkupText`
#: composes inside an f-string instead of by hand:
#:
#:     MarkupText(f"a {bold | 'subtitle'} can be {italic | 'styled'} {colored(RED_B) | 'on fire'}")
#:
#: `bold("x")` says the same. Styles chain with `|`: `bold | italic | "x"`.
bold = _Markup("<b>", "</b>")
italic = _Markup("<i>", "</i>")


def colored(color: rgba | str) -> _Markup:
    """
    `colored(RED_B) | "x"` paints x — an `rgba` or a `"#RRGGBB"`, what every
    colour here takes. Not `color`: that name is the `videocode.color` module.
    """
    if isinstance(color, str):
        color = rgba(color)
    hexa = f"#{color.r:02x}{color.g:02x}{color.b:02x}" + (f"{color.a:02x}" if color.a != 255 else "")
    return _Markup(f'<font color="{hexa}">', "</font>")
