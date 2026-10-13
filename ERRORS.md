# Errors

Mistakes Claude Code made in this project. One line each: date — what went wrong — what to do instead.

- 2026-10-12 — Read `Context.cursor` as the scene's clock while writing a template (`videos/lol/runes.py`), from its use in `tutorial.py`, where it is read right after a `wait()`; it is the end of the last statement written, so a page laid out after a 10 s zoom scheduled its greys from second 10 and came out 110 s long, seen only because the frame count was printed — the clock a template starts from is `Context.waitOffset`, and a template's length is read in frames (`--inspect`) before its picture is looked at.
- 2026-10-13 — Scheduled a label's pop with `apply(popIn(), start=at)` (`videos/politics/assembly.py`); `apply`'s `start` does not move an effect, which keeps its own clock, so the pop ran at second 0 while the label was hidden and the label then appeared whole, seen only when its width was measured at every frame — an effect's start goes in the effect (`popIn(start=at)`), and an entrance is checked by measuring the element on each frame of it, not on stills taken after it.
