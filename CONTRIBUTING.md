# Contributing

This page is the short version: how to build a change, check it, and send it.
The long forms are linked, not copied, so that there is one place to keep right.

## Start from an issue

Every change starts as a GitHub issue, and every commit names it. The body is
a `## What` followed by a few bullets: what is wrong or missing, what "done"
looks like, and how a test will show it. [#389](https://github.com/anpawo/Video-Code/issues/389)
is a good model. Labels say the area: `python-API`, `editor`, `timeline`,
`vulkan-engine`, `ai-agent`, `doc`, `ci-cd`, `bug`, `feature`…

Work on a branch named after it — `feature/389-agent-resume`, `ci/381-…` — and
merge through a pull request that says `Closes #N`. Pull requests are merged
with a merge commit.

## Build

[docs/user/user.md](docs/user/user.md#building-from-source) is the build from
source; [docs/SETUP_LINUX.md](docs/SETUP_LINUX.md) has the Linux packages.

Three things that cost people an afternoon:

- **Which binary.** On Linux `cmake --build build --target video-code` writes
  `build/video-code`. The tests, `make check` and `make test` run
  `./video-code` at the root, which is a *copy*, and on Linux `make` does not
  refresh it yet ([#402](https://github.com/anpawo/Video-Code/issues/402)). An
  old copy there is a test of old code. Copy it yourself, as CI does:
  `cp build/video-code video-code`, or run `build/video-code` directly.
- **What needs a rebuild.** Only C++ (`src/`, `include/`, CMake). The editor
  watches `qml/` and reloads its chrome when a file changes, and the Python
  library is imported from the working directory — run from the repository
  root and a change to `videocode/` is live on the next run.
- **Python packages.** `python3 -m pip install pybind11 -r requirements.txt`.
  If they live in a virtualenv, activate it before running the binary or the
  tests: the embedded interpreter adds an *activated* venv's `site-packages`
  (`src/Main.cpp`), and a venv it was never told about is
  `ModuleNotFoundError`. The venv must be the same Python version as the one
  the binary was built against.

## Check

Nothing blocks a push. What guards the repo is in three places, split by what
each can actually decide — [docs/WORKFLOWS.md](docs/WORKFLOWS.md) has the
table and the reasons:

- **GitHub Actions**, on every push and pull request: the Python suites,
  pyright, that new public API arrived documented and tested, repetition,
  qmllint, clang-format, the Linux and macOS builds, the C++ unit tests, the
  QML chrome, and that `eg.py` still renders. A red run means the push already
  landed — fix it in the next one.
- **`make check`**, when you ask: visual regression, the preview against the
  headless renderer, C++ unit tests, the render digest, and the performance
  guard. It needs this machine's GPU, which is why CI cannot run it, and it
  *records* the timings into `test/perf/history.jsonl` — commit that line with
  the change it measured.
- **The pre-commit hook**, once armed with `make arm` (~15 s): what the
  repository forgot to commit, coverage, types, formatting, the QML chrome,
  repetition and the render digest. It is the only one that refuses.

The pieces, to run one at a time:

| | |
|---|---|
| Python suites | `./test/run_tests.sh` runs every `test/*_test.py`; each prints `All checks passed.` and exits 0, or `N FAILURE(S):` and exits 1. A missing tool (ffmpeg, LaTeX, the binary) skips its section unless `VC_REQUIRE_TOOLS=1`. |
| Types | `python3 -m pyright` |
| New public API | `python3 test/coverage_check.py` — a new public name needs a docstring, a mention in `docs/*.md` and one in `test/`. A deliberate exception is fine: say why in the commit message. |
| Repeated code | `python3 test/repetition_check.py`; `--update` accepts a deliberate clone, `test/twins.json` declares two files alike on purpose. |
| Render digest | `python3 test/perf/digest.py` — what the scenes ask the renderer to do, held to zero tolerance; `--update` when that is what the change meant. |
| C++ | `cmake --build build --target video-code-tests && ./build/video-code-tests`, and `clang-format -i` on what you touched. |
| Visual | `make test`; `make test-golden` rewrites the goldens in `test/visual/golden/`. Look at the render first: a golden can be recording a bug. Tolerated failures are listed, with a reason, in `test/visual/known_failures.txt`. |

**The editor, without a window.** A test or an agent drives the real editor
through a local socket:

```bash
./build/video-code --editor --check-chrome --serve --file docs/by-example/tour.py &
./build/video-code tell state
./build/video-code tell seek at=2.5
./build/video-code tell quit
```

On a machine with no display, set `QT_QPA_PLATFORM=offscreen`.
`test/editor_control_test.py` shows every verb.

## Commit

The history is the changelog, so a subject says what is true after the commit,
in words, behind the area it touches and with the issue in parentheses:

```
agent: the conversation survives closing the editor (#389)
library: fadeTo(o), the opacity verb that was missing beside moveTo and rotateTo (#182)
timeline: zoom out to a quarter of the whole scene (#397)
```

The areas are the ones `git log --oneline` shows — `library`, `editor`,
`inspector`, `timeline`, `preview`, `templates`, `agent`, `errors`, `text`,
`docs`, `test`, `ci`… The body says why, and what was measured. Small commits,
each one working.

**The board.** [docs/board.html](docs/board.html) is the one page that says
what is happening; [docs/FEATURES_TODO.md](docs/FEATURES_TODO.md) is its long
form — measurements, designs that were rejected and why. A feature gets its own
`board:` commit that updates both, numbered by its row:

```
board: the agent's conversation survives the window, waiting for his mouse (92, #389); 94 test files
```

A row leaves the board when its issue is done. Keep the two files agreeing.

**The README** is generated: edit the partials in `docs/readme/`, then
`docs/readme/generate.sh` (it also re-renders the example gif). An edit to
`README.md` alone is lost on the next run.

## Licence

Video-Code is under the [PolyForm Noncommercial License 1.0.0](LICENSE), with
three permissions added on top of it by Marius Rousset, whose copyright
notice it carries.
`LICENSE` has no terms for contributions — there is no contributor agreement —
so a contribution comes in under the project's licence.

Two consequences:

- A dependency has to live with a noncommercial licence. `python-chess`
  (GPL-3.0) left the repository for that reason ([docs/FEATURES_TODO.md](docs/FEATURES_TODO.md),
  section G).
- `LICENSE` reads the credit address and the commercial price from the
  README's License section, so `docs/readme/09_license.md` is part of what
  the licence says, not prose to tidy.
