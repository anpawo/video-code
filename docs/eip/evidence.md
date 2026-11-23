# Evidence for the jury

One page per question the jury asks: does it work, who outside the team took
part, and is the code getting better. Every line links to something on GitHub
that carries its own date. Tracked in #457; updated as the evidence comes in.

## 1. It works: the demo

| What | Where | Date |
|---|---|---|
| The showcase scene, rendered by CI on every push and kept as a download | `eg.py` → artifact `eg-render` of each run of [Tests, lint and builds](https://github.com/anpawo/video-code/actions/workflows/ci.yaml) | every push |
| The render is checked, not just started: the step fails under 100 frames | `.github/workflows/ci.yaml`, step "The showcase scene still renders" | since 2026-08-25 |

To reproduce it on your machine (build first, see `CONTRIBUTING.md`):

```
./video-code --file eg.py --generate eg.mp4
```

Still to add: Eliot's chess video, with its script and inputs, as the
end-to-end example.

## 2. People outside the team

| Who | What | Link | Date |
|---|---|---|---|
| Cédric Dinont (former EIP mentor) | Fixed the build and run on Ubuntu | #129 | merged 2026-07-04 |
| Quentin Forand (EIP mentor) | `blink()`, `popOut()`, `riseIn()`, the easings.net easing families, `Star` | #450, #451, #452, #453, #454 | opened 2026-11-23 |

How a newcomer gets in: 24 issues labelled
[good-first-issue](https://github.com/anpawo/video-code/issues?q=label%3Agood-first-issue),
each small enough for a first pull request, and `CONTRIBUTING.md`, which says
where to start, how to build, how to check, and the licence a contribution
comes under.

## 3. Code quality, and how it is enforced

Nothing reaches `main` without a pull request, and every pull request runs
these gates ([workflow](https://github.com/anpawo/video-code/actions/workflows/ci.yaml)):

| Gate | What it refuses |
|---|---|
| Python tests, types and API coverage | a failing assertion test (98 test files), a type error, a public name no test uses |
| QML lint | an editor file that does not lint |
| C++ formatting | C++ that `clang-format` would change |
| macOS build, C++ tests and QML load | a build or C++ test that fails on macOS |
| Linux build, full suite, showcase render | the full suite failing on Linux, or the showcase rendering under 100 frames |
| Mutants | a new line of `videocode/` that no test runs, or that a test does not catch when the line is made wrong (#400) |
| Render digest | any change in what the 54 scenes ask the renderer to draw, at zero tolerance |
| Claude review | a pull request the automatic review finds a bug, a weakened test, a secret or an undescribed change in (#408, #455) |

Two more records are kept but refuse nothing: the visual regression goldens
(`test/visual/`), compared on the author's machine because a shared runner has
no GPU, and the perf history, measured there too and published from `main` as
a curve.

## Still open

- The official number of external contributions required, and whether a
  mentor's contribution counts.
- A dated screenshot of each gate passing, saved here.
