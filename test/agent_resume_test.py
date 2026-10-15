#!/usr/bin/env python3
"""
The Agent pane's conversation survives closing the editor.

The log and the session id are kept in the project's dock file; the next editor
on that file shows the log again and starts `claude` with `--resume <id>`. A
session that is gone is asked again in a fresh one, said in the pane; New
conversation clears both. The stand-in `claude` (test/agent_stream/claude)
writes down the arguments of every start. No window opens, and no agent runs.

Run directly: `python3 test/agent_resume_test.py`
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

SOCKET = f"/tmp/videocode-resume-{os.getpid()}.sock"
log = tempfile.NamedTemporaryFile(suffix=".log", delete=False)
dock = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
told = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
for one in (log, dock, told):
    one.close()
env = {**os.environ, "VC_SOCKET": SOCKET, "VC_DOCK_FILE": dock.name, "VC_STAND_IN_ARGS": told.name,
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


def launches() -> list:
    with open(told.name) as lines:
        return [json.loads(line) for line in lines if line.strip()]


def resumed(args: list):
    return args[args.index("--resume") + 1] if "--resume" in args else None


def saved() -> dict:
    with open(dock.name) as file:
        text = file.read()
    return json.loads(text).get("agent", {}) if text.strip() else {}


def ask(question: str) -> dict:
    probe(f"agent.ask('{question}')")
    deadline = time.time() + 20
    answer = {}
    while time.time() < deadline:
        answer = json.loads(probe("JSON.stringify(agent.log.length > 0 ? agent.log[agent.log.length - 1] : {})"))
        if answer.get("ended", 0) > 0:
            break
        time.sleep(0.3)
    return answer


editor = None


def start():
    global editor
    editor = subprocess.Popen(["./video-code", "--editor", "--check-chrome", "--serve", "--file", "docs/by-example/tour.py"],
                              env=env, stdout=open(log.name, "w"), stderr=subprocess.STDOUT)
    deadline = time.time() + 30
    while time.time() < deadline and not tell("state").get("ok"):
        time.sleep(0.5)


def stop():
    tell("quit")
    editor.wait(timeout=10)


try:
    # -----------------------------------------------------------------------
    section("a conversation is written to the dock file")

    start()
    first = ask("first")
    check("the first question is answered", first.get("ended", 0) > 0)
    check(f"by a child that resumed nothing ({[resumed(one) for one in launches()]})", len(launches()) == 1 and resumed(launches()[0]) is None)
    kept = saved()
    check(f"the dock file holds its session ({kept.get('session')!r})", kept.get("session") == "stand-in")
    check(f"and its question and answer ({len(kept.get('log', []))} entries)",
          [one["who"] for one in kept.get("log", [])] == ["me", "agent"])
    stop()

    # -----------------------------------------------------------------------
    section("the next editor shows it, and continues it")

    start()
    shown = json.loads(probe("JSON.stringify(agent.log.map((e) => e.who + ':' + e.body.length))"))
    check(f"the page is back as it was ({shown})", len(shown) == 2 and shown[0] == "me:1" and shown[1].startswith("agent:"))
    check("and the session with it", probe("Agent.sessionId") == "stand-in")
    second = ask("second")
    last = launches()[-1]
    check(f"the next question starts `claude --resume stand-in` ({resumed(last)})", resumed(last) == "stand-in")
    check("and is answered under the first", second.get("ended", 0) > 0 and len(json.loads(probe("JSON.stringify(agent.log)"))) == 4)
    stop()

    # -----------------------------------------------------------------------
    section("a session that is gone starts a new one, and says so")

    with open(dock.name) as file:
        layout = json.load(file)
    layout["agent"]["session"] = "gone-0000"
    # An answer that was still being written when the window closed.
    layout["agent"]["log"].append({"who": "me", "body": [{"kind": "text", "text": "third"}]})
    layout["agent"]["log"].append({"who": "agent", "body": [], "started": 1000, "ended": 0})
    with open(dock.name, "w") as file:
        json.dump(layout, file)

    start()
    cut = json.loads(probe("JSON.stringify(agent.log[agent.log.length - 1])"))
    check(f"an unfinished answer is closed on the way in, saying so ({cut.get('body')})",
          cut.get("ended", 0) > 0 and [one["kind"] for one in cut.get("body", [])] == ["note"])
    before = len(launches())
    answer = ask("fourth")
    tried = launches()[before:]
    check(f"the lost session was tried, then a fresh one ({[resumed(one) for one in tried]})",
          [resumed(one) for one in tried] == ["gone-0000", None])
    notes = [one["text"] for one in answer.get("body", []) if one["kind"] == "note"]
    check(f"the pane says the agent no longer remembers ({notes})",
          len(notes) == 1 and "could not be picked up" in notes[0] and "No conversation found" in notes[0])
    words = [one["text"] for one in answer.get("body", []) if one["kind"] == "text"]
    check(f"and the question is still answered ({words})", answer.get("ended", 0) > 0 and len(words) == 1)
    check("the new session is the one kept", probe("Agent.sessionId") == "stand-in" and saved().get("session") == "stand-in")

    # -----------------------------------------------------------------------
    section("New conversation clears the page and the session")

    probe("agent.fresh()")
    check("the page is empty", probe("agent.log.length") == 0)
    check("the agent knows no session", probe("Agent.sessionId") == "")
    kept = saved()
    check(f"and the dock file neither ({kept})", kept.get("session") == "" and kept.get("log") == [])
    before = len(launches())
    ask("fifth")
    check("the next question resumes nothing", [resumed(one) for one in launches()[before:]] == [None])
    stop()
finally:
    if editor is not None and editor.poll() is None:
        editor.kill()
    for path in (log.name, dock.name, told.name):
        try:
            os.unlink(path)
        except OSError:
            pass

summary()
