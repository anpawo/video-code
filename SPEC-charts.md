# Spec: `LineChart` and `PieChart`

Module id: `charts`. Issue: #443. Written 2026-11-23.

## Objective

`BarChart` and `Leaderboard` (`videocode/template/input/BarChart.py`) are the
only charts made from data. `Graph` plots functions, not rows. A line chart and
a pie chart are still written by hand: a polyline, its dots and labels, and
wedges whose angles someone added up. The author of an explainer video wants to
pass the rows and get a chart whose numbers stay with their shapes while it
animates in. `BarChart` already gives that for bars.

## Decisions

| Decision | Source |
|---|---|
| Build it now, in parallel with #442, without a separate approval stop for this spec | Stated by the user, 2026-11-23 ("open issue for 4 and 5 and directly implement them in parallel using sdd") |
| The same data forms, `fromCSV`, units and keyword names as `BarChart` (`width`, `height`, `top`, `color`, `fontSize`, `showValues`) | The controller's choice: one vocabulary for the chart family |
| `LineChart` scale floor `bottom=0` by default, as the bar chart's baseline is 0 | The controller's choice. A line chart that starts its axis at the minimum exaggerates change, so that stays an explicit `bottom=` |
| Percentages rounded by largest remainder, so that they add up to 100 | The controller's choice. `Hemicycle` already uses largest remainder for seats (`docs/FEATURES_TODO.md`, C16) |
| No new golden image. Geometry is tested numerically, and the controller renders a `--sheet` and looks at it | The controller's choice. A golden is written only after a human has looked at it (`docs/FEATURES_TODO.md`, rule 1) |

## Evidence

| Fact | Class |
|---|---|
| `BarChart.__init__(data, *, width=8, height=3.5, gap=0.3, top=None, color=BLUE_C, fontSize=0.28, showValues=True)`. `_rows()` accepts a dict or a list of pairs. `fromCSV(path, label=, value=)` refuses a bad cell by its line. `grow()` moves each value with its bar | Read in `videocode/template/input/BarChart.py`, `main` at 67732cc |
| Scenes import templates by module: `from videocode.template.input.BarChart import BarChart`. Nothing re-exports it from `videocode` | Read: the only other `.py` users are `videocode/context.py:1014` and a docstring in `videocode/serialize.py:1110` |
| `docs/FEATURES.md` lists `BarChart` and `Leaderboard` at lines 203–204, in a table of templates | Read, `main` at 67732cc |
| `test/barchart_test.py` checks geometry with `helpers.check` and reads frame-by-frame values from `Context` | Read |

## Behaviour

### `LineChart`

```python
LineChart(data, *, width=8, height=3.5, top=None, bottom=0, color=BLUE_C,
          fontSize=0.28, showValues=True, dots=True, strokeWidth=0.05)
LineChart.fromCSV(path, label=..., value=..., **options)
chart.draw(duration=1.2, easing=Easing.InOut) -> LineChart
```

- One point per row. The points are evenly spaced across `width`, the first at
  the left edge and the last at the right edge. A single row is one point in the
  middle.
- The y scale runs from `bottom` (at the baseline, `-height/2`) to `top` (at
  `+height/2`). `top` defaults to the highest value. A value below `bottom` or
  above `top` is refused, and the message names its row. `top <= bottom` is refused.
- Under each point there is its label. When `showValues` is on, the value is
  above the point (written as `BarChart._say` writes it). When `dots` is on,
  there is a dot at the point.
- Built complete, like every input. `draw()` is the entrance: the line grows
  from the first point to the last. Dot `i` and value `i` appear at the frame
  the line reaches point `i`, ±1 frame. The test reads this frame by frame.
- The chart is centred on the group's position.

### `PieChart`

```python
PieChart(data, *, radius=1.6, colors=None, donut=0, startAngle=90, clockwise=True,
         fontSize=0.24, showLabels=True, showPercent=True)
PieChart.fromCSV(path, label=..., value=..., **options)
chart.grow(duration=0.8, every=0.1, easing=Easing.InOut) -> PieChart
```

- One slice per row, in data order, starting at `startAngle` (degrees, 90 =
  the top) and going clockwise unless `clockwise=False`. Each slice's angle is
  `360 * value / sum`, and the angles add up to exactly 360.
- `colors=None` cycles a fixed palette from `videocode.constants`. A list
  gives the colour of each slice in order, and a list shorter than the data is
  refused.
- `donut` is the hole's radius as a fraction of `radius`, `0 <= donut < 1`.
- Each slice's label sits outside the ring, on the slice's middle angle. When
  `showPercent` is on, the label carries its percentage. The percentages are
  rounded by largest remainder to whole numbers that add up to exactly 100.
- Refused, and the message names the cause: a negative value, a data set whose
  sum is 0, a `donut` outside the range, and no rows.
- `grow()`: slice `i` starts at `i * every` and sweeps open from its own start
  angle to its full angle over `duration`. Its label appears when the slice
  has finished opening.

### Both

- The row parsing (`_rows`) and the CSV reading of `BarChart.fromCSV` are
  reused, not copied. Moving them into a shared helper in the same package is
  allowed, and `BarChart`'s behaviour and tests stay unchanged.

## Not in scope

Axes with ticks and gridlines, several series in one chart, legends, animated
value changes after the entrance (that is #183, tracked values).

## Commands

```
source <main checkout>/.venv/bin/activate
python3 test/linechart_test.py
python3 test/piechart_test.py
./test/run_tests.sh
python3 -m pyright
python3 test/coverage_check.py
python3 test/repetition_check.py
python3 test/perf/digest.py
```

No C++ change, so no rebuild. The tests that need the binary run `./video-code`.
In a worktree, build it once or copy it from the main checkout's `build/video-code`.

## Project structure

- `videocode/template/input/LineChart.py`, `videocode/template/input/PieChart.py`: new.
- `videocode/template/input/BarChart.py`: only if `_rows` or the CSV reading moves into a shared helper.
- `test/linechart_test.py`, `test/piechart_test.py`: new.
- `docs/FEATURES.md`: one row for each, next to `BarChart` (lines 203–204).

## Code style

Follow `BarChart.py`: a module docstring that says why the template exists,
keyword-only options, `ValueError` messages that name the value, and comments
that say why.

## Testing strategy

Follow `test/barchart_test.py`. Test the geometry (positions, angles, sums),
the refusals (each with an input that is valid except for the field under test,
and with an assertion on the message text), `fromCSV`, and the entrance frame by
frame.

## Boundaries

- Always: keep `BarChart`'s behaviour and its tests unchanged, and keep the digest of the 54 scenes unchanged.
- Ask first: a new dependency, a change to `Polygon` or another core input.
- Never: write a golden image, run `make check` (it writes `test/perf/history.jsonl`), or edit `docs/board.html`, `docs/FEATURES_TODO.md` or any file under `src/`.

## Success criteria

The acceptance criteria of #443, word for word.
