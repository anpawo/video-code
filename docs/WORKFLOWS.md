# What guards the repo

Three places, split by what each can actually decide. Nothing blocks a push to
a branch; `main` only takes pull requests Claude has reviewed
([below](#main-takes-pull-requests)).

| where | what it checks | when | blocks? |
|---|---|---|---|
| **GitHub Actions** | types, the suites, docs/test coverage of new API, qmllint, formatting, the build, the C++ unit tests, the QML chrome, `eg.py` still renders, the bake digest | every push and PR | the run goes red, the push already landed |
| **the review** (`.github/workflows/review.yaml`, Claude) | a bug it can point to, a weakened test, a secret, code reaching for credentials | every pull request into `main` | yes: `main` merges nothing without its check |
| **the weekly audit** (`.github/workflows/audit.yaml`, Claude) | two functions doing one job, a public name nothing calls | Mondays 06:00 UTC, or by hand | no: at most three draft PRs |
| **`make check`** | visual regression, C++ unit tests, bake digest, performance — and RECORDS the timings into `test/perf/history.jsonl` | when you ask for it | no |
| **`/ship`** | writes the docs, tests and examples a change owes | before committing | no |
| `.githooks/pre-commit` | what the repo forgot to commit, coverage, types, the QML chrome (~15 s) — armed with `make arm` | on commit, once armed | yes |

## The board

One page says what is happening, so nobody has to ask:
**https://claude.ai/code/artifact/a80200f9-2f71-48e8-b59e-7a8d6353e3ca**

Its source is `docs/board.html`. Edit that file and publish it to the same URL.
Five sections, colour-coded and fixed: **Needs your check** (orange, the only
one that asks something of a person), **In progress** (blue), **To do** (green,
split by what BLOCKS each group rather than by theme), **Won't do** (red, with
the reason in the right-hand column — that column is the point of the section),
**Shipped** (with the commit's short SHA).

Update it as the state changes, not at the end of a session: a board that is
right once a day is a board someone has to ask about. Hover a row for a third of a second and its
three-bullet detail opens; the bullets live in that row's `data-b`.

`docs/FEATURES_TODO.md` is the long form of the same information — measurements,
numbers, designs that were rejected and why. The board is the view; that file is
the record. Keep them agreeing.

## GitHub does the waiting

The `fast` job of `.github/workflows/ci.yaml` runs the suites and pyright. It
also runs `test/coverage_check.py --pushed`, which reads every public symbol the
pushed range adds to the library (`videocode/`, `src/`, `include/`) and asks:

- is there a docstring where it is defined?
- is it mentioned in `docs/*.md`?
- is it mentioned in `test/`?

For C++ it reads headers only: a type declared in a `.cpp` is reachable by
nobody, so it is not surface. Asking a function-local helper for a documentation
page is a false alarm, and a false alarm on a hook is how a team learns to type
`--no-verify`.

It never writes anything, and it greps for names — so it cannot see a docstring
that lies or a test that asserts nothing. It is the floor, not the ceiling. When
it goes red, run `/ship` and push again. A deliberate exception is fine: say why
in the commit message.

The build job now renders `eg.py` too. That file is the living showcase of every
feature worth seeing, so if it stops rendering, an example in the docs has gone
stale — which is the failure mode documentation actually has.

## main takes pull requests

Since 2026-10-22 ([#408](https://github.com/anpawo/Video-Code/issues/408)) nobody
pushes to `main`: a change arrives as a pull request, and the ruleset `main`
lets it merge once two things hold.

- **The check `Claude review` is green.** `.github/workflows/review.yaml` runs
  on every pull request into `main` that is not a draft and follows
  `.github/prompts/review.md`: Claude reads the diff without running it, fails
  it only for something it can point to (a bug, a weakened test, a secret, code
  reaching for credentials, a change its description does not say), comments
  on the rest, and posts the check. The ruleset accepts that check only from
  the Claude GitHub App, so no workflow can post it in its place. Each push to
  the pull request is reviewed again. Claude never merges: its token cannot
  write to the repository, and a person merges once the check is green.
- **A change under `.github/` has Marius's approval** (`.github/CODEOWNERS`).

Marius bypasses both.

Both Claude jobs set `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB`: the commands Claude
runs (the audit's tests included) get no Claude token in their environment and
run apart from Claude's process. The action calls it best-effort: it narrows
what a prompt injection or a hostile test can reach, it does not close it.

Why: the Claude token runs on Marius's subscription, and a repository secret
reaches any workflow that anyone with write access writes, on any branch. The
token now lives in the environment `claude`, which only a job running on `main`
can open, and `main`'s workflows only change with his approval.

## The weekly audit

`test/repetition_check.py`, in the `fast` job and in the pre-commit hook, is the
gate: it records every verbatim clone by the hash of its content in
`test/repetition.json` and refuses one the record does not know, in the Python,
the C++, the QML and the GLSL. What it cannot see is two functions doing one job
with DIFFERENT code. That takes reading, so Claude reads, once a week:
`.github/workflows/audit.yaml` runs `anthropics/claude-code-action` on Marius's
subscription (the `CLAUDE_CODE_OAUTH_TOKEN` secret of the `claude` environment,
made by `claude setup-token`),
not on an API key.

Its instructions are `.github/prompts/audit.md`, versioned here so a change to
them is a commit. It runs the script's `--candidates` and `--list`, reads, and
for at most three findings opens a DRAFT pull request on a `claude/audit-*`
branch, assigned to Marius, only for a deletion it has run the tests on. Nothing
else: no email, no issue, and nothing at all on a week with nothing worth his
time. It never pushes to `main` and never merges. Its pull requests come from
the Claude GitHub App, so CI runs on them.

It remembers what it has already raised by listing its own `claude/audit-*`
pull requests, so a finding is not proposed twice unless its code changed.
Closing a draft PR is how a finding is refused.

The perf half was dropped at the end of its trial (2026-09-18 to 2026-10-16):
with no email, its questions had nowhere to go. The `fast` job says the one
thing a runner can say about speed honestly: `history.py --stale` warns when
more than ten engine commits have gone unmeasured.

**Declaring a twin.** Two files alike on purpose go in `test/twins.json`:

```json
{ "files": ["src/a.cpp", "src/b.cpp"], "reason": "why they stay two", "date": "2026-09-18" }
```

`files` takes globs. Inside a declared pair the script fails on GROWTH of the
repeated lines rather than on a new hash — a bug fixed on both sides changes
the hashes and must stay green — and prints a warning when a clone VANISHES
from the pair, which is what a fix applied to one side only looks like. The
audit is told to stay silent on the pair.

**Accepting a new clone.** The refusal names it — `file:line ↔ file:line (N
lines)`. If it is deliberate:

```bash
python3 test/repetition_check.py --update
```

and the diff of `repetition.json` shows one line per clone you accepted.

## One rule, one place

Two of the defects this repository was audited for were a rule written twice
whose copies agreed by coincidence. `Context.channelKey` is the answer to *what
name does this piece of state answer to*: `Args:<name>` for an `args` shader,
the class name for everything else. It is asked by `Context.apply`, which
stores a frame under that key, and by `Input.apply`, which decides from it
whether two statements are rivals. Had those two ever drifted apart, the editor
would have warned about the wrong pairs while the stack stored under a
different name, and nothing would have said so. `test/contention_test.py`
asserts that they agree — not that either is right on its own, which is the
part a single-sided test would have missed.

## Done (2026-09-01): the pivot was a query, and is now a value

A council of six seats (2026-08-31, `~/.claude/councils/2026-08-31-videocode-semantique-groupes/`)
compared Manim, After Effects, Blender, Figma/SVG, Lottie and glTF against this
repository. Its conclusion, and the reason it is written here rather than acted
on: **the redesign is decided, the urgency is not.**

**What is wrong.** `Group._pivot(align)` is a function of `(content, align)`
re-evaluated at read time. There is no way for an author to place the point by
hand — `videocode/shader/vertexShader/` has no `pivot`, no `anchor`, no
`about_point`, and `align(x, y)` is itself a fraction of the derived bounding
box. Every other engine on the table lets the author answer that question;
this one only lets them ask it. So the code is stuck between two measured
failures:

| | measured |
|---|---|
| pivot frozen (today, `_MemberBase._snapshot`) | a group transform overwrites a member's own animation — **29 frames of 30**, silently, and it hits a plain leaf exactly as hard as a nested group |
| pivot live (sampling restored) | `Group(Group(a,b),c).rotateBy(90)` → **58 distinct pivots**, formation diverging by **~960×** over 30 frames |

**What was done, in this order.** Item 1 is the one that mattered; the rest
followed from it and were cosmetic on their own. All five landed on
2026-09-01, each byte-identical on the corpus except item 4, which changed
nothing there either — the three single-frame collisions counted below turned
out to compose to the same numbers.

1. **An author-placed pivot.** `about_point` on `rotate`/`scale`, plus a named
   granularity for `Text` in the shape of After Effects' `Anchor Point
   Grouping` (Character / Word / Line / All) — a `Letter` has no downstream
   identity to parent to, so its pivot has to be a rule the engine resolves at
   emission. This one retires the `isinstance` tests **and** the freeze **and**
   the re-emission.
2. `_MemberBase.parentInverse: v2`, zero for a leaf, replacing
   `pivot: maybe[v2]`. This is Blender's `matrix_parent_inverse`: a stored
   correction rather than a branch. Measured byte-identical on 49/49 scenes and
   43/43 test files — free, and **cosmetic if done alone**.
3. The emitted frame carries a pivot resolved to a number, never a
   `_pivot(align)` re-read.
4. Compose a member's timeline with the group's instead of overwriting it.
   Closes the whole class. The large piece.
5. Name the axis *placed vs composite* in the code — a `Group` has
   `meta.index is None` and never reaches `Context.stack`, and that, not the
   pivot, is what makes it a different kind of thing.

**Why it had been postponed.** Zero animations were actually lost anywhere in
the 55-scene corpus: the three real channel collisions are single-frame
placements a parent legitimately replaced. The defect was reproducible in three
lines and had bitten nobody. Item 1 changes the public API and deserved to be
decided when someone needed it, not because a council named it. That decision
was reversed on 2026-09-01 and the five items were done in order.

**Item 2 was never done on its own.** It passes every gate while teaching the
codebase that groups and leaves are the same kind of thing, which is the one
conclusion the council rejected — item 1 landed before it, and item 5 named the
axis that does separate them: `placed` vs `composite`, a slot in the stack
rather than a pivot.

**What the API gained.** `rotateTo`/`rotateBy`/`scaleTo`/`scaleBy` take
`about=v2(x, y)`; `Text.anchor` takes `Anchor.CHARACTER | WORD | LINE | ALL`,
After Effects' Anchor Point Grouping, resolved at emission because a `Letter`
has nothing an author could hold. `test/pivot_about_test.py` and
`test/group_defect_test.py` hold both ends.

## What GitHub cannot check, and why

**Visual regression.** The goldens in `test/visual/golden/` were rendered on
Apple Silicon through Metal. The CI runner has no GPU and falls back to software
Vulkan (`mesa-vulkan-drivers`), whose antialiasing differs — every scene would
fail, for reasons that have nothing to do with the change. Comparing pixels
means comparing them against the same renderer.

**Performance.** A shared runner's timings, on software rendering, say nothing
about a baseline measured on this machine — measured, the runner renders at
589 ms/frame against ~8 ms here, which is a different rasterizer rather than a
noisier one. So the split is: **this machine measures, GitHub remembers.**
`make check` appends one line per commit to `test/perf/history.jsonl`, which
travels in the commit like a golden, and the `history` job publishes the curve
without ever running a benchmark. What CI *can* compute exactly is what the
scenes ASK the renderer to do — `test/perf/digest.py`, a per-scene hash of the
bake, held to zero tolerance on any runner.

A threshold on wall time would either never
fire or fire constantly.

Both live in `make check` instead:

```bash
make check
```

- **Visual** — renders every scene in `test/visual/scenes/` and compares against
  its golden. Only failures *not* listed in `test/visual/known_failures.txt`
  count, so "already broken" is never mistaken for "broken just now".
- **Performance** — `test/perf/guard.py` re-runs the benchmark and compares
  against `test/perf/baseline.json`: load time (+30 % tolerated), render speed
  (+20 %), total wall time (+20 %), peak memory (+25 %). Timings keep the best
  of three runs; the mean drags in whatever else the laptop was doing.

Never run a blanket `--update-golden` to make a suite green. A golden can be
recording a bug: the `matte` golden did exactly that on 2026-07-28, blessing a
word whose letters were mis-spaced. Look at the image, decide whether the new
render is right, and regenerate that one scene alone.

Re-baselining performance is a decision, not a chore:

```bash
python3 test/perf/guard.py --update
```

Do it when a change makes the renderer legitimately slower (a feature worth its
cost) or legitimately faster (then the new floor protects the win), and say
which in the commit message. `docs/optimization.md` records how the current
numbers were earned — start there before accepting a regression.

## `/ship` — the half a script cannot do

CI decides whether a change is *allowed* in. The skill makes it *worth* letting
in: it reads the diff, writes the missing docstrings, the `docs/*.md` entries and
the tests, adds a **runnable** example for each, and checks whether the
surrounding documentation went stale — a wrong doc is worse than a missing one,
because it is trusted.

Deterministic checks block; judgement writes. Keeping them apart is why nothing
on your critical path is slow.

## The optional local hook

If you would rather catch the coverage debt before pushing than read it off a
red CI run:

```bash
git config core.hooksPath .githooks     # arms .githooks/pre-commit (~12 s)
git config --unset core.hooksPath       # disarms it
```

It runs the coverage check only — types and tests stay on GitHub, and nothing
gated to a push. `git commit --no-verify` bypasses it once.
