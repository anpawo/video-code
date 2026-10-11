#!/usr/bin/env python3


from __future__ import annotations

import re
import subprocess
from functools import cache

from pathlib import Path
from videocode.ty import *
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import freetype
    from videocode.input.shape.text.Text import Letter


_FONT_DIR = Path(__file__).parents[4] / "assets" / "fonts"
_STEPS = 4
_TAB_SIZE = 4
_FT_FLAGS = 1 | 2 | 8  # FT_LOAD_NO_SCALE | FT_LOAD_NO_HINTING | FT_LOAD_NO_BITMAP

# An opening or closing tag, or an ASS override block (`{\an8}`) — a subtitle
# file is full of both and means neither to be drawn.
_TAG_RE = re.compile(r"<(/?)(\w+)([^>]*)>|\{\\[^}]*\}")
_COLOR_RE = re.compile(r"""color\s*=\s*["']?(#[0-9A-Fa-f]{3,8})""")
# `bold | "a < b"` writes `&lt;` — the only way a `<` reaches the letters
# without _TAG_RE reading it. Just these three: `html.unescape` also turns a
# hand-written `&copy 2020` into `©`.
_ENTITY_RE = re.compile(r"&(lt|gt|amp);")
_ENTITIES = {"lt": "<", "gt": ">", "amp": "&"}

#: (bold, italic, color) — what one run of characters is shaped and painted with.
type runStyle = tuple[bool, bool, maybe[rgba]]
type run = tuple[int, int, bool, bool, maybe[rgba]]
_PLAIN: runStyle = (False, False, None)


