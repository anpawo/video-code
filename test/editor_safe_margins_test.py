#!/usr/bin/env python3
"""
The preview's safe margins: drawn over the picture's own rect, gone when they
are off, remembered across a restart, and on a 9:16 frame the zones TikTok,
Reels and Shorts cover.

Checked on a windowless editor driven through its socket, one per frame shape.
The toggle is reached through the chrome's own function rather than the `'`
key: a synthetic QKeyEvent never reaches Qt's shortcut map (see
editor_keys_test.py), so the key is checked where it is decided — the keymap.
No window opens.

Run directly: `python3 test/editor_safe_margins_test.py` (`VC_BINARY=./build/video-code`
to check a fresh build rather than the copy at the root).
"""

import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, ".")
sys.path.insert(0, "test")

from helpers import check, needsTool, section, summary

binary = os.environ.get("VC_BINARY", "./video-code")
if not needsTool(binary, "the editor is the built binary"):
    summary()
    sys.exit(0)
try:
    from PIL import Image, ImageChops
except ImportError:
    print("  (skipped: PIL reads the screenshots)")
    summary()
    sys.exit(0)

work = tempfile.mkdtemp(prefix="vc-guides-")
scene = f"{work}/scene.py"
# One flat colour: anything that changes on screen when the guides come on is
# the guides.
with open(scene, "w") as f:
    f.write("from videocode import *\nRectangle(width=W, height=H, fillColor=rgba(40, 60, 90), strokeColor=TRANSPARENT)\nwait(1)\n")


class Editor:
    def __init__(self, *size: str):
        # In /tmp, not beside the scene: a socket's path stops at 104 bytes, and
        # the temporary folder of a session can already be 80 of them.
        self.sock = f"/tmp/vc-guides-{os.getpid()}-{len(size)}-{time.monotonic_ns()}.sock"
        self.log = open(f"{work}/editor.log", "a+")
        self.process = subprocess.Popen(
            [binary, "--editor", "--check-chrome", "--serve", "--file", scene, *size],
            env={**os.environ, "VC_SOCKET": self.sock, "VC_DOCK_FILE": f"{work}/dock.json",
                 "VC_COLORS_FILE": f"{work}/colors.json"},
            stdout=self.log, stderr=subprocess.STDOUT,
        )
        for _ in range(150):
            if os.path.exists(self.sock):
                break
            time.sleep(0.2)
        time.sleep(2.5)
        link = socket.socket(socket.AF_UNIX)
        link.connect(self.sock)
        self.wire = link.makefile("rw")

    def tell(self, **request) -> dict:
        self.wire.write(json.dumps(request) + "\n")
        self.wire.flush()
        return json.loads(self.wire.readline())

    def shot(self, name: str) -> Image.Image:
        time.sleep(0.6)
        self.tell(do="screenshot", out=f"{work}/{name}.png")
        return Image.open(f"{work}/{name}.png").convert("RGB")

    def toggle(self) -> None:
        self.tell(do="key", spec="Eval:toggleSafeMargins()")

    def said(self, expression: str) -> str:
        """A QML expression's value, read back off the editor's stdout."""
        self.tell(do="key", spec=f"Eval:{expression}")
        time.sleep(0.3)
        self.log.seek(0)
        found = re.findall(rf"Probed the expression {re.escape(expression)} → (.*)$", self.log.read(), re.M)
        return found[-1] if found else ""

    def quit(self) -> None:
        try:
            self.tell(do="quit")
        finally:
            time.sleep(0.5)
            self.process.kill()


def box(a: Image.Image, b: Image.Image) -> tuple[int, int, int, int] | None:
    return ImageChops.difference(a, b).convert("L").point(lambda v: 255 if v > 12 else 0).getbbox()


