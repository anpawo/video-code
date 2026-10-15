#!/usr/bin/env python3
"""
The model and the effort picked in the Agent pane are what `claude` is started with.

A pick is felt from the next question, on a new child resumed on the same
session; it is kept in the project's dock file and is there again in the next
editor. The stand-in `claude` (test/agent_stream/claude) writes down the
arguments of every start. No window opens, and no agent runs.

Run directly: `python3 test/agent_model_test.py [picture.png]`
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

SOCKET = f"/tmp/videocode-model-{os.getpid()}.sock"
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


def flag(args: list, name: str):
    return args[args.index(name) + 1] if name in args else None


def flags(args: list) -> tuple:
    return flag(args, "--model"), flag(args, "--effort"), flag(args, "--resume")


def saved() -> dict:
    with open(dock.name) as file:
        text = file.read()
    return json.loads(text).get("agent", {}) if text.strip() else {}


def ask(question: str) -> list:
    """The starts the question caused, as (model, effort, resumed) each."""
    before = len(launches())
    probe(f"agent.ask('{question}')")
    deadline = time.time() + 20
    while time.time() < deadline:
        if json.loads(probe("JSON.stringify(agent.log[agent.log.length - 1])")).get("ended", 0) > 0:
            break
        time.sleep(0.3)
    return [flags(one) for one in launches()[before:]]


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
    section("nothing picked passes nothing")

    start()
    check("the pickers open on the defaults", probe("Agent.model + '|' + Agent.effort") == "|")
    started = ask("first")
    check(f"no --model and no --effort ({started})", started == [(None, None, None)])

    # -----------------------------------------------------------------------
    section("a pick is the next question's, on the same conversation")

    probe("agent.pick('model', 'haiku')")
    probe("agent.pick('effort', 'high')")
    check("nothing restarts while nobody asks", len(launches()) == 1)
    started = ask("second")
    check(f"a new child, on haiku at high effort, resuming the session ({started})",
          started == [("haiku", "high", "stand-in")])
    started = ask("third")
    check(f"and the next question is asked of that same child ({started})", started == [])
    kept = saved()
    check(f"the dock file keeps the pick ({kept.get('model')!r}, {kept.get('effort')!r})",
          (kept.get("model"), kept.get("effort")) == ("haiku", "high"))
    if len(sys.argv) > 1:
        probe("(function () { app.showPanel('agent') ; return 1 })()")
        time.sleep(0.5)
        tell("screenshot", f"out={sys.argv[1]}")
    probe("agent.pick('effort', '')")
    started = ask("fourth")
    check(f"back to the default effort is a new child without --effort ({started})",
          started == [("haiku", None, "stand-in")])
    stop()

    # -----------------------------------------------------------------------
    section("the next editor starts with the pick")

    start()
    check("the pick is back", probe("Agent.model + '|' + Agent.effort") == "haiku|")
    started = ask("fifth")
    check(f"and is what the first child is started with ({started})", started == [("haiku", None, "stand-in")])
    stop()

    # -----------------------------------------------------------------------
    section("a value the picker does not offer is not passed")

    with open(dock.name) as file:
        layout = json.load(file)
    layout["agent"]["model"] = "--dangerously-skip-permissions"
    layout["agent"]["effort"] = "ultra"
    with open(dock.name, "w") as file:
        json.dump(layout, file)
    start()
    check("both read back as the defaults", probe("Agent.model + '|' + Agent.effort") == "|")
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
