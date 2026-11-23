#!/usr/bin/env python3

"""
`--loudness <LUFS>` (#442, SPEC-loudness.md): the written file reaches a
loudness target by ffmpeg's two-pass `loudnorm`.

Every claim here is read off something real. The level comes from ffmpeg's
`ebur128` on the WRITTEN file, a pass of its own that knows nothing of the
render. The commands come from a stand-in `ffmpeg` first on PATH, which writes
down the arguments it was given and then runs the real one, so the test sees
the measurement pass and the render's filter as ffmpeg received them.

Without the flag the render's command must not move by one byte: those
arguments are compared with the ones the renderer of `main` (67732cc, built
at c7e4025, which only adds the spec) passed for the same scenes.

Run directly: `python3 test/loudness_test.py`
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, ".")
sys.path.insert(0, "test")
from helpers import check, needsRenderer, needsTool, section, summary

BINARY = os.path.abspath("video-code")
# Every process this test starts has a bound. The longest one is a 1080p
# render of six seconds; five minutes is far past it on any machine here.
TIMEOUT = 300

WIDTH = 160
HEIGHT = 90


def run(args: list[str], env: dict[str, str] | None = None, cwd: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, timeout=TIMEOUT, env=env, cwd=cwd)


class Ffmpeg:
    """A stand-in `ffmpeg` that records each command, then runs the real one."""

    def __init__(self, folder: str) -> None:
        real = shutil.which("ffmpeg")
        assert real, "needsTool checked ffmpeg first"
        bindir = os.path.join(folder, "bin")
        os.makedirs(bindir)
        self.log = os.path.join(folder, "ffmpeg-calls.jsonl")
        stand_in = os.path.join(bindir, "ffmpeg")
        with open(stand_in, "w") as out:
            out.write(
                f"#!{sys.executable}\n"
                "import json, os, sys\n"
                f"with open({self.log!r}, 'a') as log:\n"
                "    log.write(json.dumps(sys.argv[1:]) + '\\n')\n"
                f"os.execv({real!r}, [{real!r}, *sys.argv[1:]])\n"
            )
        os.chmod(stand_in, 0o755)
        self.env = dict(os.environ, PATH=bindir + os.pathsep + os.environ.get("PATH", ""))

    def calls(self) -> list[list[str]]:
        """The commands since the last call, oldest first."""
        if not os.path.exists(self.log):
            return []
        with open(self.log) as log:
            said = [json.loads(line) for line in log if line.strip()]
        os.remove(self.log)
        return said


def loudness(path: str) -> float | None:
    """Integrated loudness of a file, by ffmpeg's ebur128 — the summary's `I:`."""
    said = run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"])
    found = re.findall(r"I:\s+(-?[\d.]+|-inf) LUFS", said.stderr)
    return float(found[-1]) if found else None


def loudnormInput(path: str, key: str = "input_i") -> float | None:
    """What loudnorm's own first pass reads in a file — its `input_i` by default."""
    said = run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "loudnorm=I=-14:TP=-1:LRA=11:print_format=json", "-f", "null", "-"])
    found = re.findall(rf'"{key}" : "(-?[\d.]+|-inf)"', said.stderr)
    return float(found[-1]) if found else None


def sampleRate(path: str) -> int | None:
    said = run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=sample_rate", "-of", "csv=p=0", path])
    return int(said.stdout) if said.stdout.strip().isdigit() else None


def option(argv: list[str], name: str) -> str:
    """The value after `name` in one command, or "" when it has none."""
    return argv[argv.index(name) + 1] if name in argv else ""


def withoutLoudnorm(graph: str) -> str:
    """The mix a filter describes, with its final loudnorm stage taken off."""
    return re.sub(r";\[[^\]]+\]loudnorm=[^;]*$", "", graph)


