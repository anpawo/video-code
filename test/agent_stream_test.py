#!/usr/bin/env python3
"""
What the agent streams is what the pane shows.

A stand-in `claude` (test/agent_stream/claude) is put first on the PATH and
plays one recorded turn; a windowless editor asks it a question and its pane is
read back. No window opens, and no agent runs.

Run directly: `python3 test/agent_stream_test.py [picture.png]`
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

if not needsRenderer("the pane is the editor's"):
    summary()
    sys.exit(0)

SOCKET = f"/tmp/videocode-stream-{os.getpid()}.sock"
log = tempfile.NamedTemporaryFile(suffix=".log", delete=False)
dock = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
dock.close()
env = {**os.environ, "VC_SOCKET": SOCKET, "VC_DOCK_FILE": dock.name,
       "PATH": os.path.abspath("test/agent_stream") + os.pathsep + os.environ["PATH"]}


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


ANSWER = "JSON.stringify(agent.log.length > 0 ? agent.log[agent.log.length - 1] : {})"

editor = subprocess.Popen(["./video-code", "--editor", "--check-chrome", "--serve", "--file", "docs/by-example/tour.py"],
                          env=env, stdout=log, stderr=subprocess.STDOUT)
try:
    deadline = time.time() + 30
    while time.time() < deadline and not tell("state").get("ok"):
        time.sleep(0.5)

    probe("agent.ask('read the scene')")
    deadline = time.time() + 20
    answer = {}
    while time.time() < deadline:
        answer = json.loads(probe(ANSWER))
        if answer.get("ended", 0) > 0:
            break
        time.sleep(0.3)
    body = answer.get("body", [])

    # -----------------------------------------------------------------------
    section("the answer is its words")

    words = [one["text"] for one in body if one["kind"] == "text"]
    check(f"the turn ended and left one answer ({words})", answer.get("ended", 0) > 0 and len(words) == 1)
    check("no colour code and no padding reach the pane",
          len(words) == 1 and words[0] == "⟶ Fait.\n\n- `a.py` read.")

    # -----------------------------------------------------------------------
    section("its steps come before its words, one line each")

    kinds = [one["kind"] for one in body]
    check(f"reasoning, two tools, then the answer ({kinds})", kinds == ["thinking", "tool", "tool", "text"])
    if kinds == ["thinking", "tool", "tool", "text"]:
        thought, read, missing = body[0], body[1], body[2]
        check(f"two counts of one stretch of reasoning are one line, at the last count ({thought['tokens']})", thought["tokens"] == 211)
        check(f"a tool says its name and what it was pointed at ({read['name']} {read['summary']})",
              (read["name"], read["summary"]) == ("Read", "/scene/a.py"))
        check("results are matched to their call, not to the order they came back in",
              (read["state"], missing["state"]) == ("ok", "bad")
              and "from videocode import *" in read["output"] and missing["output"] == "File does not exist.")
        check(f"its arguments are kept for the unfolding ({read['input']!r})", '"limit": 40' in read["input"])

    # -----------------------------------------------------------------------
    section("a step unfolds where it is")

    turn = int(probe("agent.log.length - 1"))
    probe(f"agent.toggle({turn}, 1)")
    opened = json.loads(probe(ANSWER))["body"]
    check("the line clicked is the one that opens", [one.get("open", False) for one in opened] == [False, True, False, False])
    check("and the page stops following the bottom, so it does not move under the reader", probe("agent.follows") is False)
    if len(sys.argv) > 1:
        probe("(function () { app.showPanel('agent') ; return 1 })()")
        time.sleep(0.5)
        tell("screenshot", f"out={sys.argv[1]}")

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
