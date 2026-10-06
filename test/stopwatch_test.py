#!/usr/bin/env python3
"""
A value typed at the playhead writes the animation that reaches it there.

The Inspector's "At the playhead" rows are the stopwatch: typing a value writes
`box.moveTo(y=1, at=3)`, a line that lands on the playhead's frame, placed so
that nothing after it moves — and refused, in words, where a line is already
setting that value. Asked of a windowless editor through the Inspector's own
signal. No window opens.

Run directly: `python3 test/stopwatch_test.py`
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

if not needsRenderer("the stopwatch is the editor's"):
    summary()
    sys.exit(0)

SCENE = "test/stopwatch/scene.py"
SOCKET = f"/tmp/videocode-stopwatch-{os.getpid()}.sock"
log = tempfile.NamedTemporaryFile(suffix=".log", delete=False)
dock = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
dock.close()
env = {**os.environ, "VC_SOCKET": SOCKET, "VC_DOCK_FILE": dock.name}

# The buffer's lines, the box's effects as [call, line, first frame, last frame, channels],
# the film's length and where each wait starts.
STATE = ("JSON.stringify({ lines: source.text.split(String.fromCharCode(10)),"
         " fx: liveScene.elements[0].effects.map((f) => [f.n, f.line, Math.round(f.l * 30), Math.round((f.l + f.d) * 30) - 1, f.kinds]),"
         " frames: execFrames, waits: liveScene.waits.map((g) => [g.line, Math.round(g.at * 30)]) })")
# What the Inspector's notice says, or "" when it says nothing.
SAID = ("(function find(item) { if (item.act !== undefined && typeof item.show === 'function') return item.visible ? String(item.children[0].text) : '' ;"
        " for (const c of item.children) { const r = find(c) ; if (r !== null) return r } return null })(inspector)")


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


def typed(key: str, value: str, frame: int, element: int = 0) -> tuple[dict, str]:
    """Type `value` in the row `key` with the playhead on `frame`; the state after, and what was said."""
    probe(f"(function () {{ inspector.keyed(liveScene.elements[{element}], '{key}', '{value}', {frame}) ; return 1 }})()")
    return json.loads(probe(STATE)), probe(SAID)


def back() -> None:
    probe("(function () { source.undo() ; app.executeScene() ; return 1 })()")


editor = subprocess.Popen(["./video-code", "--editor", "--check-chrome", "--serve", "--file", SCENE],
                          env=env, stdout=log, stderr=subprocess.STDOUT)
try:
    deadline = time.time() + 30
    while time.time() < deadline and not tell("state").get("ok"):
        time.sleep(0.5)
    base = json.loads(probe(STATE))

    # -----------------------------------------------------------------------
    section("the line lands on the playhead's frame, and nothing after it moves")

    now, said = typed("Position:y", "1", 101)
    check(f"in the middle of a wait, it goes under that wait ({now['lines'][6]!r})", now["lines"][6] == "box.moveTo(y=1, at=3)")
    check("twelve frames ending on the playhead's", ["moveTo", 7, 90, 101, ["Position:y"]] in now["fx"])
    check("the film keeps its length and every wait its start",
          now["frames"] == base["frames"] and [at for _, at in now["waits"]] == [at for _, at in base["waits"]])
    check(f"and the Inspector says what was written ({said})", "position y reaches 1 at 3.37s" in said and said.endswith("added"))
    back()

    now, _ = typed("Position:y", "1", 59)
    check(f"while x is moving, y is free: under the line that moves x ({now['lines'][5]!r})",
          now["lines"][5] == "box.moveTo(y=1, at=1.6)" and ["moveTo", 5, 42, 71, ["Position:x"]] in now["fx"])
    check("and the wait under it starts when it did", now["waits"] == [[4, 12], [7, 72], [9, 144]])
    back()

    now, _ = typed("Opacity", "128", 100)
    check(f"opacity has its verb ({now['lines'][6]!r})", now["lines"][6] == "box.fadeTo(128, at=2.97)" and ["fadeTo", 7, 89, 100, ["Opacity"]] in now["fx"])
    back()

    # -----------------------------------------------------------------------
    section("a value a line is already setting is that line's to say")

    now, said = typed("Position:x", "0", 60)
    check(f"in the middle of the move: refused, in words ({said})",
          now["lines"] == base["lines"] and "moveTo() on line 5 is setting position x at 2.00s" in said)

    now, said = typed("Position:x", "0", 75)
    check(f"right after it: the animation takes the frames that are free ({now['lines'][6]!r})",
          now["lines"][6] == "box.moveTo(x=0, at=2.4, duration=0.14)" and ["moveTo", 7, 72, 75, ["Position:x"]] in now["fx"])
    check("and still pushes nothing", now["frames"] == base["frames"])
    back()

    # -----------------------------------------------------------------------
    section("what cannot be written is said, and nothing is written")

    now, said = typed("Rotation", "30", 1)
    check(f"on its first frame a value is where it starts ({said})", now["lines"] == base["lines"] and "type it in Transform" in said)

    now, said = typed("Position:x", "0", 100, element=1)
    check(f"an element with no name cannot be told anything ({said})", now["lines"] == base["lines"] and "give it a name first" in said)

    with open(SCENE) as onDisk:
        check("the file on disk was never touched", onDisk.read().split("\n")[:8] == base["lines"][:8])

    tell("quit")
    editor.wait(timeout=10)
finally:
    if editor.poll() is None:
        editor.kill()
    for path in (log.name, dock.name):
        try:
            os.unlink(path)
        except OSError:
            pass

summary()