# What the renderer of `main` passed to ffmpeg for each scene, recorded by this
# test's stand-in from a run of that binary (c7e4025) on 2026-11-23, with the
# test's temporary folder written as {DIR}. Changing a value here means a
# render without --loudness changed.
UNCHANGED: dict[str, list[str]] = {
    "one sound": [
        "-y", "-f", "rawvideo", "-pixel_format", "bgra", "-video_size", "160x90", "-framerate", "30", "-i", "-",
        "-i", "{DIR}/steps.wav",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-crf", "23",
        "-filter_complex", "[1:a]volume=0.5,adelay=500|500[a0];[a0]atrim=start=0:end=3,asetpts=PTS-STARTPTS[arange]",
        "-map", "0:v", "-map", "[arange]", "-c:a", "aac", "-movflags", "+faststart", "-loglevel", "warning", "{DIR}/one-sound.mp4",
    ],
    "two sounds": [
        "-y", "-f", "rawvideo", "-pixel_format", "bgra", "-video_size", "160x90", "-framerate", "30", "-i", "-",
        "-i", "{DIR}/steps.wav", "-ss", "0.5", "-to", "2.5", "-i", "{DIR}/steps.wav",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-crf", "23",
        "-filter_complex",
        "[1:a]volume=1,adelay=0|0[a0];[2:a]volume=1,adelay=1000|1000[a1];"
        "[a0][a1]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[aout];"
        "[aout]atrim=start=0:end=4,asetpts=PTS-STARTPTS[arange]",
        "-map", "0:v", "-map", "[arange]", "-c:a", "aac", "-movflags", "+faststart", "-loglevel", "warning", "{DIR}/two-sounds.mp4",
    ],
    "a window": [
        "-y", "-f", "rawvideo", "-pixel_format", "bgra", "-video_size", "160x90", "-framerate", "30", "-i", "-",
        "-i", "{DIR}/steps.wav",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-crf", "23",
        "-filter_complex", "[1:a]volume=1,adelay=0|0[a0];[a0]atrim=start=1:end=2.5,asetpts=PTS-STARTPTS[arange]",
        "-map", "0:v", "-map", "[arange]", "-c:a", "aac", "-movflags", "+faststart", "-loglevel", "warning", "{DIR}/a-window.mp4",
    ],
    "no sound": [
        "-y", "-f", "rawvideo", "-pixel_format", "bgra", "-video_size", "160x90", "-framerate", "30", "-i", "-",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-crf", "23",
        "-an", "-movflags", "+faststart", "-loglevel", "warning", "{DIR}/no-sound.mp4",
    ],
}


def scenes(folder: str, wav: str) -> dict[str, tuple[str, list[str]]]:
    """name → (scene source, extra flags), the scenes the reference was run on."""
    return {
        "one sound": (f"from videocode import *\nSound({wav!r}, start=0.5, volume=0.5)\nwait(3)\n", []),
        "two sounds": (
            f"from videocode import *\nSound({wav!r})\nSound({wav!r}, start=1, trimStart=0.5, trimEnd=2.5)\nwait(4)\n",
            [],
        ),
        "a window": (f"from videocode import *\nSound({wav!r})\nwait(6)\n", ["--from", "1", "--to", "2.5"]),
        "no sound": ("from videocode import *\nwait(1)\n", []),
    }


