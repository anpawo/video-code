# Video-Code — Feature Map

A tour of what the `videocode` Python API can currently do, with pointers to
the implementing file and a runnable example for each feature. Useful as a
starting point to explore the codebase (e.g. for building the GUI — #117).

General notes:
- **Coordinate system**: world coordinates, **Y is positive upward**, origin
  at screen center. `WORLD_TO_SCREEN_RATIO = 120` maps world units to pixels
  (`videocode/constants.py`). `WORLD_WIDTH`/`WORLD_HEIGHT`/`WORLD_OFFSET_X`/
  `WORLD_OFFSET_Y` give the visible world-space bounds — 16x9 at the default
  1920x1080, 9x16 in portrait, etc. (see [Render size](#render-size)).
- **Everything is an `Input`** (`videocode/input/input.py`) — every shape,
  text, image, video, sound, group, etc. is a subclass and shares the
  transformation/animation API described in [Transformations](#transformations--animation-input-methods).
- **Runnable examples**: `test/visual/scenes/*.py` are small self-contained
  scenes used by the visual-regression suite (`./video-code --visual-test`)
  — each one below maps to the feature(s) it covers. `video.py` is the
  living demo script (`./video-code` to preview, `--generate out.mp4` to
  render).
- Run any scene with `./video-code --file test/visual/scenes/<name>.py` to
  preview it live.

---

## Inputs — Shapes (`videocode/input/shape/`)

All shapes are `Polygon` subclasses (`Polygon.py`) — they share
`fillColor`, `strokeColor`, `strokeWidth`, `cornerRadius` (0-100%, percent of
the shape that becomes rounded), and `sharpCorners` (vertex indices exempt
from rounding).

| Class | File | What it is |
|---|---|---|
| `Polygon(vertices, fillColor, strokeColor, strokeWidth, cornerRadius, sharpCorners, open)` | `Polygon.py` | Base for all shapes — arbitrary vertex list, filled via earcut (handles holes/multi-contour), optional rounded corners |
| `Rectangle(width, height, fillColor, strokeColor, strokeWidth, cornerRadius)` | `Rectangle.py` | |
| `Square(size, ...)` | `Rectangle.py` | `Rectangle` with `width == height` |
| `HorizontalLine(length, ...)` / `VerticalLine(length, ...)` | `Rectangle.py` | Thin rectangles, optionally `rounded` |
| `Circle(radius, fillColor, strokeColor, strokeWidth)` | `Circle.py` | Bezier-approximated circle |
| `Dot(...)` | `Circle.py` | Small filled `Circle` |
| `Triangle(p0, p1, p2, fillColor, strokeColor, strokeWidth, cornerRadius)` | `Triangle.py` | Arbitrary 3-point triangle |
| `EquilateralTriangle` / `RightTriangle` | `Triangle.py` | Convenience constructors |
| `Curve(points, strokeColor, strokeWidth, cornerRadius)` | `Curve.py` | Open polyline/curve (`open=True`, `fillColor=TRANSPARENT`); `.animate()` reveals it point-by-point |
| `FunctionGraph(...)` | `Curve.py` | `Curve` sampled from a math function |

**Examples**: `test/visual/scenes/shapes.py` (basic shapes + corner rounding),
`test/visual/scenes/curve.py` (curve reveal animation), `test/visual/scenes/gradient*.py`
(shapes filled with gradients instead of solid colors).

---

## Inputs — Text & Documents (`videocode/input/shape/text/`)

| Class | File | What it is |
|---|---|---|
| `Letter(char, font, fontSize, ...)` | `Letter.py` | A single glyph outline as a `Polygon` (FreeType + HarfBuzz). Multi-contour glyphs (holes, e.g. "o") handled via earcut-with-holes. |
| `Text(text, fontSize, fontFamily, fillColor, strokeColor, strokeWidth, bold, italic)` | `Text.py` | A line of text — `Group[Offset[Letter]]`, each letter individually positioned |
| `MarkupText(markup, fontSize, fontFamily, fillColor, strokeColor, strokeWidth, bold, italic)` | `Text.py` | A `Text` whose style changes INSIDE the line: `<b>`, `<i>`, `<font color="#hex">`/`<span color=…>` style the run they wrap, each run shaped with its own face so a bold word advances by bold widths. Every other tag (`<u>`, a subtitle's `{\an8}`, an unknown name) is stripped, never drawn. `.text` is the plain text, so `find()`/`typeIn()`/`anchor`/gradients are unchanged, and assigning `.fillColor` still overrides every run. See `_TextHelper.py` for `parseMarkup()`. Kerning across a run boundary is lost. |
| `bold | "x"`, `italic | "x"`, `colored(rgba) | "x"` | `Text.py` | The tags of a `MarkupText` written for you, so a line composes inside an f-string: `MarkupText(f"a {bold | 'subtitle'} can be {italic | 'styled'} {colored(RED_B) | 'on fire'}")`. `bold("x")` says the same; styles chain (`bold | italic | "x"`); a `<` or `&` in the wrapped text is escaped and reaches the letters. `bold | "x" | italic` (wrong order) is a `TypeError`. |
| `Markdown(filepath, fontSize, fillColor, strokeColor, strokeWidth, x, y, lineSpacing)` | `Markdown.py` | Renders a `.md` file as a stack of `MarkupText` blocks. v1: `#`...`######` headings (size-scaled), `- `/`* ` bullets (rendered "• "), whole-line `**bold**`/`*italic*`, plain paragraphs — plus inline `**bold**`/`*italic*` mixed within a line. See `_MarkdownHelper.py` for `parseMarkdown()`. |
| `Subtitles(filepath, fontSize, fillColor, strokeColor, strokeWidth, y, lineSpacing)` | `Subtitles.py` | Parses a `.srt` file (`_SubtitleHelper.parseSRT()`) into `MarkupText` blocks that `hide()`/`show()` themselves at each cue's start/end time — a cue's `<i>`/`<b>`/`<font color>` styles the line, `{\anN}` and `<u>` are dropped |

**Examples**: `test/visual/scenes/text.py`, `text_stroke.py`, `text_gradient.py`,
`markdown.py` (uses `test/test.md`), `subtitles.py` (uses `test/test.srt`);
`test/markup_text_test.py` (uses `test/test_tags.srt`).

---

## Inputs — Media (`videocode/input/media/`)

| Class | File | What it is |
|---|---|---|
| `Image(filepath, width, height, cornerRadius, strokeColor, strokeWidth, uvMapping, uvAngle)` | `Image.py` | Image file as a (optionally rounded/stroked) textured `Polygon`. Both of `width`/`height` ⇒ stretched to that box; only one ⇒ the other follows the file's aspect ratio; neither ⇒ natural size — known to Python as well as to C++, so a bare `Image` groups and gets a `SurroundingRectangle` like any shape. |
| `WebImage(url)` | `Image.py` | Downloads an image over HTTPS (via `curl`, plain HTTP refused) **when the scene is baked**, caches it in the gitignored `webimage/`, then behaves like `Image`. A scene using one is not reproducible: its input lives on someone else's server and can change with no commit behind it. Fine for a video you are making, wrong for a test scene. |
| `Video(filepath, cuts, startFrame, endFrame, speedRamps, width, height, cornerRadius, strokeColor, strokeWidth, uvMapping, uvAngle)` | `Video.py` | Video file as a textured `Polygon`. `cuts`/`startFrame`/`endFrame` trim/skip source frames during playback. `speedRamps=[(playbackStart, playbackEnd, rate), ...]` retimes windows of the playback timeline: rate `2.0` = sped up, `0.5` = slow-mo, `0.0` = freeze-frame, `-1.0` = reverse. `width`/`height` size it the same way `Image` does — only one given, and the other follows the source's aspect ratio (`ffprobe` runs at construction to read it). The file's own audio track, when it has one, is muxed into the render — cut where the picture is cut and retimed with it when the source is not 30 fps — so no `Sound` on the same file is needed (one would play the track twice). |
| `Sound(filepath, start, volume, trimStart, trimEnd)` | `Sound.py` | Purely auditory — no visual geometry. `start` = seconds AFTER the script's cursor, like `hide(start=…)` and like every shape written on that line: a `Sound` after `wait(2)` plays at 2s, `start=0.5` there plays at 2.5s (before any `wait()` the cursor is 0, so `start` is the plain output delay). `volume` is a 0-1 multiplier, `trimStart`/`trimEnd` cut the source clip. Multiple `Sound`s get mixed together via ffmpeg `amix`. A sound landing past the end of the scene lengthens the output by its tail — the mux has no `-shortest`. `volume` is also a CLAIM like any other property: `music.over(start=2, duration=1.5).volume = 0` fades it out on the timeline, and the mux reads the level frame by frame instead of the constructor's number. `music.duck(under=voice)` writes both ramps of the move every voice-over makes — down as the voice starts, back up once it ends — and `sound.length()` is how long it plays, trims included. |

`uvMapping` (`Image`/`Video`, default `UVMapping.STRETCH`) controls how the
texture is wrapped onto the shape: `STRETCH` is bbox-normalized UVs (texture
stretched to the bounding box); `RADIAL`/`CONIC` are polar UVs around the bbox
center, mirroring `RadialGradient`/`ConicGradient`'s center/angle convention
(`u=radius,v=angle` vs `u=angle,v=radius`). `uvAngle` (degrees) rotates the
angular origin for radial/conic mapping.

### Video time remapping (`speedRamps`)

```python
video = Video("clip.mp4", speedRamps=[
    (30, 60, 0.0),     # freeze for a second (frames 30-60 of the playback timeline)
    (60, 120, -1.0),   # then play backwards
])
```

How: each `(playbackStart, playbackEnd, rate)` window retimes the post-cut
playback timeline — everything outside the windows plays normally.
**Pros**: composes with `cuts`/`startFrame`/`endFrame`; freeze/reverse/speed
in one param. **Cons**: nearest-frame sampling only (no frame blending for
slow-mo); a `cuts` boundary *inside* a ramp window isn't re-applied by the
ramp's rate math (documented in the docstring).

### Motion tracking (`video.track` + `attachTo`)

```python
video = Video("footage.mp4", width=8, height=4.5)
sticker = Circle(radius=0.3, fillColor=RED_A)
sticker.attachTo(video.track(310, 220))   # x,y = pixel in the SOURCE footage
```

How: `track()` runs OpenCV optical flow over the source frames and returns a
`TrackedPath` (per-frame world positions); `attachTo()` makes any `Input`
follow it. Needs `pip install opencv-python` (lazy — only `.track()` callers).
**Pros**: real tracking, ~sub-pixel accurate on clean footage; the attached
input is a normal `Input` (animate/style it freely). **Cons**: tracking loses
lock on occlusion/fast motion (it then holds the last good position); frame
indices are source-frame space, so it doesn't auto-realign under
`cuts`/`speedRamps`; assumes the `Video` itself doesn't move.

### Beat-sync (`sound.beats`)

```python
sound = Sound("music.wav")
logo = Circle(radius=0.9, fillColor=rgba(255, 150, 40))
for beat in sound.beats():                # timestamps in seconds
    logo.apply(pulse(scale=1.3, start=beat, duration=0.3))
```

How: decodes the audio via ffmpeg and runs spectral-flux onset detection
(numpy only — no librosa); returns second-timestamps that plug into any
effect's `start=`. Tune with `sensitivity` (higher = fewer, stronger onsets)
and `minInterval` (minimum spacing). **Pros**: works on any ffmpeg-decodable
file; no heavy deps. **Cons**: it detects *transients* (drum hits, clicks),
not musical meter — no BPM/downbeat awareness, so legato music without sharp
attacks won't produce beats.

### Auto-captions (`sound.transcribe`)

```python
speech = Sound("interview.mp4")           # Sound accepts video files too
subs = Subtitles(speech.transcribe())     # writes a real .srt, returns its path
```

How: runs faster-whisper (OpenAI Whisper weights, CPU, no PyTorch) and writes
a standard `.srt` the existing `Subtitles` input renders; `model="small"` etc.
for better accuracy, `language="en"` to skip auto-detection. **Pros**:
standard `.srt` output (editable/reusable outside the tool); models cached
after first download. **Cons**: the default `tiny` model trades accuracy for
speed (occasional misheard words); first use downloads ~75MB; CPU-only.

**Examples**: `test/visual/scenes/image_shape.py`,
`test/visual/scenes/uv_mapping.py`, `video.py` (scene),
`test/visual/scenes/sound.py` (uses `test/test.wav`);
`test/track_test.py`, `test/beat_sync_test.py`, `test/transcribe_test.py`
(runnable end-to-end demos with synthetic/checked-in fixtures).

---

## Inputs — SVG (`videocode/input/shape/svg/`)

| Class | File | What it is |
|---|---|---|
| `SVG(filepath, width, height)` | `SVG.py` | Parses an SVG (via `svgelements`) into one `SVGPath` `Polygon` per shape element, each `Offset` to its position within the SVG canvas — `Group[Offset[SVGPath]]` |
| `SVGPath` | `SVGPath.py` | Static `Polygon` holding one precomputed shape's contours |

A shape painted with a gradient — `fill="url(#sunset)"` or `stroke="url(#sunset)"`,
what an icon exporter writes — becomes a `LinearGradient`/`RadialGradient`, stops,
opacity and direction included, instead of the flat black it used to be silently
painted. `logo.fillColor = WHITE` still overrides the file. Not supported, and
warned about rather than guessed at: `gradientTransform`, `gradientUnits="userSpaceOnUse"`,
`<pattern>`, and gradients that inherit their stops through `href` — those still
fall back to `BLACK`. A diagonal gradient is spread across the shape's extent along
its axis, so it lands slightly off what a browser draws.

**Example**: `test/visual/scenes/svg.py`; `test/svg_gradient_test.py`.

---

## Inputs — Math (`videocode/input/shape/tex/`)

| Class | File | What it is |
|---|---|---|
| `MathTex(tex, fillColor, strokeColor, strokeWidth, width, height)` | `MathTex.py` | Renders a LaTeX math expression (e.g. `r"\frac{1}{2} + \int_0^1 x^2 dx"`) as a `Group[Offset[SVGPath]]`, recolored as one unit — `formula.fillColor = RED_A` recolors every glyph |
| `Tex(tex, ...)` | `MathTex.py` | Like `MathTex`, but `tex` is inserted verbatim as the document body instead of being wrapped in `$...$` — for plain text or LaTeX constructs (e.g. `align*`) that shouldn't be in math mode |
| `_TexHelper.texToSVG(tex, mathMode)` | `_TexHelper.py` | Compiles `tex` via `latex` + `dvisvgm --no-fonts` (every glyph becomes an outlined path, no embedded fonts) and caches the result under `.cache/tex/<hash>.svg` |

Requires a LaTeX distribution with `latex` and `dvisvgm` on `PATH` (see
`docs/SETUP_LINUX.md`). Manim-style, Manim isn't a dependency: the SVG output
is loaded through the same `_SVGHelper`/`SVGPath`/`Offset`/`Group` pipeline as
`SVG`.

**Example**: `test/visual/scenes/mathtex.py`.

---

## Composite / Template Inputs (`videocode/template/input/`)

| Class | File | What it is |
|---|---|---|
| `Plane(center)` | `Plane.py` | Background grid (rectangle + horizontal/vertical faint lines) — handy for axes/debugging |
| `Box(size, margin, text, color)` | `Box.py` | Rectangle + centered `Text`, `isHovered` flag for interactivity |
| `Button(width, height, text, color)` / `RedButton` / `GreenButton` / `BlueButton` | `Button.py` | Rounded rectangle + label, `isHovered` flag |
| `Graph(xRange, yRange, xExclude, yExclude, unitSize, fontSize, color, lineThickness)` | `Graph.py` | Cartesian axes with numbered ticks |
| `PositiveGraph`, `GraphPoint` | `Graph.py` | Axes restricted to positive quadrant; a labeled point on a `Graph` |
| `BarChart(data, width, height, gap, top, color, fontSize, showValues)` | `BarChart.py` | One bar per row of data, its label under it and its value ON it. The tallest bar is exactly `height`, so `top=` is what lets two charts be read against each other. `grow()` animates the bars up from the baseline and writes each value with the SAME ramp as its bar, so the number rides the bar's top instead of sitting where it was left — which is the one thing every hand-written chart gets wrong. `BarChart.fromCSV(path, label=, value=)` reads the data from a file, by column name with a header row or by column number without, and refuses a bad cell by line rather than dropping the bar. |
| `Leaderboard(rows, …)` | `BarChart.py` | The same chart, sorted biggest first — a leaderboard read in the order the data happened to be in is not a leaderboard. |
| `ParticlesRay(size, nbr)` | `Particles.py` | Ring of small lines radiating outward (e.g. for click/sparkle effects) |
| `Shadow(shape, offset, color, blurStrength)` | `Shadow.py` | Copy of another `Polygon`'s geometry, solid-filled, offset, rendered behind via `zIndex` |
| `SurroundingRectangle(shape, buff, color, strokeWidth, cornerRadius)` | `SurroundingRectangle.py` | Rectangle outline around another `Polygon`'s bounding box + `buff`, for highlighting — Manim's `SurroundingRectangle` |
| `Underline(shape, buff, color, strokeWidth)` | `Underline.py` | Rounded line under another `Polygon`'s bounding box, offset by `buff` — Manim's `Underline` |
| `Cross(shape, buff, color, strokeWidth)` | `Cross.py` | Two diagonal lines forming an "X" over another `Polygon`'s bounding box + `buff` — Manim's `Cross` |
| `FocusOn(x, y, color, startRadius, endRadius, duration, easing)` | `FocusOn.py` | Translucent circle that shrinks onto `(x, y)` while fading in — "spotlight converging on a point" — Manim's `FocusOn` |
| `DashedLine(x1, y1, x2, y2, dashLength, dashedRatio, color, strokeWidth)` | `DashedLine.py` | Straight line rendered as evenly-spaced dashes — Manim's `DashedLine`, for annotation/helper lines |
| `Arrow(length, bodyLength, bodyWidth, tipLength, tipHeight, bodyInTip, fillColor, strokeColor, strokeWidth, cornerRadius)` | `Arrow.py` | Single-`Polygon` arrow shape |
| `Cursor()` | `Arrow.py` | Pre-shaped `Arrow` styled as a mouse cursor |
| `SplitView(ratio, split, marginX, marginY, padding, ...)` / `Panel` | `SplitView.py` | Two panels dividing the frame — see below |
| `Row(*inputs, gap, align)` / `Column(*inputs, gap, align)` | `Layout.py` | Inputs side by side / stacked, `gap` measured **edge to edge**, centred on the group — see below |
| `Grid(*inputs, cols, gap, rowGap, colGap)` | `Layout.py` | Inputs in reading order over `cols` columns, each column as wide as its widest member, each row as tall as its tallest |

**Examples**: `test/visual/scenes/shadow.py`, `test/visual/scenes/groups.py`,
`test/visual/scenes/chess.py` (chessboard built from these primitives).

### Edge-to-edge layouts — `Row`, `Column`, `Grid`

```python
Row(Rectangle(width=4, height=2), Circle(radius=1), gap=0.5)   # circle's left edge 0.5 right of the rectangle's right edge
Column(Rectangle(width=3, height=0.5), Row(a, b, gap=0.3), gap=0.2, align=Align.START).position(-4, 2)
Grid(*[Square(0.8) for _ in range(7)], cols=3, gap=0.25)         # three rows, the last one flush left
```

`gap` is the distance between two neighbours' EDGES, in world units (120 px;
the 1080p world is 16 x 9) — `XAlign`'s `gap` is a centre-to-centre pitch that
ignores widths, and it is off-centre for even counts. `align` picks the
cross-axis edge to flush: `Align.START` (top of a `Row`, left of a `Column`),
`Align.CENTER` (default), `Align.END`. Nesting works: a `Row` inside a `Column` is
measured by its content. **Ceiling**: the layout is computed once, at
construction — a member that grows or is replaced afterwards does not reflow
the formation; build a new one.

**Examples**: `test/layout_test.py`.

### Your own templates — `<project>/templates/*.py`

A `templates/` folder at the project root (beside the scene, no `__init__.py`)
is the project's own pack, and the editor's Library panel lists it beside the
library's under **YOUR TEMPLATES**:

```python
# templates/LowerThird.py
from videocode import *
from videocode.input.interface.Group import Group

class LowerThird(Group):
    """A name and a title, bottom left."""          # the panel's description
    def __init__(self, name: str, title: str = "Guest", color: rgba = BLUE_C):
        super().__init__(Text(text=name), Text(text=title, fillColor=color))

# templates/presets.py — a public function is an effect preset, applied with .apply(myPop())
def myPop():
    return popIn(scale=0.3, easing=Easing.Elastic)
```

The fields are read off `__init__`, the description off the first docstring
line, and dropping one writes `from templates.LowerThird import LowerThird` —
which resolves because the project root is `sys.path[0]`. Helpers you do not
want offered start with `_`. A file that fails to import is named on stderr and
left out; the rest of the panel is unaffected. `templateCatalogue(root)` and
`effectCatalogue(root)` in `videocode/serialize.py` are what the editor asks.
`enumValues(name)` answers next to them, for a type rather than a folder: the
members of `UVMapping` or `Align`, spelled the way a scene writes them
(`Align.START`), and nothing at all for anything that is not an enum. That is
how a field in an element's card knows whether to offer a list to pick from or
a place to type.

A default that depends on the frame must not spell `W`/`H` as a literal — take
`None` and resolve in the body, as `SplitView` does (see `setScreen` in
`constants.py`). The folder is plain files, so it travels with `git`.

### Two-panel layouts — `SplitView(split=Split.…)`

```python
sv = SplitView(ratio=3 / 5)                    # columns at 16x9, rows at 9x16
sv = SplitView(ratio=3 / 5, split=Split.ROWS)  # stacked, whatever the frame
Text("hi").position(sv.a.left, sv.a.top)       # same API either way
```

Named after what each PANEL is, like CSS grid — `COLUMNS` = two columns side
by side, `ROWS` = two rows stacked. Not "in a row".

| Mode | Layout | `ratio` sizes |
|---|---|---|
| `AUTO` (default) | `COLUMNS` if the world is wider than tall, else `ROWS` | the split axis |
| `COLUMNS` | `a \| b`, side by side, full height | `b`'s width against `a`'s |
| `ROWS` | `a` above `b`, stacked, full width | `b`'s height against `a`'s |

In a 16x9 world `AUTO` **is** `COLUMNS`, so swapping one for the other there
changes nothing — they diverge only when the frame is square or portrait.

How: `AUTO` reads the world box, which already tracks the render size — so one
scene renders side-by-side as a 16x9 master and stacked as a 9x16 phone cut,
with no edit. `a` is always the first panel and `b` the second, and every
`Panel` property (`left`/`right`/`top`/`bot`/`cx`/`cy`/`innerWidth`/
`innerHeight`) means the same thing in both, so a scene written against them
survives the flip. **Pros**: two columns in a portrait frame are each too
narrow to hold anything — stacking is the only layout that keeps both panels
usable, and `AUTO` picks it for you. **Cons**: a stacked panel is short and
wide, so a `Paragraphe` of many lines that fitted a full-height column can
overflow it vertically — that is content tuning, not layout. `panelHeight` is
a `COLUMNS`-only override (in `ROWS` the split decides the heights).

**Examples**: `test/visual/scenes/split_rows.py` (portrait, golden-tested),
`test/splitview_test.py`, `video.py`, `docs/by-example/tuto.py`.


---

## Grouping & Composition (`videocode/input/interface/`)

| Class | File | What it is |
|---|---|---|
| `Group(*inputs)` | `Group.py` | Holds multiple `Input`s; `.apply()`/transformation calls broadcast to every member. Subclass it to build composite inputs (see Template Inputs above). |
| `StatefulGroup(*inputs)` | `StatefulGroup.py` | Like `Group`, but snapshots each member's position/scale/rotation/opacity/align at creation and re-applies the group's *delta since creation* to each member — so members that already diverged from each other stay diverged (vs. `Group` collapsing them to the same absolute value) |
| `Offset(input, x, y, r)` | `Offset.py` | Wraps an input with a fixed local-frame offset (rotates with the wrapped input). Used internally by `Text`/`SVG` to place letters/shapes within their parent. |
| `Interface` | `Interface.py` | Common base for `Group`/`Offset` — defines `flush`, `wait`, `waitTo`, `waitFor`, `broadcast` |

**How a group's own animations combine** — the same claim model as a leaf,
applied to the group's rigid state (`Group._RIGID_CHANNELS`): `pos.x`, `pos.y`,
`rot`, `scl.x`, `scl.y`, `align.x`, `align.y`. `g.moveTo(x=2, duration=1)` and
`g.moveBy(y=3, start=0.5, duration=2)` both play, and x travels exactly as it
would have alone. What a group emits toward its members is worked out per
frame from those channels — members are never told to compose anything.

`align` is on that list because it decides the **pivot**, and a pivot is what
every emission was computed from. A group re-emits its whole window on each
call, so an `align` landing mid-window used to hand its new pivot to frames
written long before it. Give it a time — `g.apply(align(0, 0.5), start=0.5)` —
and the frames before it keep the pivot they were emitted with. A bare
`g.apply(align(...))` carries no time and so still applies from the start of
the window: `align` is still doing two jobs at once (aligning the content, and
placing the pivot), and separating them is an open question.

**Examples**: `test/visual/scenes/groups.py`, `stateful_group_scale.py`,
`test/visual/scenes/mirror.py`.

---

## Transformations & Animation (`Input` methods, `videocode/input/input.py`)

Every `Input` (shape, text, group, ...) has:

**Instant setters** (apply at a point in time):
- `position(x, y)`, `align(x, y)` (align relative to screen edges, e.g.
  `align(x=RIGHT_SIDE)`), `rotation(degree)`, `scale(factor | x=, y=)`,
  `opacity(o)`, `zIndex(z)`
- Layering: `inFrontOf(other)`, `behind(other)`, `bringToFront()`,
  `sendToBack()`, `bringForward()`, `sendBackward()`, `background()`
- Visibility: `hide(start)`, `show(start)`

**Eased animations** (`start`, `duration`, `easing: RateFunc`):
- `moveTo`/`moveBy`, `scaleTo`/`scaleBy`, `rotateTo`/`rotateBy`,
  `alignTo`, `fadeIn`/`fadeOut`, `fadeTo(o)` — to an opacity, from wherever
  it stands
- `moveAlong(path, face=False)` — travel a `Curve` (or any list of points) at
  ONE SPEED: the walk is measured first and each frame steps the same distance
  along it, because the points a curve is written with are dense at its bends
  and sparse on its straights, and stepping point to point crawls through the
  corners and bolts down the rest. `easing` shapes that speed as it shapes any
  other animation, and `face=True` also turns the element the way it is going —
  read from the frame before to the frame after, so a corner turns through its
  angles rather than snapping.
- `rotateTo`/`rotateBy`/`scaleTo`/`scaleBy` take `about=v2(x, y)` — the pivot,
  placed by hand. Without it a group derives one from `align`, a fraction of
  its own bounding box, so it can only ever name a point its content already
  has: `g.rotateBy(90, about=v2(0, 0))` turns the group around the origin
  whether or not anything is there. It rides on the timeline like `align`, so
  placing one mid-animation does not re-pivot the frames already written.
- `Text.anchor = Anchor.CHARACTER | WORD | LINE | ALL` — After Effects' Anchor
  Point Grouping. A `Letter` has no downstream identity to parent to, so its
  pivot is a rule resolved at emission: `CHARACTER` spins every glyph where it
  stands, `WORD` turns each whitespace-separated run as a whole, `LINE` splits
  on newlines, `ALL` (default) is the single group pivot. `about=` outranks it.
- `input.placed` / `input.composite` — whether an input has a slot of its own in
  the stack C++ renders. A `Group` is composite: it never reaches the stack, and
  what is drawn are the members it moves. That, not the pivot, is what makes it
  a different kind of thing; a leaf built inside `Context.noRegister()` is on
  the same side of the line.
- Generic: `ease(attr, to, ...)` / `easeTogether(...)` — animate *any*
  `@prop` attribute frame-by-frame (e.g. `Rectangle.ease("width", 5,
  duration=1)`, used for #125's width/height/radius animation). `duration=0`
  lands the value at once, like `moveTo` — one frame carrying the destination.

**Timeline control**:
- Module-level `wait(seconds, stop=None)` — a scheduling gap: nothing new
  happens, and by default the world stays ALIVE (shader fills animate,
  videos play). `stop` pauses selected ambient clocks for the span —
  `Clock.VIDEOS` / `Clock.PAINTS` / `Clock.EFFECTS`, one or a list; paused
  clocks RESUME where they stopped (pause, not skip). Module-level
  `freeze(seconds)` = `wait` stopping all three — a literal freeze-frame.
- `wait(seconds)`, `waitTo(frame)`, `waitFor(otherInput)`, `flush()` —
  sequencing helper, see `Curve.animate()` / `Box`/chains in `chess.py`
  for usage patterns
- `apply(*shaders, start, duration, offset)` — low-level: push raw
  `IShader`s onto the action stack (everything above is sugar over this)
- `with shot() as intro:` / `cut(intro, body, credits)` — name a stretch of the
  film and leave it. `cut(intro, body, crossfade=0.6)` dissolves instead of
  cutting: each shot becomes ONE layer for the dissolve (`shot.asOneLayer()`
  wraps it in a `Composition`, once), because two shots fading member by member
  show through each other's holes. Measured on a square leaving and a circle
  arriving: the outgoing reads 255 → 195 → 146 → 87, the incoming 51 → 107 →
  152 → 207, crossing in the middle of the window. The cost is the
  composition's: members of a dissolving shot no longer take part in the
  frame's z-order on their own. Everything made inside the block belongs to the shot (a
  shot inside another belongs to both), and `cut` puts a whole shot away at the
  frame the next one opens, instead of hiding every element of every section by
  hand. A hard cut only: a crossfade needs the two shots to fade as single
  layers, and as they are each element would fade on its own and the two shots
  would show through each other. A shot nobody cuts from is just a name for a
  stretch, which is worth having on its own.

**How two of them combine** — an effect CLAIMS the channels it was given, and
nothing else:
- **Different channels compose, whatever their windows.** `moveTo(x=2,
  duration=1)` and `moveBy(y=3, start=0.5, duration=2)` both play: x eases over
  its second and then HOLDS at 2 while y is still travelling. `x` and `y` are
  different channels; so are `fillColor` and `strokeColor`, and every other
  `Args` attribute. Starts, durations and ends do not have to line up.
- **The same channel does not.** Two effects claiming `Position:x` over shared
  frames overwrite: the last one to write wins those frames. That is deliberate
  — there is no sensible average of "go to 2" and "go to 5" — and the run says
  so out loud rather than letting the video be quietly the wrong one:

  ```
  [videocode] scene.py:4 moveTo() and scene.py:5 moveBy() both write Position:x
              on the Square from scene.py:3, over 30 frames from frame 0.
  ```

  Separate them with `flush()` or a `start=`, or write the one thing you mean.
- **A channel nobody claims on a frame keeps the value it last had** — a
  transform holds until the next one, so an effect that ends early does not snap
  back.
- **The order the lines are typed in does not change the film.** An animation
  starts from the value its element has on the frame it OPENS, not from where
  the lines above happened to leave it: `moveTo(x=5, start=2)` followed by
  `moveTo(x=2)` plays exactly like the same two lines the other way round. A
  scene with a `start=` that reaches back behind a line written above it is run
  again until every base is the one of its own frame.
- **A group works the same way**, on its own channels — see *Grouping &
  Composition*. And its own working-out is not a rival: `g.scaleTo(...)
  .rotateBy(...)` re-emits position for every member on both calls;
  `_rigidTimeline` has already composed them per channel, so nothing is
  reported. A member written BY HAND during a group's window still is — there
  the group and the line really do disagree.

**Mirroring**:
- `mirror(*targets)` / `unmirror(*targets)` — replicate every future shader
  applied to this input onto the target inputs too (cycle-safe). See
  `mirror_transformations_feature` notes / `test/visual/scenes/mirror.py`.

**Callbacks**:
- `addPreCallback`/`addPostCallback` — hook into a shader's
  apply lifecycle

**Examples**: `test/visual/scenes/animation.py`, `layers.py` (zIndex),
`resize.py` (`ease` on width/height/radius), `mirror.py`.

---

## Camera — the whole picture at once (`videocode/input/Camera.py`)

Every scene has one, already made: `camera`. It moves like anything else —
same claims, same easing, same `over()`:

```python
camera.moveTo(x=3, duration=1)       # pan: the picture slides left
camera.over(duration=1).zoom = 2     # magnify about what it looks at
camera.position(0, 0)                # back to the middle, at once
camera.scaleTo(1.5, duration=0.6)    # the same zoom, spelled the other way
```

`camera.position` is the world point that lands in the MIDDLE of the frame,
so moving the camera right moves the picture left; `camera.zoom` is a
magnification about that point (2 shows half as much, twice as big).
`camera.width` / `camera.height` say how much world the frame currently
shows.

How: the per-frame position and scale become one `Camera2D` push constant
that the vertex stage applies to every vertex — `gl_Position.xy = (ndc -
centre) * zoom`. It is **not** a composite of the scene into a layer: nothing
is flattened, no extra render pass exists, and a scene with no camera renders
byte-identically to one written before there was one. There is no camera
rotation, deliberately: vertices reach the GPU in NDC, which is not square, so
a rotation applied there would shear the picture rather than turn it.

### Staying out of it — `input.pinToFrame()`

```python
camera.over(duration=1).zoom = 2
Rectangle(width=7, height=0.7, fillColor=WHITE).position(0, -4).pinToFrame()
```

A caption that zooms with the picture is unreadable, so subtitles, a
watermark or a lower third opt out: a pinned input is drawn in FRAME space and
takes the identity camera. It reaches a `Group`'s members, like
`background()`. **Pros**: per-input, costs nothing (the same push constant,
with the identity in it). **Cons**: it is a whole-input decision — there is no
half-pinned element, and nothing un-pins one later.

**Examples**: `test/visual/scenes/camera.py`, `test/camera_test.py`.

---

## Compositing & Grading

Editor-style compositing — plain `Input` methods and fragment effects
(`docs/ADDING_EFFECTS.md` explains how they work inside the renderer).

### Blend modes — `input.blendMode(BlendMode.…)`

```python
warm = Rectangle(width=3, height=3, fillColor=rgba(200, 120, 80))
cool = Rectangle(width=3, height=3, fillColor=rgba(80, 140, 220)).position(1, 0)
cool.blendMode(BlendMode.MULTIPLY)   # NORMAL / MULTIPLY / SCREEN / ADD
```

How: sets how this input's pixels mix with whatever is drawn behind it
(multiply darkens the overlap, screen lightens, add clips toward white).
**Pros**: per-input, switchable mid-timeline via `offset=`. **Cons**: exact
for opaque pixels but approximate at antialiased edges; `OVERLAY` is
unsupported (needs destination-pixel reads the fixed-function blend can't do).

### Track mattes — `content.matte(source)`

```python
with Context.noRegister():
    letters = Text("HELLO", fontSize=2, fillColor=WHITE).inputs
word = CompoundPolygon(*letters)                       # matte needs ONE input
gradient = Rectangle(width=9, height=2.5, fillColor=LinearGradient(RED, BLUE))
gradient.matte(word)                                   # visible only inside the glyphs
```

How: this input is drawn only where `source` has coverage; `source` itself is
never rendered — it's a pure stencil. Works with any content (video, image,
math shaders). **Pros**: composes with the input's other effects; respects
antialiased edges. **Cons**: the source must be a single `Input` — a
multi-letter `Text` is a Group, so merge it via `CompoundPolygon` first.

### Adjustment layers — `AdjustmentLayer()`

```python
Circle(radius=1, fillColor=RED_A).position(-2, 0).zIndex(1)
Square(side=2, fillColor=BLUE_C).zIndex(1)
AdjustmentLayer().zIndex(5).apply(grayscale(), duration=2)   # grades everything below z=5
Square(side=2, fillColor=YELLOW).position(2, 0).zIndex(10)   # above the layer — untouched
```

How: an invisible full-frame input whose applied fragment effects grade the
flattened composite of everything *below its zIndex*; multiple layers stack
cumulatively. **Pros**: grade many inputs at once without touching them; any
fragment effect works. **Cons**: costs a full-frame flatten pass per layer;
membership is zIndex-based only (no per-input opt-out below the layer).

### Compositions — `Composition(...)`, `Comp` for short

```python
badge = Composition(Circle(radius=1), Square(side=1.4).position(0.8, 0))
badge.opacity(128)                 # ONE flat 50% shape, no bright band at the overlap
badge.apply(blur(strength=3))      # blurs the pair, not each shape
badge.moveBy(x=3)                  # members still move rigidly, as in any Group

# a multi-letter Text is ONE input once it is a composition — no CompoundPolygon
Rectangle(width=10, height=2.6, fillColor=RAINBOW).matte(Composition(*Text("COMP").position(0, -3).inputs))
```

How: a `Group` that also owns an invisible full-frame layer. Its members are
drawn into that layer instead of onto the frame, and the layer carries the
composition's opacity, fragment effects, `matte`, `zIndex` and `blendMode` — the
`composition` and `compositionMember` vertex shaders mark the two ends, and the renderers
flatten the member list the way an adjustment layer flattens a z-range.
**Pros**: a group fade is one fade (a plain `Group(a, b).opacity(128)` fades
each member, so overlaps go bright); an effect runs once over the pair; a
`Text` becomes a single input a matte can use. **Cons**: members no longer take
part in the frame's z-order on their own — a composition is one layer at one depth;
and a member that is itself semi-transparent still loses colour to the
transparent-clear flatten, which every isolated layer in this engine does
today (measured: a 50% white square reads 90 instead of 153 through any effect
layer, compositions included).

### Glow — `.apply(glow(radius, intensity))`

```python
Circle(radius=1, fillColor=YELLOW).apply(glow(radius=9, intensity=1.2), duration=2)
```

How: a blurred copy is additively composited back onto the sharp original.
**Pros**: cheap halo, best on bright shapes over the dark background.
**Cons**: the halo can't extend past other inputs drawn on top of it.

### Chroma key — `.apply(chromaKey(color, tolerance, softness))`

```python
footage = Image("greenscreen.png", width=6, height=4)
footage.apply(chromaKey(color=GREEN, tolerance=0.3, softness=0.15), duration=2)
```

How: pixels close to `color` (hue/saturation distance) become transparent.
**Pros**: standard green-screen keying with a soft edge falloff. **Cons**:
cheap/uneven lighting needs `tolerance`/`softness` tuning; strong color spill
on the subject isn't removed.

### LUT color grading — `.apply(lut("file.cube", intensity))`

```python
shot = Image("photo.png", width=8, height=4.5)
shot.apply(lut("assets/luts/warm.cube"), duration=2)
```

How: applies a standard Adobe/DaVinci `.cube` 3D color LUT — the same files
colorists exchange (free packs everywhere). **Pros**: real industry format;
parsed once and cached per file; `intensity` blends toward the original.
**Cons**: none notable — sampled trilinearly via a 2D atlas, so very cheap.

### Shader fills — `fillColor=<shader>` (any shape, and Text)

```python
Rectangle(width=4, height=3, fillColor=silk())          # the shader IS the fill
Text("FIRE", fontSize=2.6, fillColor=fire())            # one pattern across the word

text.fillColor = WHITE                                  # ends the shader at that frame
text.fillColor = starNest()                             # ...or switch shaders mid-video
```

How: a fragment shader is valid anywhere `fillColor` goes — it then PAINTS
the input every frame, as persistent fill state: from assignment until
`fillColor` is reassigned or the video ends. Hiding or fading the input does
NOT end the fill — it's simply not rendered while invisible and is still
there when the input comes back. Signatures use the `paint` alias
(`type paint = rgba | PaintShader`): fragment shaders come in two kinds —
PAINTS generate pixels from position + time (`silk`, `fire`, `starNest`,
any `mathShader`) and can be fills; FILTERS transform existing pixels
(`blur`, `grayscale`, `glow`, `lut`, ...) and belong in `.apply()` — using
one as a fill is a TypeError. On a `Text` this builds the
merged-glyph matte structure internally (one continuous pattern spread
across the word, auto-sized canvas).
**Pros**: reads as what it is (the fill); no durations to manage; switching
segments the timeline exactly where you assign. **Cons**: shader-mode Text
holds a silhouette, not letters — no per-letter animation (native Group
matte, wherewasi, would lift that); a letters-mode Text can't switch to a
shader fill after creation (recreate it instead).

**Examples**: `test/visual/scenes/blend_modes.py`, `matte.py`, `glow.py`,
`lut.py`, `adjustment_layer.py`, `effect_shaders4.py` (chromaKey).

---

## Shaders (`videocode/shader/`)

Shaders are the low-level primitives `apply()`/transformation methods push
onto the action stack; can also be used directly via `.apply(...)`.

**Vertex shaders** (`shader/vertexShader/`) — affect geometry/transform:
`position`, `translate` (relative), `scale`, `rotation`, `align`, `opacity`,
`zIndex`, `hide`, `show`, `args` (raw `Args:<name>` passthrough, e.g. for
animating `points`/`contourSizes`)

**Fragment shaders** (`shader/fragmentShader/`) — post-processing on the
rendered pixels:
| Shader | File | Effect |
|---|---|---|
| `grayscale(strength)` | `grayscale.py` | Desaturate |
| `blur(...)` | `blur.py` | Gaussian-style blur |
| `brightness(...)` / `contrast(...)` / `gamma(gamma)` | | Basic color adjusts |
| `sharpen(...)` | `sharpen.py` | Unsharp-mask sharpening |
| `grain(...)` | `grain.py` | Film-grain noise |
| `crop(...)` | `crop.py` | Crop to a region (object-relative) |
| `lightSweep(...)` | `lightSweep.py` | Animated diagonal light/highlight sweep |
| `vignette(...)` | `vignette.py` | Darkened corners (object-relative) |
| `pixelate(...)` | `pixelate.py` | Mosaic pixelation |
| `glitch(...)` | `glitch.py` | RGB split + random slice offsets (time-driven) |
| `vhs(intensity)` | `vhs.py` | Scanlines + chroma shift + analog noise (time-driven) |
| `duotone(dark, light, contrast)` | `duotone.py` | Two-ink recolor through an S-curve |
| `zoomBlur(...)` | `zoomBlur.py` | Radial "zoom punch" blur |
| `sepia()` / `invert(amount)` / `posterize(...)` / `hueRotate(...)` | | CSS-style color filters |
| `halftone(...)` | `halftone.py` | 45° print-style dot grid |
| `chromaKey(color, tolerance, softness)` | `chromaKey.py` | Green-screen keying — see [Compositing & Grading](#compositing--grading) |
| `spotlight(x, y, width, height, corner, softness, darkness)` | `spotlight.py` | Darkens everything outside a rounded box — FRAME coordinates, not object-relative |
| `glow(radius, intensity)` | `glow.py` | Additive bloom halo — see [Compositing & Grading](#compositing--grading) |
| `lut(filepath, intensity)` | `lut.py` | `.cube` LUT color grade — see [Compositing & Grading](#compositing--grading) |
| `roundCorners(radius)` | `roundCorners.py` | Round a clip's own corners (object-relative) |
| `feather(softness)` | `feather.py` | Fade a clip to transparent towards its own edges (object-relative) |
| `saturation(amount)` | `saturation.py` | Luma-based (Rec. 709) saturation, 0=gray .. 2=doubled |
| `temperature(warmth)` | `temperature.py` | White-balance-style warm/cool push, luma-preserving |
| `chromaticAberration(amount)` | `chromaticAberration.py` | RGB split radiating from the frame centre |
| `letterbox(ratio)` | `letterbox.py` | Black bars to a target aspect ratio (frame-relative) |

**Examples**: `test/visual/scenes/crop.py`, `lightsweep.py`,
`lightsweep_group.py`, `effect_shaders*.py`.

### Math shaders — `mathShader("file.glsl")` (procedural content)

```python
# Any fragcoord.xyz / Shadertoy-style fragment shader, loaded by path —
# math shaders are PAINTS: they are the fill, never .apply()'d:
bg = Rectangle(width=16, height=9, fillColor=mathShader("assets/mathshaders/plasma.glsl"))

# Bundled presets — the flagship combo is pattern-through-text:
Text("SILK", fontSize=2, fillColor=silk(speed=1.0, quality=1.0))
Text("FIRE", fontSize=2, fillColor=fire())
```

How: unlike every other fragment shader, a math shader REPLACES the input's
pixels with a generated animated pattern (the input's alpha is kept as
coverage, so it stays inside the shape and composes with `.matte()`). The
GLSL file is compiled at runtime and cached per path — write your own by
copying `assets/mathshaders/plasma.glsl` (the contract is documented in it
and in the `mathShader` docstring); no rebuild, no C++.
**Pros**: the whole Shadertoy/fragcoord universe becomes usable content;
zero-alpha pixels early-out so cost scales with the shape's coverage, and
`quality=` trades raymarch steps for speed. **Cons**: raymarched shaders are
intrinsically heavy at 1080p (measured full-frame: silk ~60ms/frame,
fire ~41ms — fine as partial-coverage content, slow as full-frame preview
backgrounds; plasma-style sine shaders are ~free); a broken GLSL file is
reported once on stderr and the effect is skipped.

| Preset | Source | Cost (full-frame 1080p) |
|---|---|---|
| `silk(speed, quality)` | fragcoord.xyz/s/ae4trrxh port | ~60ms/frame |
| `fire(speed, quality)` | "3D Fire" by @XorDev | ~41ms/frame |
| `starNest(speed, quality)` | "Star Nest" by Pablo Roman Andrioli (MIT) | ~19ms/frame |
| `plasma.glsl` (template) | classic sine plasma | ~free |

#### Where the pattern lives — `space=Space.…`

```python
sq.fillColor = starNest()                      # SHAPE (default) — follows its host
bg.fillColor = silk(space=Space.FRAME)         # a window onto a frame-wide pattern
sq.fillColor = fire(space=Space.ANCHOR)        # frozen where it started; growing UNCOVERS it
p = starNest(space=Space.GROUP)                # one pattern across several hosts
a.fillColor = p; b.fillColor = p
```

A math shader is measured against a box: the origin it draws around, and the
unit it scales by, both come from it. `Space` picks which box.

| Mode | Box | Behaviour under a moving/scaling host |
|---|---|---|
| `SHAPE` (default) | the host's own, this frame | pattern moves and scales WITH it — a growing shape MAGNIFIES the pattern |
| `FRAME` | the whole frame | pattern stays put; the host slides over it like a torch beam |
| `ANCHOR` | the host's, frozen at `fillShaderSince` | pattern pinned where it started — growing UNCOVERS it |
| `GROUP` | the union of every host sharing the instance | one pattern spanning them all |

How: `resolveEffectParams` picks the box, resolves origin + unit from it, and
patches them over the 3-float head. The GLSL never learns the mode, so
anchoring costs a shader file nothing. `ANCHOR` is RE-DERIVED from the
declared frame (`getMesh(getMetadata(fillShaderSince))`, memoised in `Core`),
never remembered from render history — so it survives preview scrubbing and
hot-reload instead of depending on which frame happened to render first.
**Pros**: `SHAPE` makes patterns behave like every other paint here
(gradients project in local mesh space, textures default to
`UVMapping.STRETCH`) and like Manim, where colour rides the mobject's points;
the other three are effects Manim can only reach by hand-masking a separate
static background. **Cons**: the box is an AABB, so no mode follows ROTATION
yet — a rotating host slides its pattern (`Space.Object`, an inverse matrix,
is the extension point). `GROUP` is a no-op on a `Text`, whose paint is
already one matted mesh spanning the word.

**Examples**: `test/visual/scenes/silk.py` (golden-tested at 2 frames),
`test/visual/scenes/shader_space.py` (all four modes, 2 frames),
`test/math_shader_test.py`, `feat.py`.

---

## Color & Gradients (`videocode/color.py`)

| Class | What it is |
|---|---|
| `rgba(r, g, b, a)` | Base color — also constructible from hex string (`rgba("#BBBBBB")`), supports `\|` operator to set alpha (`WHITE \| 0.5`) or override with another color (`BLUE_C \| BLACK`) |
| `LinearGradient(...)` | Multi-stop linear gradient, usable anywhere an `rgba` is (`fillColor=LinearGradient(...)`) |
| `RadialGradient(...)` | Multi-stop radial gradient |
| `ConicGradient(...)` | Multi-stop conic/angular gradient |

Gradients correctly respect holes on multi-contour shapes (e.g. letters with
holes like "o"/"a").

### Background — the `BG` script global

```python
BG = WHITE                          # anywhere in the script — that's it
BG = rgba(18, 32, 84)               # any plain color
BG = LinearGradient(RED_A, BLUE_B)  # gradients work too
```

How: assign a color to the module-level `BG` and stop thinking about it —
resolved after the scene runs, so position in the script doesn't matter. A
plain `rgba` becomes the renderer's clear color (zero draw cost, alpha
ignored); a gradient becomes one static full-frame `Rectangle` layered behind
everything. **Pros**: replaces the manual full-frame-rect + `background()` +
"remember to do it" dance; hot-reload safe. **Cons**: deliberately
color-only — an animated background (e.g. `Plane`) stays explicit
(`Plane().drift()` at the END of the script, so the drift covers the full
duration).

### Render size

```sh
./video-code --file scene.py                                    # 1920x1080
./video-code --file scene.py -w 1200 --height 1500 --generate out.mp4
```

The resolution is a **command-line concern only**: `-w`/`--width` and
`--height`, defaulting to 1920x1080. A scene cannot change it — assigning
`SCREEN_WIDTH` in a script rebinds that script's own global and nothing else,
because by then the surface is allocated and the world box is built. (There is
no `-h` short form: argparse reserves it for `--help`.)

Everything downstream is derived, never declared:

| | |
|---|---|
| `SCREEN_WIDTH` / `SCREEN_HEIGHT` | read from the renderer, in `videocode/constants.py` |
| `WORLD_WIDTH` / `WORLD_HEIGHT` | `screen / WORLD_TO_SCREEN_RATIO` — 16x9 at 1920x1080, 9x16 at 1080x1920 |
| `WORLD_OFFSET_X/Y`, `TOP_SIDE`, `BL`, `TR`, ... | from the world box |
| the Qt preview window | `screen * --windowRatio`, so it always has the output's shape |
| the editor's preview and its exports | `--editor -w 1080 --height 1920` makes, previews and exports a 1080x1920 scene |

How: `VC::makeConfig` reads the two flags, points the world->pixel transform at
them (`config::screen`/`screenOffset`) and exports `VC_SCREEN`, all before
`videocode` is imported — so `constants.py` builds its world box from the real
numbers on the first read. One direction, no negotiation: C++ decides, Python
is told. **Pros**: the world box, the preview surface and the encoder cannot
disagree, which is the failure that used to put every shape off-centre; and
one scene renders to any format without edits. **Cons**: a scene can't carry
its own format, so a project with several targets drives them from the command
line — `--for youtube,tiktok,square` does the several in one go. The world unit stays 120 px whatever the
resolution, so shapes keep their physical size and only the world BOX changes —
a portrait render doesn't shrink your content, it gives you 9x16 instead of
16x9 to place it in.

One process, several sizes — `constants.setScreen(width, height)`. The
import-time read above answers the normal case, where the resolution is known
before `videocode` loads. The visual-regression suite is the exception: it
renders landscape and portrait cases in a single interpreter, so `C++`'s
`applyScreenSize` calls `setScreen` to re-derive the world box in place. It
rebinds the resolution-derived names (`W`, `H`, `TOP_SIDE`, `BL`, …) in every
already-imported `videocode` module, because a star-import copies values. Call
it yourself only if you drive the renderer from an embedding of your own.

The one thing `setScreen` cannot rebind is a **default argument** — it was
evaluated when its module was imported, and no rebinding of a global reaches
it. So a template whose default depends on the world box takes `None` and
resolves in its body: `SplitView(marginX=None)` and `PositiveGraph(xRange=None)`
do exactly that. Follow suit in new templates, or they will silently lay
themselves out for the previous resolution.

**Examples**: `test/screen_test.py`, and the two portrait golden cases
`test/visual/scenes/aspect_portrait.py` / `split_rows.py` (the suite pins their
resolution in `kGoldenCases`, since a scene has no say).


Typed enums also live in `videocode/constants.py` (plus `BlendMode` in
`shader/vertexShader/blendMode.py`): `Direction.LEFT/RIGHT/TOP/BOTTOM` (slides,
wipes, transitions), `Axis.X/Y/BOTH` (shake), `UVMapping.STRETCH/RADIAL/CONIC`
(Image/Video), `BlendMode.NORMAL/MULTIPLY/SCREEN/ADD`.

Named colors and directional constants live in `videocode/constants.py`:
`WHITE`, `BLACK`, `TRANSPARENT`, `RED_A/B/C`, `BLUE_B/C`, etc., and
`UP`/`DOWN`/`LEFT`/`RIGHT`/`UR`/`UL`/`DR`/`DL`, `TOP_SIDE`/`BOTTOM_SIDE`/
`LEFT_SIDE`/`RIGHT_SIDE`, `TL`/`TR`/`BL`/`BR`, `ORIGIN`.

**Examples**: `test/visual/scenes/gradient.py`, `gradient_percent.py`,
`gradient_conic.py`, `gradient_holes.py`, `text_gradient.py`.

---

## Effects (`videocode/template/effect/`)

Standalone generator functions that build shader sequences. Call via `input.apply(*effect(input, ...))`.

### Core (`effect/core/`) — the main animation effects, also wired as `Input` methods

| Name | File | What it is |
|---|---|---|
| `moveTo`/`moveBy`, `groupMoveTo`/`groupMoveBy` | `moveTo.py` | Position easing (group variants preserve relative member layout) |
| `scaleTo`/`scaleBy` | `scaleTo.py` | Scale easing |
| `rotateTo`/`rotateBy` | `rotateTo.py` | Rotation easing |
| `alignTo` | `alignTo.py` | Align easing |
| `fadeTo` | `fadeTo.py` | Opacity easing |
| `click(low, up, start, duration, easing)` | `click.py` | Iterable of `scale` shaders producing a "press down/release" pulse — see `ParticlesRay`/`Button` usage |

### Other (`effect/other/`) — standalone effects, not exposed as Input methods

| Name | File | What it is |
|---|---|---|
| `highlight(input, scaleFactor, color, ...)` | `highlight.py` | Scale pulse + `fillColor` flash via `Easing.ThereAndBack`; `input` must be a `Polygon` |
| `typewriter(...)` | `typewriter.py` | Per-letter staggered reveal on a `Text` |
| `stagger(effect, every)` | `stagger.py` | The same effect on every member of a group, each starting `every` seconds after the previous — `Row(*cards).apply(stagger(popIn(), every=0.08))`; a `Text` staggers per letter; `every=0` is the plain effect |
| `shake(amplitude, frequency, axis=Axis.X, decay)` | `shake.py` | Error/attention shake (deterministic, group-rigid) |
| `popIn(...)` / `bounceIn(...)` / `spinIn(...)` / `blurIn(...)` | | Entrances: overshoot scale, gravity bounce, spin+scale, unblur |
| `slideIn(direction=Direction.LEFT, ...)` / `slideOut(...)` | `slide.py` | Slide + fade entrance/exit |
| `wipeIn(direction, ...)` / `wipeOut(...)` | `wipe.py` | Directional reveal/hide via animated crop |
| `pulse(scale, times, ...)` | `pulse.py` | There-and-back scale pulse (beat-sync's partner) |
| `zoomPunch(...)` / `flash(...)` / `jelly(...)` / `swing(...)` / `tada(...)` / `stamp(...)` | | Emphasis effects (Animate.css-style) |
| `kenBurns(...)` | `kenBurns.py` | Slow pan+zoom for stills |

### Montage (`effect/other/camera.py`, `impact.py`, `whipPan.py`, `spotlightOn.py`, `desaturate.py`, `vignetteIn.py`, `scope.py`, `glitchBurst.py`, `retime.py`)

Editing grammar for footage: a camera that never sits still, plus the beats
and grades that go with it. Coordinates are **generic** — a fraction of a box,
never a domain notion; turning "the third square of the fifth rank" into
`(x, y)` is the caller's job, videocode stays subject-agnostic.

Two coordinate spaces, on purpose, and they are NOT interchangeable:
- **camera moves** take fractions of the input's OWN box, (0,0) top-left —
  they move the mesh, so they must speak its geometry (`framing.py`);
- **light/grade shaders** take frame UV, (0,0) top-left of the FRAME — they
  run on rendered pixels and know nothing of the mesh.

| Name | File | What it is |
|---|---|---|
| `punchIn(zoom, start, duration, easing)` | `camera.py` | Slow continuous zoom; claims `scale` only, so it composes with a pan |
| `zoomTo(x, y, zoom, ...)` | `camera.py` | Zooms AND reframes so `(x, y)` lands at the frame centre |
| `snapZoom(x, y, zoom, hold, attack, release)` | `camera.py` | Violent in, hold, ease back — returns exactly to the origin |
| `travelling(fromX, fromY, toX, toY, zoom, ...)` | `camera.py` | Zoom set once, then a pan from one point to another |
| `reframe()` | `camera.py` | Snaps position/scale back to `(0, 0)` / `(1, 1)` — the camera moves are stateful, a reel chaining them resets between two |
| `impact(x, y, zoom, amplitude, frequency, ...)` | `impact.py` | Punch + decaying rumble as ONE effect (two effects would fight over `position`) |
| `whipPan(toX, toY, zoom, blur, ...)` | `whipPan.py` | Fast throw with a blur envelope — **degraded**: the blur is isotropic, there is no directional motion-blur shader |
| `spotlightOn(x, y, radius, softness, darkness, ...)` | `spotlightOn.py` | Round pool of light on a frame point, everything else dimmed |
| `zoneFocus(x, y, width, height, corner, ...)` | `spotlightOn.py` | Same, rectangular — for framing a region rather than a point |
| `desaturate(amount, ...)` / `vignetteIn(...)` / `vignetteBeat(...)` | `desaturate.py`, `vignetteIn.py` | Grades: drain the color, or close the corners (`Beat` = there-and-back) |
| `scope(ratio)` / `unscope(ratio)` | `scope.py` | Animate cinemascope bars in/out via `crop` |
| `glitchBurst(amount, slices, seed, blocks, ...)` | `glitchBurst.py` | One `glitch` + optional `pixelate` ramp — cannot ramp `amount`, `glitch` is time-driven and re-issuing it restarts its clock |

**Retiming** (`retime.py`) — `speedRamp`, `ralenti`, `accelere`,
`freezeFrame`, `rewind` are **not** `Effect`s: retiming changes which SOURCE
frame is decoded, which `Video` decides once at construction. They build
`speedRamps=` triples:

```python
Video("game.mov", speedRamps=[*accelere(at=0, duration=20, rate=4.0),
                              *ralenti(at=24, duration=2, rate=0.4)])
```

Sampling is nearest-frame with no blending at any rate, so `ralenti` is a
slow motion, not an interpolated one — there is no optical-flow retiming in
the engine.

`decimate(first, frames, ratio)` (also `retime.py`) is the one retiming helper
that builds `cuts=` rather than `speedRamps=`: a scene is always 30 fps and the
engine reads one source frame per scene frame, so a 60 fps source plays at half
speed unless every other frame is cut (`ratio = sourceFps / FRAMERATE`).

**Footage helpers** — what a reel needs before the first camera move:
`probeVideo(path)` (`utils/probe.py`) returns `(width, height, fps)` through
`ffprobe`, and `containSize(w, h)` (`effect/framing.py`) returns the world size
that fits a source in the frame without stretching or cropping.

**Shared ramp** (`effect/ramp.py`) — `dipAndReturn(peak, start, duration,
fade)` yields the `(value, time)` pairs a grade follows: rise over `fade`,
hold, fall back over `fade`. It emits one pair **per frame through the hold**,
because a fragment shader posed on a frame only applies to that frame: a
plateau emitted once left the middle of the window with no shader at all, and
a 2 s `spotlightOn` was visible for 0.35 s, gone for 1.3 s, then visible
again. `spotlightOn`, `zoneFocus` and `desaturate` all go through it.

**Example**: `chess_montage.py` (the named reel), `montage.py` (the game
itself: real moves, camera only),
`test/visual/scenes/montage_camera.py`, `montage_grade.py`.

**Transitions** (`transitions.py`) — plain functions animating TWO inputs at
once (not `.apply()` effects):

```python
crossfade(sceneA, sceneB, duration=0.8)
push(cardA, cardB, direction=Direction.LEFT, distance=4)
wipeBetween(shotA, shotB, direction=Direction.RIGHT)
dipToBlack(sceneA, sceneB, duration=0.6)
zoomThrough(clipA, clipB, zoom=1.6)
slideOver(sceneA, sceneB, direction=Direction.RIGHT)
```

How: call after positioning both inputs at their resting spots; the incoming
input should sit behind the outgoing one (`zIndex`) so nothing flashes early —
`slideOver` is the exception, its `incoming` covers `outgoing` so it must sit
ABOVE it, and `outgoing` itself is never touched.

Easing curves (`videocode/utils/bezier.py`):
- CSS-style cubic-beziers (`CubicBezier`): `Easing.Linear`, `Easing.In`,
  `Easing.Out`, `Easing.InOut`
- Manim-inspired rate functions (`Func`, ported from manim's
  `rate_functions`): `Easing.Smooth`, `Easing.RushInto`, `Easing.RushFrom`,
  `Easing.SlowInto`, `Easing.DoubleSmooth`, `Easing.ExponentialDecay` (0→1),
  and `Easing.ThereAndBack`, `Easing.ThereAndBackWithPause`, `Easing.Wiggle`
  (animate out and back to the start value — `f(0) == f(1) == 0`)
- Editor-style overshoots: `Easing.Back` (overshoot past 1 then settle),
  `Easing.Elastic` (springy oscillation), `Easing.Bounce` (gravity bounces)
- Custom rate functions: `Func(lambda t: ...)` wraps any `t in [0,1] -> m`
  callable as a `RateFunc`, usable anywhere `easing=` is accepted.
- Hand-drawn curves: `easing=CubicBezier(0.2, 0.9, 0.8, 0.1)` — the four
  control points, the same thing a preset is. The editor's curve on an effect
  row writes exactly that, and `curves()` is where it reads the presets from:
  every `Easing` that IS a `CubicBezier`, spelled as a scene writes it
  (`{"Easing.Out": (0.0, 0.0, 0.58, 1.0), ...}`).

---

## Running / Output (`src/Main.cpp`, `src/compiler/Compiler.cpp`)

| Flag | Effect |
|---|---|
| (none) | Live Qt preview window, hot-reloadable with `Ctrl+R` |
| `--file <path>` | Script to run (default `video.py`) |
| `--generate [out.mp4\|out.mov\|out.webm\|out.gif\|out.png]` | Headless render — the extension picks the format: `.mp4` = h264; `.mov` = ProRes 4444 with real per-pixel **alpha** (transparent background); `.webm` = VP9 with alpha; `.gif` = 2-pass palette (no alpha/audio); image ext → single frame. Audio (`Sound` inputs) muxed where the container allows. |
| `-w`/`--width`, `--height` | Output resolution in pixels (default 1920x1080). The only way to set it. See *Render size* |
| `--framerate` | Output fps — scenes are authored at 30fps and resampled |
| `--from <s\|name>` / `--to <s\|name>` | Render only that stretch of the scene — seconds (`--from 12.5`) or the name of a `timestamp()` written in it (`--from "show: rectangle"`). Frames are `[from, to)`; past the end clamps. Sounds keep their place: one that began before `--from` is heard from where the stretch enters it. With an image extension, `--from` picks the still. See *Render a stretch* |
| `--for <shapes>` | Render the scene once per named shape — `youtube`, `tiktok`, `square` — one file each, the shape in the filename. Each render RE-RUNS the scene at that resolution, so the scene lays itself out for it. With `--lint`, check the scene in each shape instead. See *One scene, every format* |
| `--set key=value` | Give a `param()` of the scene a value, read as its default's type. Repeatable. Also with `--lint` and `--editor`. See *One scene, many videos* |
| `--data rows.csv\|rows.json` | Render the scene once per row, each column a `param()`; `--generate "out/{name}.mp4"` names the files. See *One scene, many videos* |
| `--hwencode` | Hardware H.264 encode (videotoolbox, macOS) |
| `--showstack` / `--showtimeline` | Debug printing during generation |
| `--visual-test [--update-golden]` | Run/refresh the golden-frame visual-regression suite (`src/test/VisualTest.cpp`, `test/visual/golden/`) |

### Render a stretch — `--from` / `--to`

```bash
./video-code --file scene.py --generate fix.mp4 --from 12 --to 22     # ten seconds, not three minutes
./video-code --file scene.py --generate fix.mp4 --from "show: rectangle" --to "show: caption"
./video-code --file scene.py --generate still.png --from 12.5          # the frame at 12.5 s
```

A ten-second fix should not cost a whole render. Either bound is seconds or a
`timestamp("…")` name from the scene — the names are listed when one is not
found. `--from` alone runs to the end, `--to` alone starts at 0, and a bound
past the end is clamped, never refused. Audio is the whole timeline mixed as
before — every `Sound` delay and `Video` cut stays absolute — with the
stretch cut out of the result, so nothing is re-delayed and a sound that
started earlier is at the right moment. The frame indices are unchanged, so
`--from 12 --to 22` renders the same pixels frames 360–659 of the whole would.

### A contact sheet — `--sheet` / `--at`

```bash
./video-code --file scene.py --generate look.png --sheet 8 --from 0 --to 20
./video-code --file scene.py --generate look.png --at 0,3.9,"the camera"
```

Several moments side by side in one image, each labelled with its time. One
look shows the motion, which a single still never does.

`--sheet N` spreads N moments evenly across `--from`…`--to`. That is the right
picture when nothing says where to look. `--at` says exactly where instead —
seconds or `timestamp()` names, comma-separated — and then it decides how many
tiles there are. A scene that named its moments has already said which ones
matter, and spreading evenly across it spends tiles on stillness: eight even
samples of the tour draw the same picture twice.

### A scene checked without rendering — `--lint`

```bash
./video-code --lint --file scene.py
# scene.py:6: error: Sound starts at 6.00 s but the film is 1.03 s long, … [sound-after-end]
```

Runs the scene and says what is wrong with it, one
`file:line: error|warning: message [rule]` per line, without drawing a frame.
Exit 1 if any line is an error; warnings alone exit 0. The rules:

| Rule | Severity | What it catches |
|---|---|---|
| `scene-error` | error | the scene does not run — a negative `wait()` is one |
| `sound-after-end` | error | a `Sound` starting on or after the last frame: the mix is cut at the film's end |
| `before-start` | error | a write before frame 0, which the renderer skips, or a negative `Sound` delay |
| `never-visible` | warning | hidden or at opacity 0 on every frame |
| `last-frame-only` | warning | made after the final `wait()`, so on screen for one frame |
| `bad-value`, `contended-key` | as in the editor | what the Code pane already underlines |
| `param` | error | with `--set`/`--data`: a required `param()` nobody gave, a value that does not read as its type, a `--set` key no `param()` reads |
| `unread-column` | warning | with `--data`: a column no row's run read |
| `title-safe` | warning | a `Text` resting outside title safe — the inner 80 % of the frame — on a frame where it is on screen |

The same findings reach the editor, underlined in the Code pane and hatched on
the clip — except `last-frame-only`, which every line typed at the end of a
scene is until its `wait()` is. From Python it is
`videocode.serialize.lintSource(source, path)`, which returns the text and the
exit code.

`--lint --set …` and `--lint --data rows.csv` run the scene once per row with
that row's values, so a batch is checked before a frame of it is drawn; a finding
every row shares is said once.

`title-safe` is a question about a frame, so it is asked in each one the scene
will be rendered in: `--lint --for youtube,tiktok,square` re-runs the scene in
each shape, as the renders do, and without `--for` the `--width`/`--height`
frame is the one checked.

```bash
./video-code --lint --file scene.py --for youtube,tiktok
# scene.py:4: warning: Text leaves title safe in the tiktok (1080x1920) frame from frame 0 (0.00 s):
#   it runs 4 px past the left edge, and title safe keeps 108 px clear there — … [title-safe]
```

It says the line, the shape and the first frame, and how close the text comes
to the edge. "Resting": a frame counts when the glyph holds that box into the
next one, or it is the last — a title sliding in from off-screen crosses the
margin on purpose and is silent, and so is a text kept wholly off the frame.
The box is the renderer's own arithmetic, redone from the stack it reads
(`getTransformationMatrixFromMetadata` on the control points' bounding box):
the same pixel as a render for an upright text, a little generous for a turned
one. Under a moving camera only texts `pinToFrame()`d are checked, and members
of a `Composition` are not — the rule stands down rather than guess. The
editor does not underline it: its preview draws the same rectangle instead.

### Safe margins in the preview — `'`

The preview's guides, after Premiere's Program Monitor: **action safe** (90 %)
and **title safe** (80 %) outlined over the picture, and a small cross at its
centre. `'` (Premiere's key, rebindable on the keyboard board) or the `▣` in the
viewbar turns them on and off; the choice is kept with the keys in the dock
file. They are drawn over the picture's own rect, so they follow the letterbox
and every resize, and they are a guide only — the renderer never sees them,
nothing of them reaches `--generate`. Title safe is the lint's rectangle.

On a **9:16** frame (`--editor -w 1080 --height 1920`) the zones TikTok, Reels
and Shorts cover with their UI are shaded as well: the tabs at the top, the
button column on the right, the caption band at the bottom. The numbers are
one table in `qml/VideoCode/PreviewPanel.qml` (`platformZones`), in pixels of a
1080x1920 frame, the union of the three apps — and **approximate**: rounded
from creator safe-zone templates and the apps' ad guidelines, not measured
here; no app publishes them for an ordinary post, and every redesign moves
them.

`tell state` says whether they are on (`guides`) and the frame (`frame`), so a
screenshot's rectangles are not mistaken for the scene's.

### Reading the editor from outside — `tell verify`

```bash
./video-code tell verify                    # runs the scene, answers with everything
./video-code tell verify sheet=6 out=/tmp/look.png
```

One call that runs the scene and answers with what it made AND what it looks
like: the elements, the moments it named, whatever the engine warned about, and
a contact sheet on disk. Without it that is three calls an agent has to know to
chain — and "it ran" is not "it is right". The sheet is laid on the scene's own
`timestamp()` moments when it named any.

### Where an element IS — `Context.stateAt(index, frame)`

```python
Context.stateAt(0, 30)   # {"Position:x": 4.0, "Position:y": 0.0, "Opacity": 255.0, …}
```

The channels an element actually holds at one frame — position, scale, rotation,
opacity, align — plus any ARGUMENT something animates, under `Args:<name>`: a
`fill()` writes the colour it has reached, frame by frame. Read off the stack the
render draws from. The arguments of a
call say what a thing was *made with* and never change; this says where it *is*,
which is what every line above it has done to it by that frame. The editor's
element card shows it under the arguments — twice: the same argument names with
their values at the playhead, then a rule, then the transform channels. What has
moved is the only thing that differs between the two rows, which is what makes it
readable without comparing two texts. It is the reading half of the timecard.

An index no scene made answers with nothing rather than raising: a card left
open on an older run asks about an element that is gone.

### One scene, every format — `--for`

```bash
./video-code --file scene.py --generate film.mp4 --for youtube,tiktok,square
# film-youtube.mp4  1920x1080
# film-tiktok.mp4   1080x1920
# film-square.mp4   1080x1080
```

Named shapes, not numbers: what an author picks is where the film is watched,
and the pixels follow from it. `youtube` is 1920x1080, `tiktok` 1080x1920,
`square` 1080x1080; a name it does not know is refused with the list of the
ones it does.

Each shape is a **second run of the scene**, not a crop and not a scale of the
first. The world box is pointed at the shape's resolution (`applyScreenSize`
→ `setScreen`) before the script executes, so the scene reads the frame it is
actually in — `Split.AUTO` splits into columns at 16:9 and rows at 9:16, `W`/`H`
and `TOP_SIDE`/`BL` give the new box — and puts things somewhere else. Measured
in `test/every_format_test.py`: a marker in the first panel of a `Split.AUTO`
view sits a quarter of the way ACROSS the youtube frame and halfway down it, and
halfway across the tiktok frame and a quarter of the way DOWN — both axes move,
which no crop can do, and the wide render squashed into 1080x1920 lands it
somewhere the tall render has nothing.

Each render prints the `Generating` line it always did, with the shape and its
place in the run appended (`· tiktok, 2 of 3`). What a shape cannot do is said:
`--for` without `--generate` is refused rather than dropped, and `--width`/
`--height` given alongside are reported as unused rather than silently
outranked. A shape that fails stops the run, naming the ones that were not
rendered — a set of files that looks complete and is not is the worse outcome.

Not included: **loudness normalisation**. The roadmap line pairs it with this
feature, but it is a separate concern — it changes the audio of every render,
needs its own flag and its own measurement, and single-pass `loudnorm` is not
the two-pass measure the name implies.

### One scene, many videos — `param()`, `--set`, `--data`

```python
name  = param("name", "World")     # a str
score = param("score", 0)          # "12" arrives as 12
brand = param("brand", BLUE)       # "#ff8800" arrives as an rgba
title = param("title")             # no default: it must be given
```

```bash
./video-code --file card.py --generate card.mp4 --set name=Ada --set score=12
./video-code --file card.py --generate "out/{name}.mp4" --data people.csv
# out/Ada.mp4, out/Grace.mp4, … — one per row, each a fresh run of the scene
./video-code --lint --file card.py --data people.csv    # every row checked, nothing drawn
./video-code --editor --file card.py --set name=Ada     # preview one row
```

A scene written once and filled from outside — Remotion's *input props*.
`param(name, default)` returns the value given for `name`, else the default;
the editor gives nothing, so a template with defaults stays previewable. The
default's type is the parameter's type: a CSV cell is always text, and it
arrives as an `int`, a `float`, a `bool` (`true/false/yes/no/1/0`), an `rgba`
(`#rrggbb[aa]`) or an enum member (by name) when that is what the default is. A
value that does not read is refused, naming its row — never passed on as a
string that breaks three calls later.

`--data` takes a `.csv` (a header line, then one render per row) or a `.json`
(a list of objects). An empty cell is a value not given, so the default applies.
`{column}` in the `--generate` path is filled per row, made safe for a filename,
its folders created; without one, a batch is numbered (`out-1.mp4`,
`out-2.mp4`…). With `--for`, every row is rendered in every shape
(`out/Ada-tiktok.mp4`). `--set` gives one value to every row.

What would otherwise render N files quietly wrong is refused before the first
frame: a key in both `--set` and the data, a `{field}` that is no column or a
row leaves empty, two rows writing one file. What only a run can see — a
`--set` key no `param()` reads, a required one nobody gave — fails the render,
and `--lint` finds it without rendering. A `--data` column no row reads is a
warning at the end: a CSV often carries columns for the filename only. A row
that fails stops the batch, saying how many renders were not made.

The values reach the scene as the resolution does: C++ exports `VC_PARAMS`
(JSON) before each run, and `param()` reads it when it is called
(`videocode/params.py`).

`videocode/serialize.py` — `execScene()` (used by the C++ embed) and
`serializeScene()` (for CLI/inspection) turn a scene script into the JSON
action-stack representation the renderer consumes.

---

## Where things live (quick map)

```
videocode/
├── input/
│   ├── input.py          # Input base class — transform/animation API
│   ├── interface/         # Group, StatefulGroup, Offset, Interface
│   ├── shape/             # Polygon + all shape subclasses, text/, svg/
│   └── media/              # Image, Video, Sound
├── shader/
│   ├── vertexShader/      # geometry/transform shaders
│   └── fragmentShader/    # pixel post-processing shaders
├── template/
│   ├── input/             # composite inputs (Plane, Box, Button, Graph, ...)
│   └── effect/            # animation-sequence helper functions (core/, other/)
├── color.py               # rgba + gradients
├── constants.py           # world-space constants, named colors, directions
└── serialize.py           # scene -> JSON action stack

src/                        # C++ renderer (Vulkan), Qt window, ffmpeg encoder
test/visual/scenes/         # one small scene per feature, used by --visual-test
video.py                     # living demo script
```