def picture(shot: Image.Image) -> tuple[int, int, int, int]:
    """Where the picture is: the scene is one flat colour, and nothing else in the chrome is that colour."""
    flat = Image.new("RGB", shot.size, (40, 60, 90))
    mask = ImageChops.difference(shot, flat).convert("L").point(lambda v: 1 if v < 8 else 0)
    w, h = mask.size
    pixels = mask.load()
    # By rows and columns that are mostly that colour, so a stray pixel of the
    # same shade somewhere in the chrome does not stretch the rect to it.
    rows = [sum(pixels[x, y] for x in range(w)) for y in range(h)]
    cols = [sum(pixels[x, y] for y in range(h)) for x in range(w)]
    ys = [y for y, n in enumerate(rows) if n > max(rows) / 2]
    xs = [x for x, n in enumerate(cols) if n > max(cols) / 2]
    assert xs and ys, "the scene's colour is nowhere on screen"
    return (xs[0], ys[0], xs[-1] + 1, ys[-1] + 1)


def within(shot: Image.Image, other: Image.Image, rect: tuple[int, int, int, int]) -> tuple[float, ...] | None:
    """What changed over the picture, as fractions of it — the viewbar's button changes too, and is not the guide."""
    drawn = box(shot.crop(rect), other.crop(rect))
    if drawn is None:
        return None
    w, h = rect[2] - rect[0], rect[3] - rect[1]
    return (drawn[0] / w, drawn[1] / h, drawn[2] / w, drawn[3] / h)


# ---------------------------------------------------------------------------
section("16:9 — two rectangles over the picture, nothing else")

editor = Editor()
try:
    state = editor.tell(do="state")
    check(f"off by default, and the frame is said ({state.get('frame')})",
          state.get("guides") is False and state.get("frame") == {"width": 1920, "height": 1080})
    check("the key is ' — Premiere's — and nobody else holds it",
          editor.said('Keymap.combo("safeMargins")') == '["\'"]' and editor.said('Keymap.holder("\'", "safeMargins")') == '[""]')
    off = editor.shot("wide-off")
    editor.toggle()
    on = editor.shot("wide-on")
    check("on, and said so", editor.tell(do="state").get("guides") is True)
    rect = picture(off)
    check(f"the picture is letterboxed 16:9 in the pane ({rect})", abs((rect[2] - rect[0]) / (rect[3] - rect[1]) - 16 / 9) < 0.03)
    drawn = within(off, on, rect)
    # The outermost thing drawn is action safe, 5 % in from every edge of the
    # picture — of the picture, not of the pane around it.
    check(f"the outermost line is action safe, 5 % in ({drawn and [round(v, 3) for v in drawn]})",
          drawn is not None and all(abs(a - b) < 0.012 for a, b in zip(drawn, (0.05, 0.05, 0.95, 0.95))))
    editor.toggle()
    # Over the picture only: the code pane's caret blinks between two shots.
    check("off again leaves no trace on the picture", within(off, editor.shot("wide-off-again"), rect) is None)
    editor.toggle()
finally:
    editor.quit()

with open(f"{work}/dock.json") as f:
    check("remembered in the dock file, with the keys", json.load(f).get("safeMargins") is True)

# ---------------------------------------------------------------------------
section("9:16 — the platform zones, from edge to edge")

editor = Editor("--width", "1080", "--height", "1920")
try:
    state = editor.tell(do="state")
    check(f"a restart opens with them on, in the frame it was given ({state.get('frame')})",
          state.get("guides") is True and state.get("frame") == {"width": 1080, "height": 1920})
    on = editor.shot("tall-on")
    editor.toggle()
    off = editor.shot("tall-off")
    rect = picture(off)
    check(f"the picture is letterboxed 9:16 ({rect})", abs((rect[2] - rect[0]) / (rect[3] - rect[1]) - 9 / 16) < 0.02)
    drawn = within(off, on, rect)
    # The tabs run along the top and the caption band along the bottom, both
    # the picture's full width: what changed reaches every edge of it.
    check(f"the zones reach every edge of the picture ({drawn and [round(v, 3) for v in drawn]})",
          drawn is not None and all(abs(a - b) < 0.012 for a, b in zip(drawn, (0, 0, 1, 1))))
finally:
    editor.quit()

summary()