if needsRenderer("--loudness is a flag of the renderer") and needsTool("ffmpeg", "the measurement and the check are ffmpeg"):
    folder = tempfile.mkdtemp(prefix="vc-loudness-")
    ffmpeg = Ffmpeg(folder)

    # A tone at two levels, 3 s quiet then 3 s 6 dB louder, made here rather
    # than committed. Two levels give it a loudness RANGE above 0, so the
    # measured range passes through as measured; the steady tone further
    # down measures 0.00, the case the render raises to 0.01.
    # Not 12 dB: the quiet half then sits 0.7 dB above the -10 LU relative
    # gate, and loudnorm (-40.4 LUFS) and ebur128 (-42.9) disagreed on it by
    # 2.5 LU — a test of the two meters' gating, not of the render.
    wav = os.path.join(folder, "steps.wav")
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
        "-i", "sine=frequency=440:duration=6:sample_rate=44100",
        "-af", "volume='if(lt(t,3),0.06,0.12)':eval=frame", "-ac", "2", wav,
    ])
    level = loudness(wav)
    # The two meters do not agree on a tone that changes level: loudnorm read
    # this one 0.7 LU louder than ebur128 did (-41.5 against -42.2, measured
    # 2026-11-23), and a steady tone or noise they read alike. The render
    # aims with loudnorm's number, so the written file lands that far below
    # the target by ebur128 — inside the ±1 LU the check allows.
    aimed = loudnormInput(wav)

    def write(name: str, source: str) -> str:
        path = os.path.join(folder, name)
        with open(path, "w") as out:
            out.write(source)
        return path

    def render(scene: str, output: str, *flags: str, size: bool = True) -> subprocess.CompletedProcess[str]:
        args = [BINARY, "--file", scene, "--generate", output, *flags]
        if size:
            args += ["--width", str(WIDTH), "--height", str(HEIGHT)]
        return run(args, env=ffmpeg.env)

    def portable(argv: list[str]) -> list[str]:
        return [a.replace(folder, "{DIR}") for a in argv]

    section("The test sound")
    check(f"the tone made with lavfi measures well below both targets ({level} LUFS)", level is not None and level < -30)

    # ── refused before the scene runs ───────────────────────────────────────
    section("Refusals — before the scene runs")
    marker = os.path.join(folder, "the-scene-ran")
    guarded = write("guarded.py", f"from videocode import *\nopen({marker!r}, 'w').close()\nSound({wav!r})\nwait(1)\n")
    out = os.path.join(folder, "refused.mp4")

    for value in ("-80", "-4", "loud"):
        said = render(guarded, out, "--loudness", value)
        check(f"--loudness {value} exits 1", said.returncode == 1)
        check(
            f"--loudness {value}: the message names the value and the range",
            f'video-code: --loudness takes a target from -70 to -5 LUFS (-14 is Spotify\'s), and "{value}" is not one.\n' in said.stderr,
        )
    # --lint is a run that writes no file, and it runs the scene: a refusal
    # that came too late would leave the marker behind.
    said = run([BINARY, "--file", guarded, "--loudness", "-14", "--lint"], env=ffmpeg.env)
    check("--loudness without --generate exits 1", said.returncode == 1)
    check(
        "--loudness without --generate: refused as --for is",
        said.stderr == "video-code: --loudness sets the level of the file it writes, so it needs --generate.\n",
    )
    check("no refusal ran the scene", not os.path.exists(marker))
    check("no refusal wrote a file", not os.path.exists(out))
    ffmpeg.calls()

    # ── without the flag: the command of main, byte for byte ────────────────
    section("Without --loudness — the ffmpeg command is main's")
    for name, (source, flags) in scenes(folder, wav).items():
        scene = write(name.replace(" ", "-") + ".py", source)
        said = render(scene, os.path.join(folder, name.replace(" ", "-") + ".mp4"), *flags)
        calls = [portable(c) for c in ffmpeg.calls()]
        check(f"{name}: renders", said.returncode == 0)
        check(f"{name}: one ffmpeg run, no measurement", len(calls) == 1)
        same = len(calls) == 1 and calls[0] == UNCHANGED.get(name)
        check(f"{name}: the arguments are main's", same)
        if not same:
            print(f"    recorded: {json.dumps(calls[-1] if calls else None)}")

    # ── the target, measured on the written file ────────────────────────────
    steps = write("steps.py", f"from videocode import *\nSound({wav!r})\nwait(6)\n")
    for target in (-14, -16):
        section(f"--loudness {target} — the written file")
        output = os.path.join(folder, f"at{target}.mp4")
        said = render(steps, output, "--loudness", str(target))
        calls = ffmpeg.calls()
        check("renders", said.returncode == 0)
        measured = loudness(output)
        check(f"ebur128 measures the file at {target} ±1 LU ({measured} LUFS)", measured is not None and abs(measured - target) <= 1.0)
        check(f"the audio is 48000 Hz ({sampleRate(output)})", sampleRate(output) == 48000)

        line = re.search(r"^Loudness: (-?[\d.]+) LUFS -> (-?[\d.]+) LUFS target \((\w+)\)$", said.stdout, re.M)
        check(f"one report line: {line.group(0) if line else said.stdout[-300:]!r}", line is not None and said.stdout.count("Loudness:") == 1)
        check("it names the target", line is not None and float(line.group(2)) == target)
        check(f"it names the mix's level as loudnorm measured it ({aimed})", line is not None and aimed is not None and abs(float(line.group(1)) - aimed) <= 0.05)
        check("the type ffmpeg reported: linear, for a tone with a range", line is not None and line.group(3) == "linear")

        check("two ffmpeg runs: the measurement, then the render", len(calls) == 2)
        if len(calls) == 2:
            measure, encode = calls
            check("the measurement reads no picture", "rawvideo" not in measure and "-map" in measure and "0:v" not in measure)
            check("the measurement writes nothing", measure[-3:] == ["-f", "null", "-"])
            check(
                "the measurement ends in loudnorm at the target, -1 dBTP, as JSON",
                f"loudnorm=I={target}:TP=-1:LRA=11:print_format=json" in option(measure, "-filter_complex"),
            )
            applied = option(encode, "-filter_complex")
            check(
                "the render applies the measured values, linear, -1 dBTP",
                re.search(rf"loudnorm=I={target}:TP=-1:LRA=\d+(\.\d+)?:measured_I=-?[\d.]+:measured_LRA=[\d.]+:measured_TP=-?[\d.]+:measured_thresh=-?[\d.]+:offset=-?[\d.]+:linear=true", applied)
                is not None,
            )
            check("then resamples to 48 kHz", re.search(r"loudnorm=[^;\[]*,aresample=48000\[", applied) is not None)
            # The render's picture is input 0, so each sound is one index higher there.
            shifted = re.sub(r"\[(\d+):a\]", lambda m: f"[{int(m.group(1)) - 1}:a]", withoutLoudnorm(applied))
            check("the measurement mixes the same graph the render does", withoutLoudnorm(option(measure, "-filter_complex")) == shifted)

    section("--loudness with --from/--to — the window is what is measured")
    output = os.path.join(folder, "window.mp4")
    said = render(steps, output, "--loudness", "-14", "--from", "2", "--to", "6")
    calls = ffmpeg.calls()
    check("renders", said.returncode == 0)
    measured = loudness(output)
    check(f"the 4 s file measures -14 ±1 LU ({measured} LUFS)", measured is not None and abs(measured + 14) <= 1.0)
    check("the measurement cuts the window out of the mix", len(calls) == 2 and "atrim=start=2:end=6" in option(calls[0], "-filter_complex"))

    section("--loudness with --data — each file is measured on its own")
    gains = write("gains.csv", "name,gain\nloud,1\nquiet,0.25\n")
    scaled = write("scaled.py", f"from videocode import *\nSound({wav!r}, volume=param('gain', 1.0))\nwait(6)\n")
    said = render(scaled, os.path.join(folder, "row-{name}.mp4"), "--loudness", "-14", "--data", gains)
    calls = ffmpeg.calls()
    check("renders both rows", said.returncode == 0)
    levels = [float(x) for x in re.findall(r"^Loudness: (-?[\d.]+) LUFS -> -14\.0 LUFS target", said.stdout, re.M)]
    check(f"two measurements, one per row ({levels})", len([c for c in calls if c[-3:] == ["-f", "null", "-"]]) == 2 and len(levels) == 2)
    check("the quiet row measured 12 dB lower than the loud one", len(levels) == 2 and abs((levels[0] - levels[1]) - 12.0) <= 0.5)
    for row in ("loud", "quiet"):
        measured = loudness(os.path.join(folder, f"row-{row}.mp4"))
        check(f"row {row} is written at -14 ±1 LU ({measured} LUFS)", measured is not None and abs(measured + 14) <= 1.0)

    section("--loudness with --for — each shape is measured on its own")
    said = render(steps, os.path.join(folder, "shape.mp4"), "--loudness", "-16", "--for", "youtube,square", "--to", "4", size=False)
    calls = ffmpeg.calls()
    check("renders both shapes", said.returncode == 0)
    check("two measurements, one per shape", len([c for c in calls if c[-3:] == ["-f", "null", "-"]]) == 2 and said.stdout.count("Loudness:") == 2)
    for shape in ("youtube", "square"):
        written = os.path.join(folder, f"shape-{shape}.mp4")
        measured = loudness(written) if os.path.exists(written) else None
        check(f"{shape} is written at -16 ±1 LU ({measured} LUFS)", measured is not None and abs(measured + 16) <= 1.0)

    # A steady tone measures LRA 0.00, and so does a few seconds of real music
    # (the controller measured test/tour_music.wav, 8 s, at 0.00). loudnorm
    # takes measured_LRA=0.00 as "dynamic" even for a pure gain cut.
    section("--loudness on a clip with no loudness range — still linear")
    steady = os.path.join(folder, "steady.wav")
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
        "-i", "sine=frequency=440:duration=6:sample_rate=44100", "-ac", "2", steady,
    ])
    flat = write("steady.py", f"from videocode import *\nSound({steady!r})\nwait(6)\n")
    output = os.path.join(folder, "steady.mp4")
    said = render(flat, output, "--loudness", "-23")
    calls = ffmpeg.calls()
    check("renders", said.returncode == 0)
    range_ = loudnormInput(steady, "input_lra")
    check(f"loudnorm reads no range in the tone (input_lra {range_})", range_ == 0.0)
    check(f"the tone is above the target, so this is a gain cut ({loudnormInput(steady)} LUFS)", (loudnormInput(steady) or -99.0) > -23.0)
    check("two ffmpeg runs: the measurement, then the render", len(calls) == 2)
    check("the render passes measured_LRA=0.01, not 0.00", len(calls) == 2 and ":measured_LRA=0.01:" in option(calls[1], "-filter_complex"))
    line = re.search(r"^Loudness: (-?[\d.]+) LUFS -> -23\.0 LUFS target \((\w+)\)$", said.stdout, re.M)
    check(f"the report says linear ({line.group(0) if line else said.stdout[-200:]!r})", line is not None and line.group(2) == "linear")
    measured = loudness(output)
    check(f"ebur128 measures the file at -23 ±1 LU ({measured} LUFS)", measured is not None and abs(measured + 23) <= 1.0)

    # ── nothing to normalise: rendered as before, and said ──────────────────
    section("Nothing to normalise — rendered as before, with the reason")
    silent = write("silent.py", f"from videocode import *\nSound({wav!r}, volume=0)\nwait(3)\n")
    quiet = write("nosound.py", "from videocode import *\nwait(1)\n")
    cases = [
        ("a scene with no sound", quiet, "out.mp4", "Loudness: not normalised — the scene has no sound.\n"),
        ("a GIF", steps, "out.gif", "Loudness: not normalised — a GIF carries no sound.\n"),
        ("an image", steps, "out.png", "Loudness: not normalised — an image carries no sound.\n"),
        ("a silent mix", silent, "out.mp4", None),
    ]
    for name, scene, file, reason in cases:
        output = os.path.join(folder, "plain-" + file)
        render(scene, output)
        before = [portable(c) for c in ffmpeg.calls()]
        os.remove(output)
        said = render(scene, output, "--loudness", "-14")
        calls = [portable(c) for c in ffmpeg.calls()]
        check(f"{name}: exits 0 and writes the file", said.returncode == 0 and os.path.exists(output))
        if reason is None:
            found = re.search(r"^Loudness: not normalised — the mix measures (\S+) LUFS, which loudnorm takes for silence \(-70 or lower\)\.$", said.stdout, re.M)
            check(f"{name}: one line says why ({said.stdout.strip().splitlines()[0] if said.stdout.strip() else ''!r})", found is not None and said.stdout.count("Loudness:") == 1)
            check(f"{name}: the render is the one without the flag", calls[1:] == before)
        else:
            check(f"{name}: one line says why", reason in said.stdout and said.stdout.count("Loudness:") == 1)
            check(f"{name}: no measurement, and the render is the one without the flag", calls == before)

    shutil.rmtree(folder, ignore_errors=True)

summary()
