# Plan: loudness and charts (2026-11-23)

Two modules with no dependency between them and no shared file. The two
`git-workflow` agents run in parallel, each in its own worktree.

| Module id | Spec | Depends on |
|---|---|---|
| `loudness` | [SPEC-loudness.md](../SPEC-loudness.md) | — |
| `charts` | [SPEC-charts.md](../SPEC-charts.md) | — |

## Wave 1 (parallel)

- [ ] **T1 — `--loudness <LUFS>`: two-pass loudnorm on the render** — #442
  - Acceptance: the criteria of #442.
  - Verify: `python3 test/loudness_test.py`, `./test/run_tests.sh`, pyright, coverage, digest unchanged, `./build/video-code-tests`.
  - Files: `src/Main.cpp`, `src/compiler/AudioMix.cpp`, `include/compiler/AudioMix.hpp`, `src/compiler/Compiler.cpp`, maybe `src/core/ScreenSize.cpp` and `include/core/ScreenSize.hpp`, `test/loudness_test.py`, `docs/ffmpeg.md`.
- [ ] **T2 — `LineChart(data)` and `PieChart(data)`** — #443
  - Acceptance: the criteria of #443.
  - Verify: `python3 test/linechart_test.py`, `python3 test/piechart_test.py`, `./test/run_tests.sh`, pyright, coverage, repetition, digest unchanged, a `--sheet` render looked at.
  - Files: `videocode/template/input/LineChart.py`, `videocode/template/input/PieChart.py`, maybe `videocode/template/input/BarChart.py`, `test/linechart_test.py`, `test/piechart_test.py`, `docs/FEATURES.md`.

Shared files: none. T1 touches only `src/`, `include/`, `docs/ffmpeg.md` and its own test. T2 touches only `videocode/template/input/`, its own tests and `docs/FEATURES.md`.

## After wave 1 (controller)

- [ ] `docs/FEATURES.md`: the "Not included: loudness normalisation" paragraph says what `--loudness` does.
- [ ] `board:` commit: `docs/board.html` and `docs/FEATURES_TODO.md`, one row each.
