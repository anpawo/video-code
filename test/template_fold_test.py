#!/usr/bin/env python3
"""
A template called from the scene is one clip, and the Inspector edits its values.

`titleCard(...)` lives in a file beside the scene and makes a rectangle and a
word. On the timeline each call is one clip named after it, not the rows of
titlecard.py's lines; the Inspector shows the template's own parameters, read
from the call and written back to it; its "parts" row opens the clip into a
block over its rows, where its own call to caption() is a clip, and a block
of its own once opened too. The same windowless editor also answers two neighbours: the zoom
reaches the whole of a 200 s scene, and the code pane draws a long line across
its whole width rather than stopping halfway under a blank block.

Run directly: `python3 test/template_fold_test.py`
"""

import json
import os
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, ".")
sys.path.insert(0, "test")

from helpers import check, needsRenderer, section, summary

if not needsRenderer("the timeline and the Inspector are the chrome's"):
    summary()
    sys.exit(0)

SCENE = "test/template_fold/scene.py"
SOCKET = f"/tmp/videocode-template-{os.getpid()}.sock"
log = tempfile.NamedTemporaryFile(suffix=".log", delete=False)
dock = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
shot = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
dock.close()
shot.close()
env = {**os.environ, "VC_SOCKET": SOCKET, "VC_DOCK_FILE": dock.name}

ROWS = "JSON.stringify(liveScene.elements.map((r) => [r.n, r.kind, r.members.length]))"
SHAPE = "JSON.stringify(liveScene.elements.map((r) => [r.n, r.kind, r.depth, r.lanes === undefined || !r.open ? 0 : r.lanes]))"

# Each template block drawn on the timeline: [first lane, lanes covered], the
# lanes counted from the first block's, which is on the first lane.
BLOCKS = ("JSON.stringify((function(){ const out = [] ; const walk = (i) => { if (i.outset !== undefined && i.visible)"
          " out.push([i.y / timeline.laneHeight, Math.round((i.height + 2 + 2 * i.depth) / timeline.laneHeight)]) ;"
          " for (const c of i.children) walk(c) } ; walk(timeline) ; out.sort((a, b) => a[0] - b[0]) ;"
          " return out.map((b) => [Math.round(b[0] - out[0][0]), b[1]]) })())")

# The code pane's text, where it sits in the window, and line 6 — the long
# comment — in the same frame: [paneX, paneWidth, lineY, lineHeight, windowWidth].
PANE = ("JSON.stringify((function(){ const find = (i) => { if (i.currentLine !== undefined && i.persistentSelection !== undefined) return i ;"
        " for (const c of i.children) { const r = find(c) ; if (r !== null) return r } return null } ;"
        " const ed = find(source) ; const fl = ed.parent.parent ; const p = fl.mapToItem(null, 0, 0) ;"
        " const r = ed.positionToRectangle(ed.text.split('\\n').slice(0, 5).join('\\n').length + 1) ;"
        " const q = ed.mapToItem(null, 0, r.y) ; return [p.x, fl.width, q.y, r.height, app.width] })())")


def tell(*args: str) -> dict:
    run = subprocess.run(["./video-code", "tell", *args], env=env, capture_output=True, text=True, timeout=60)
    try:
        return json.loads(run.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"ok": False}


def probe(expression: str):
    tell("key", f"spec=Eval:{expression}")
    with open(log.name) as out:
        said = out.read()
    answers = [one for one in said.splitlines() if one.startswith("Probed the expression")]
    if not answers:
        raise AssertionError(f"the editor did not answer the probe `{expression}`.\nWhat it said instead:\n{said[-3000:] or '(nothing at all)'}")
    return json.loads(answers[-1][len("Probed the expression ") + len(expression) + 3 :])[0]


editor = subprocess.Popen(["./video-code", "--editor", "--check-chrome", "--serve", "--file", SCENE],
                          env=env, stdout=log, stderr=subprocess.STDOUT)
