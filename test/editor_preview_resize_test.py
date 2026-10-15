#!/usr/bin/env python3
"""
The preview keeps its picture when the pane changes size.

A new size rebuilds the preview's renderer, and a clip's texture lived in the
one thrown away: after ⌘4 the pane showed a solid colour until the scene ran
again. Checked on a windowless editor driven through its socket — a frame
before the switch, ⌘4 through the native menu, a frame after. No window opens.

The meshes kept from the last frame, the scene's and each shape's own, named
the old renderer's textures too. That held by luck while the new sets landed
where the old ones had been; once a run had rebuilt the clip, its texture was
no longer the first, and ⌘3 at the same frame turned the preview black here —
and killed the editor with SIGSEGV in a window.

Run directly: `python3 test/editor_preview_resize_test.py`
"""

import json
import os
import socket
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, ".")
sys.path.insert(0, "test")

from helpers import check, needsRenderer, needsTool, section, summary

if not needsRenderer("the editor is the built binary") or not needsTool("ffmpeg", "the clip is made with it"):
    summary()
    sys.exit(0)

if sys.platform != "darwin":
    print("  (skipped: the layout is switched through the native menu bar, macOS only)")
    summary()
    sys.exit(0)

from PIL import Image, ImageStat

work = tempfile.mkdtemp(prefix="vc-resize-")
clip, scene, sock = f"{work}/clip.mp4", f"{work}/scene.py", f"/tmp/vc-resize-{os.getpid()}.sock"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=3", "-pix_fmt", "yuv420p", clip], check=True)
with open(scene, "w") as f:
    f.write(f"from videocode import *\nVideo({clip!r}, width=W, height=H)\nwait(2)\n")

editor = subprocess.Popen(
    ["./video-code", "--editor", "--check-chrome", "--serve", "--file", scene],
    env={**os.environ, "VC_SOCKET": sock, "VC_DOCK_FILE": f"{work}/dock.json"},
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
try:
    for _ in range(150):
        if os.path.exists(sock):
            break
        time.sleep(0.2)
    time.sleep(3)
    link = socket.socket(socket.AF_UNIX)
    link.connect(sock)
    wire = link.makefile("rw")

    def tell(**request) -> dict:
        wire.write(json.dumps(request) + "\n")
        wire.flush()
        return json.loads(wire.readline())

    # ---------------------------------------------------------------------------
    section("⌘4 makes the preview pane bigger, and the clip is still in it")

    tell(do="seek", at=1.0)
    time.sleep(0.8)
    tell(do="screenshot", out=f"{work}/before.png")
    tell(do="key", spec="Menu:4")
    time.sleep(1.2)
    tell(do="seek", at=1.1)
    time.sleep(0.8)
    tell(do="screenshot", out=f"{work}/after.png")

    tell(do="key", spec="Eval:source.text = source.text.replace('width=W, height=H', 'width=W * 0.8, height=H * 0.8')")
    tell(do="key", spec="Eval:app.executeScene()")
    time.sleep(1.5)
    tell(do="screenshot", out=f"{work}/ran.png")
    tell(do="key", spec="Menu:3")
    time.sleep(1.2)
    tell(do="screenshot", out=f"{work}/switched.png")
    tell(do="quit")
finally:
    time.sleep(0.5)
    editor.kill()

after = Image.open(f"{work}/after.png").convert("L")
w, h = after.size
# The middle of the window, which the preview pane covers once ⌘4 has given it the room.
middle = after.crop((int(w * 0.35), int(h * 0.3), int(w * 0.65), int(h * 0.6)))
spread = ImageStat.Stat(middle).stddev[0]
check(f"the pane shows the clip, not a flat colour (spread {spread:.1f})", spread > 20)

section("a run rebuilds the clip, then ⌘3 at the same frame")

switched = Image.open(f"{work}/switched.png").convert("L")
w, h = switched.size
# Vibe Editing, as a fresh dock lays it out, puts the preview on the left; the
# shrunk clip covers the middle of it.
middle = switched.crop((int(w * 0.12), int(h * 0.32), int(w * 0.5), int(h * 0.62)))
spread = ImageStat.Stat(middle).stddev[0]
check(f"the pane shows the rebuilt clip, not black (spread {spread:.1f})", spread > 20)

summary()
