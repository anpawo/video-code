# Spec: `--loudness` — the render reaches a loudness target

Module id: `loudness`. Issue: #442. Written 2026-11-23.

## Objective

A render is delivered at whatever level its sounds were mixed at. The platforms
turn a loud file down and leave a quiet one quiet, so the author cannot know how
loud the video will play. `docs/FEATURES.md` lists this as "Not included:
loudness normalisation" (the `--for` section) and gives the reasons: it changes
the audio of every render, it needs its own flag and its own measurement, and a
single `loudnorm` pass does not do the two-pass measurement that its name suggests.

After this change: `video-code scene.py --generate out.mp4 --loudness -14`
writes a file whose integrated loudness is −14 LUFS. A separate measurement of
the written file confirms the value. Without the flag nothing changes.

## Decisions

| Decision | Source |
|---|---|
| Build it now, in parallel with #443, without a separate approval stop for this spec | Stated by the user, 2026-11-23 ("open issue for 4 and 5 and directly implement them in parallel using sdd") |
| Opt-in flag `--loudness <LUFS>`. There is no default target. | The controller's choice: `docs/VEILLE.md` says "La cible sera un réglage", and a default would change every render |
| True-peak ceiling −1 dBTP, fixed | The controller's choice, from the Spotify figure below |
| Export only. The editor preview keeps playing the mix without normalisation, and the docs say so. | The controller's choice. The preview bakes a WAV after each run, and a measurement pass there adds a delay to every run. Left for a later issue. |

## Evidence

| Fact | Class |
|---|---|
| Installed ffmpeg is `n9.0.2`. Its `loudnorm` takes `I` (−70..−5, default −24), `LRA` (1..50, default 7), `TP` (−9..0, default −2), `measured_I`, `measured_LRA`, `measured_TP`, `measured_thresh`, `offset`, `linear` (default true), `print_format` (none, json, summary) | Measured: `ffmpeg -h filter=loudnorm`, 2026-11-23 |
| Two-pass `loudnorm` reaches the target. A 6 s 440 Hz tone measured −41.75 LUFS on pass 1 (`I=-14:TP=-1:LRA=11:print_format=json`). Pass 2 with the measured values, `linear=true` and `aresample=48000`, then `-c:a aac`, gave a file that `ebur128=peak=true` measured at −14.0 LUFS and 48000 Hz | Measured, one tone, 2026-11-23 |
| Pass 1 on that tone reported `"normalization_type" : "dynamic"`. A one-pass `loudnorm` falls back to dynamic mode | Measured, the same run |
| Spotify: −14 LUFS, peak −1 dBTP. Apple Podcasts: −16 LKFS. YouTube, TikTok and Instagram publish no figure. | Documented in `docs/VEILLE.md` (research of 2026-09-28), source support.spotify.com/us/artists/article/loudness-normalization/ |
| The render pipes raw frames into one `ffmpeg` process (`src/compiler/Compiler.cpp`, `popen`). The audio graph comes from `VC::Audio::buildAudioArgs`/`buildAudioGraph` (`src/compiler/AudioMix.cpp`), and the editor's WAV bake uses the same graph | Read in the code, `main` at 67732cc |

## Behaviour

1. `--loudness <LUFS>` is valid with `--generate`. With `--for` and `--data`,
   each file gets its own measurement.
2. A value outside −70..−5, or one that is not a number, is refused before the
   scene runs. The message names the value and the range. `--loudness` without
   `--generate` is refused with the same wording as `--for` without `--generate`.
3. Measurement: before the picture pipe starts, one audio-only ffmpeg run reads
   the same graph that the render will mix (the same inputs, the same filter, the
   same `--from`/`--to` window and the same clamp to the film's length). It ends
   in `loudnorm=I=<t>:TP=-1:LRA=<lra>:print_format=json` and writes to `-f null -`.
   The JSON block is parsed from stderr.
4. Application: the render's filter gets one more stage after the final label:
   `loudnorm=I=<t>:TP=-1:LRA=<lra>:measured_I=…:measured_LRA=…:measured_TP=…:measured_thresh=…:offset=…:linear=true:print_format=summary`,
   then `aresample=48000`. The output label changes to match.
   `<lra>` is the larger of 11 and the measured LRA, capped at 50. A target
   below the measured range is what makes `loudnorm` give up linear mode.
5. Report: one line on stdout, for example
   `Loudness: -23.4 LUFS -> -14.0 LUFS target (linear)`. The type is the one
   ffmpeg reports. A `dynamic` result is printed, not hidden.
6. When nothing is normalised, the render goes on as before and prints one line
   with the reason. This happens for a scene with no sound, a GIF output, and a
   mix that measures −70 LUFS or lower, where the gain would be unbounded.
7. Without `--loudness`, `buildAudioArgs` returns byte-for-byte the string it
   returns on `main`, and the digest of the 54 scenes stays unchanged.

## Not in scope

The editor preview and its Export dialog. A loudness default. Changing the
target per sound (that is `volume`). A `--lint` rule.

## Commands

```
cmake -S . -B build -G Ninja -DCI_BUILD=ON      # with -DFETCHCONTENT_SOURCE_DIR_<DEP>= in a worktree
cmake --build build --target video-code
cp build/video-code video-code                  # the tests run ./video-code (issue #402)
source <main checkout>/.venv/bin/activate
python3 test/loudness_test.py
./test/run_tests.sh
python3 -m pyright
python3 test/coverage_check.py
python3 test/perf/digest.py
cmake --build build --target video-code-tests && ./build/video-code-tests
clang-format -i <touched .cpp/.hpp>
```

## Project structure

- `src/Main.cpp`: the argument and its help text.
- `src/core/ScreenSize.cpp`, `include/core/ScreenSize.hpp`: where the render options (`renderFrom`) are collected, if the flag joins them.
- `src/compiler/AudioMix.cpp`, `include/compiler/AudioMix.hpp`: the measurement and the extra filter stage.
- `src/compiler/Compiler.cpp`: the measurement before `popen`, and the report line.
- `test/loudness_test.py`: new.
- `docs/ffmpeg.md`: the user-facing paragraph.

## Code style

C++20, `std::format`, the comment style of `AudioMix.cpp` (a comment says why,
and what was measured). Python tests follow `test/sound_test.py` (`helpers.check`,
`section`, `summary`).

## Testing strategy

- A C++ or Python check that `buildAudioArgs` without loudness is unchanged.
- An end-to-end test that renders a short scene with one `Sound` at a known
  level through `./video-code --generate`, at `-14` and at `-16`. `ebur128`
  measures each file, and the test asserts the target ±1 LU. The sound is
  generated by the test with ffmpeg `lavfi`, not committed.
- Refusal tests: out-of-range value, a value that is not a number, and no
  `--generate`. Each asserts the message text, not only the exit code.
- A no-sound scene and a GIF each print their reason and exit 0.

## Boundaries

- Always: keep the output without the flag byte-identical, and measure the written file.
- Ask first: any change to the default render, a new dependency.
- Never: run `make check` (it writes `test/perf/history.jsonl`), rewrite goldens, edit `docs/FEATURES.md`, `docs/board.html` or `docs/FEATURES_TODO.md` (the controller does those after the merge).

## Success criteria

The acceptance criteria of #442, word for word.