try:
    deadline = time.time() + 30
    while time.time() < deadline and not tell("state").get("ok"):
        time.sleep(0.5)

    section("a template call is one clip")
    rows = json.loads(probe(ROWS))
    check(f"two calls, two clips, and the square beside them ({rows})",
          [r[:2] for r in rows] == [["titleCard", "template"], ["titleCard", "template"], ["square", "polygon"]])
    check("each clip holds what it made: the rectangle, and the call that writes the word", rows[0][2] == 2 and rows[1][2] == 2)

    section("the Inspector reads its values off the call")
    probe("app.inspect(liveScene.elements[0])")
    values = json.loads(probe("JSON.stringify(inspector.argRows.map((r) => [r.label, r.value, r.isDefault]))"))
    check(f"its own parameters, written or not ({values})",
          values == [["title", '"One"', False], ["color", "BLUE_C", True]])
    probe("inspector.argumentWritten(inspector.element, inspector.cls, 'title', '\"Uno\"')")
    line = probe("source.text").split("\n")[6]
    check(f"a value typed there is written where the call has it, by position ({line})", line == 'titleCard("Uno")')
    probe("app.inspect(liveScene.elements[1])")
    values = json.loads(probe("JSON.stringify(inspector.argRows.map((r) => [r.label, r.value]))"))
    check(f"and by name, on a call that names them ({values})", values == [["title", '"Two"'], ["color", "RED_A"]])

    section("its parts, when asked for, in a block")
    probe("inspector.partsShown(inspector.element, true)")
    shape = json.loads(probe(SHAPE))
    check(f"each clip is followed by its rectangle and its own call to caption(), a clip too ({shape})",
          [r[:2] for r in shape] == [["titleCard", "template"], ["Rectangle", "polygon"], ["caption", "template"],
                                     ["titleCard", "template"], ["Rectangle", "polygon"], ["caption", "template"], ["square", "polygon"]])
    check("the block of each covers its own lane and the two inside it", shape[0][3] == 3 and shape[3][3] == 3)
    check("drawn as one frame per block", json.loads(probe(BLOCKS)) == [[0, 3], [3, 3]])

    probe("app.unfold(liveScene.elements[2], true)")
    shape = json.loads(probe(SHAPE))
    check(f"the call inside opens as a block of its own, a level down ({shape})",
          [r[1:] for r in shape[:4]] == [["template", 0, 4], ["polygon", 1, 0], ["template", 1, 2], ["polygon", 2, 0]])
    check("framed inside the outer one", json.loads(probe(BLOCKS)) == [[0, 4], [2, 2], [4, 4], [6, 2]])
    probe("app.unfold(liveScene.elements[2], false)")
    probe("app.unfold(liveScene.elements[0], false)")
    check("and folded again", len(json.loads(probe(ROWS))) == 3)

    section("a gesture on it is refused, and says why")
    plan = json.loads(probe("JSON.stringify(app.planGesture(liveScene.elements[0], 'body', 1))"))
    check(f"nothing is written onto the call ({plan.get('message')})", plan["ok"] is False and "template" in plan["message"])

    section("the zoom reaches the whole scene")
    probe("timeline.zoomToFit()")
    zoom, fit = json.loads(probe("JSON.stringify([timeline.pxPerSecond, timeline.fitZoom])"))
    check(f"a 200 s scene fits the pane: {zoom:.2f} px/s for {fit:.2f} — below the 25 the floor used to be",
          fit < 25 and abs(zoom - fit) < 0.01)

    section("the code pane draws a long line across its whole width")
    try:
        from PIL import Image
    except ImportError:
        print("  (skipped: PIL reads the screenshot)")
    else:
        paneX, paneW, lineY, lineH, windowW = json.loads(probe(PANE))
        tell("screenshot", f"out={shot.name}")
        image = Image.open(shot.name).convert("L")
        scale = image.width / windowW

        def lit(left: float, right: float) -> int:
            box = (int((paneX + left * paneW) * scale), int(lineY * scale), int((paneX + right * paneW) * scale), int((lineY + lineH) * scale))
            pixels = image.crop(box).tobytes()
            ground = min(pixels)
            return sum(1 for value in pixels if value > ground + 40)

        near, far = lit(0.05, 0.45), lit(0.55, 0.95)
        check(f"the far half of the pane holds as much text as the near half ({far} lit pixels against {near})",
              near > 0 and far > near * 0.5)

    tell("quit")
    editor.wait(timeout=10)
finally:
    if editor.poll() is None:
        editor.kill()
    for path in (SOCKET, log.name, dock.name, shot.name):
        if os.path.exists(path):
            os.unlink(path)

summary()