@cache
def fontPath(family: str, bold: bool, italic: bool) -> str:
    styles = ["BoldItalic", "Bold-Italic", "Bold_Italic"] if bold and italic else ["Bold"] if bold else ["Italic"] if italic else ["Regular", ""]
    if _FONT_DIR.is_dir():
        for style in styles:
            for ext in (".ttf", ".otf"):
                for sep in ("-", " ", "_", ""):
                    p = _FONT_DIR / f"{family}{sep}{style}{ext}"
                    if p.exists():
                        return str(p)
    fc_style = "Bold Italic" if bold and italic else "Bold" if bold else "Italic" if italic else "Regular"
    try:
        r = subprocess.run(
            ["fc-match", f"{family}:style={fc_style}", "--format=%{file}"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    raise FileNotFoundError(f"Font not found: {family!r} bold={bold} italic={italic}")


@cache
def loadFaces(path: str) -> tuple["freetype.Face", Any, int, float, tuple[float, float]]:
    # Imported lazily: freetype (~15ms) and uharfbuzz (~10ms) are only needed
    # when a scene actually uses Text, but Text is imported unconditionally
    # by videocode/__init__.py.
    import freetype
    from uharfbuzz import Blob as HBBlob, Font as HBFont, Face as HBFace  # type: ignore[import-untyped]

    ft = freetype.Face(path)
    upem = ft.units_per_EM
    blob = HBBlob(Path(path).read_bytes())
    hb_font = HBFont(HBFace(blob))
    hb_font.scale = (upem, upem)

    # Get cap height (keep existing code)
    try:
        ft.load_char(ord("H"), _FT_FLAGS)
        pts = ft.glyph.outline.points
        capH = float(max(p[1] for p in pts)) if pts else float(upem) * 0.7
    except Exception:
        capH = float(upem) * 0.7

    return ft, hb_font, upem, capH, (float(ft.descender), float(ft.ascender))


def shape(text: str, hb_font: Any, features: dict[str, bool] | None = None) -> tuple[list, list]:
    from uharfbuzz import Buffer as HBBuffer, shape as hb_shape  # type: ignore[import-untyped]

    buf = HBBuffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb_shape(hb_font, buf, features or {})
    return buf.glyph_infos, buf.glyph_positions


def walkContourQuadratics(rawPts: list, tags: list[int]) -> list[tuple[float, float]]:
    """
    Closed anchor-handle pairs [a0, h0, a1, h1, …] from one FreeType contour.

    Conic (TrueType quadratic) segments pass through as TRUE quadratics — the
    renderer tessellates them adaptively to on-screen pixel size, so glyphs
    stay smooth at any fontSize (fixed-step sampling left visible kinks on big
    letters). Straight segments get midpoint handles; cubic segments (CFF
    fonts) are still sampled at _STEPS and emitted as straight pairs.
    """
    n = len(rawPts)
    if n < 2:
        return []
    pts = [(float(p[0]), float(p[1])) for p in rawPts]
    tg = [t & 3 for t in tags]
    ON, CONIC, CUBIC = 1, 0, 2

    start = next((k for k in range(n) if tg[k] == ON), None)
    if start is None:
        # All-off-curve contour (TrueType allows it): the implied on-curve
        # midpoint between the last and first control points starts the path.
        pts = [((pts[-1][0] + pts[0][0]) / 2, (pts[-1][1] + pts[0][1]) / 2)] + pts
        tg = [ON] + tg
        n += 1
        start = 0
    pts = pts[start:] + pts[:start]
    tg = tg[start:] + tg[:start]

    pairs: list[tuple[float, float]] = []
    cur = pts[0]

    def line(to: tuple[float, float]):
        nonlocal cur
        if to == cur:
            return
        pairs.append(cur)
        pairs.append(((cur[0] + to[0]) / 2, (cur[1] + to[1]) / 2))
        cur = to

    i = 1
    while i < n:
        if tg[i] == ON:
            line(pts[i])
            i += 1
        elif tg[i] == CUBIC and i + 2 < n:
            x0, y0 = cur
            x1, y1 = pts[i]
            x2, y2 = pts[i + 1]
            x3, y3 = (
                pts[i + 2]
                if tg[i + 2] == ON
                else (
                    (pts[i + 1][0] + pts[(i + 2) % n][0]) / 2,
                    (pts[i + 1][1] + pts[(i + 2) % n][1]) / 2,
                )
            )
            for s in range(1, _STEPS + 1):
                t = s / _STEPS
                mt = 1 - t
                line(
                    (
                        mt**3 * x0 + 3 * mt**2 * t * x1 + 3 * mt * t**2 * x2 + t**3 * x3,
                        mt**3 * y0 + 3 * mt**2 * t * y1 + 3 * mt * t**2 * y2 + t**3 * y3,
                    )
                )
            i += 3 if i + 2 < n and tg[i + 2] == ON else 2
        else:  # CONIC run (or stray CUBIC tag)
            ctrls: list[tuple[float, float]] = [pts[i]]
            j = i + 1
            while j < n and tg[j] == CONIC:
                ctrls.append(pts[j])
                j += 1
            # The run ends on the next on-curve point, or closes back to the
            # contour start when the conic is the trailing segment.
            endPt = pts[j] if j < n else pts[0]
            for k, ctrl in enumerate(ctrls):
                nxt = ((ctrl[0] + ctrls[k + 1][0]) / 2, (ctrl[1] + ctrls[k + 1][1]) / 2) if k < len(ctrls) - 1 else endPt
                pairs.append(cur)
                pairs.append(ctrl)
                cur = nxt
            i = j + (1 if j < n and tg[j] == ON else 0)

    # Close the path back to the first anchor with a straight segment if the
    # walk didn't already end there (conic closures end exactly at pts[0]).
    line(pts[0])
    return pairs


@cache
def _glyphContours(path: str, glyphId: int) -> tuple[tuple[tuple[float, float], ...], ...]:
    """
    Unscaled per-contour control points (anchor-handle pairs) in font units.

    Contours stay separate — the renderer fills outer+holes via earcut-with-holes
    and strokes each contour on its own, so no bridge edges exist to be stroked
    or to break at partial opacity.
    """
    ft, *_ = loadFaces(path)
    ft.load_glyph(glyphId, _FT_FLAGS)
    ol = ft.glyph.outline
    if not ol.points:
        return ()
    raw = list(ol.points)
    tags = list(ol.tags)
    ends = list(ol.contours)
    contours: list[tuple[tuple[float, float], ...]] = []
    start = 0
    for end in ends:
        pairs = walkContourQuadratics(raw[start : end + 1], tags[start : end + 1])
        if len(pairs) >= 6:
            # Reversed to keep the same winding the legacy vertex pathway
            # produced (it iterated reversed(verts)) — stroke extrusion
            # direction depends on it.
            contours.append(tuple(reversePairs(pairs)))
        start = end + 1
    return tuple(contours)


def _glyphVerts(path: str, glyphId: int) -> list[tuple[float, float]]:
    """Flattened control points across all contours — bbox/min computations only."""
    return [p for c in _glyphContours(path, glyphId) for p in c]


def reversePairs(pairs: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """
    Reverse the winding of a closed anchor-handle pair list.

    With anchors A0..Am-1 and handles H0..Hm-1 (Hi sits between Ai and Ai+1),
    the reversed path is [A0, Hm-1, Am-1, Hm-2, …, A1, H0] — same curves,
    opposite traversal direction.
    """
    anchors = pairs[0::2]
    handles = pairs[1::2]
    m = len(anchors)
    out: list[tuple[float, float]] = [anchors[0]]
    for k in range(1, m):
        out.append(handles[m - k])
        out.append(anchors[m - k])
    out.append(handles[0])
    return out


def _markupColor(attributes: str) -> maybe[rgba]:
    """`color="#FF6A00"` out of a tag's attributes — anything else is no colour."""
    match = _COLOR_RE.search(attributes)
    if match is None:
        return None
    hexa = match.group(1).lstrip("#")
    if len(hexa) == 3:  # #f00, what a hand-written cue writes
        hexa = "".join(c * 2 for c in hexa)
    return rgba(f"#{hexa}") if len(hexa) in (6, 8) else None


def parseMarkup(markup: str) -> tuple[str, tuple[run, ...]]:
    r"""
    Split `<b>`/`<i>`/`<font color=…>` markup into plain text and styled runs.

    A run is (start, end, bold, italic, color) in PLAIN-character indices —
    the indices `buildLetterData` needs, the tags themselves being gone by
    then. `<span color=…>` reads like `<font>`, and the two nest.

    Everything else that looks like a tag — `<u>`, `{\an8}`, an unknown name —
    is STRIPPED rather than drawn: a subtitle file saying `{\an8}<b>Loud</b>`
    never means the braces to reach the screen, and a `Text` drew all 48
    characters of that cue as glyphs.
    """
    plain: list[str] = []
    runs: list[run] = []
    colors: list[maybe[rgba]] = []
    bold = italic = 0
    length = start = 0
    current: runStyle = _PLAIN
    pos = 0

    for tag in _TAG_RE.finditer(markup):
        chunk = _ENTITY_RE.sub(lambda m: _ENTITIES[m.group(1)], markup[pos : tag.start()])
        plain.append(chunk)
        length += len(chunk)
        pos = tag.end()

        closing, name = tag.group(1) == "/", (tag.group(2) or "").lower()
        if name == "b":
            bold = max(bold - 1, 0) if closing else bold + 1
        elif name == "i":
            italic = max(italic - 1, 0) if closing else italic + 1
        elif name in ("font", "span"):
            # Pushed even when the tag names no colour, so its `</font>` pops
            # its own entry and not the one an enclosing tag opened.
            if closing:
                if colors:
                    colors.pop()
            else:
                colors.append(_markupColor(tag.group(3)))

        new: runStyle = (bold > 0, italic > 0, next((c for c in reversed(colors) if c is not None), None))
        if new != current:
            if length > start and current != _PLAIN:
                runs.append((start, length, current[0], current[1], current[2]))
            start, current = length, new

    tail = _ENTITY_RE.sub(lambda m: _ENTITIES[m.group(1)], markup[pos:])
    plain.append(tail)
    length += len(tail)
    if length > start and current != _PLAIN:
        runs.append((start, length, current[0], current[1], current[2]))

    return "".join(plain), tuple(runs)


def _runSegments(line: str, offset: int, runs: maybe[tuple[run, ...]], bold: bool, italic: bool) -> list[tuple[str, runStyle]]:
    """
    The line cut where a run starts or ends — one shaping call per piece.

    `offset` is where the line begins in the text the runs were measured
    against. No runs means one piece, which is what keeps a plain `Text`
    shaping exactly the string it always shaped.
    """
    if not runs:
        return [(line, (bold, italic, None))]

    styles: list[runStyle] = [(bold, italic, None)] * len(line)
    for begin, end, b, i, color in runs:
        for k in range(max(begin - offset, 0), min(end - offset, len(line))):
            styles[k] = (bold or b, italic or i, color)

    pieces: list[tuple[list[str], runStyle]] = []
    for char, st in zip(line, styles):
        if pieces and pieces[-1][1] == st:
            pieces[-1][0].append(char)
        else:
            pieces.append(([char], st))
    return [("".join(chars), st) for chars, st in pieces]


@cache
def buildLetterData(
    text: str,
    fontSize: float,
    fontFamily: str,
    bold: bool,
    italic: bool,
    runs: maybe[tuple[run, ...]] = None,
    letterSpacing: float = 0.0,
) -> list[tuple[str, float, float, runStyle]]:
    """
    Returns (char, x_offset, y_offset, style) for each rendered glyph.
    Newlines split the text into lines; each subsequent line is offset downward
    by one line height (ascender − descender, scaled). Tabs expand to the next
    _TAB_SIZE-column stop before shaping — fonts carry no U+0009 glyph, so
    HarfBuzz would otherwise map a tab to .notdef and draw a tofu box.

    `runs` (see `parseMarkup`) restyles slices of the text: each one is shaped
    with its OWN face, the pen carrying across, so a bold word inside a regular
    line advances by bold widths. The line's height and baseline stay on the
    base face, so a run never moves the line it sits in.
    """
    path = fontPath(fontFamily, bold, italic)
    _, baseFont, _, capH, (desc, asc) = loadFaces(path)
    baseScale = fontSize / capH
    lineHeight = (asc - desc) * baseScale

    result: list[tuple[str, float, float, runStyle]] = []

    lineStart = 0
    for lineIdx, rawLine in enumerate(text.split("\n")):
        yBase = -lineIdx * lineHeight
        cx = 0.0

        for segment, st in _runSegments(rawLine, lineStart, runs, bold, italic):
            # Expanded before shaping so info.cluster keeps indexing the same string.
            line = segment.expandtabs(_TAB_SIZE)
            if not line:
                continue
            if (st[0], st[1]) == (bold, italic):
                segPath, hbFont, scale = path, baseFont, baseScale
            else:
                # A run scales by its OWN capH — the one `Letter` will scale
                # its outline by. Off the base face's, a bold run came out
                # subtly mis-sized against its own glyphs.
                segPath = fontPath(fontFamily, st[0], st[1])
                _, hbFont, _, segCapH, _ = loadFaces(segPath)
                scale = fontSize / segCapH
            infos, positions = shape(line, hbFont)

            for info, pos in zip(infos, positions):
                xOff = cx + pos.x_offset * scale
                yOff = yBase + pos.y_offset * scale
                cached = _glyphVerts(segPath, info.codepoint)
                if cached:
                    verts = [(x * scale, y * scale) for x, y in cached]
                    char = line[info.cluster] if info.cluster < len(line) else ""
                    result.append((char, xOff + min(v[0] for v in verts), yOff + min(v[1] for v in verts), st))
                cx += pos.x_advance * scale + letterSpacing * fontSize

        lineStart += len(rawLine) + 1

    return result


@cache
def lineAnchor(fontFamily: str, bold: bool, italic: bool, fontSize: float, alignY: float) -> float:
    path = fontPath(fontFamily, bold, italic)
    _, _, _, capH, (desc, asc) = loadFaces(path)
    scale = fontSize / capH
    return desc * scale + alignY * (asc - desc) * scale


def buildLetters(
    text: str,
    fontSize: float,
    fontFamily: str,
    bold: bool,
    italic: bool,
    fillColor: rgba,
    strokeColor: rgba,
    strokeWidth: float,
    runs: maybe[tuple[run, ...]] = None,
) -> list[Letter]:
    from videocode.input.shape.text.Text import Letter

    letters: list[Letter] = []
    for char, _x, _y, (isBold, isItalic, color) in buildLetterData(text, fontSize, fontFamily, bold, italic, runs=runs):
        letter = Letter(
            char=char,
            fontSize=fontSize,
            fontFamily=fontFamily,
            bold=isBold,
            italic=isItalic,
            fillColor=fillColor if color is None else color,
            strokeColor=strokeColor,
            strokeWidth=strokeWidth,
        )
        letters.append(letter)

    return letters
