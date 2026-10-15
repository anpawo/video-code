#!/usr/bin/env python3
"""
`test/mutants.py` on sources small enough to read: which wrong versions of a
line it makes, which added lines it counts as code, and what a diff adds.
"""
import sys

sys.path.insert(0, "test")

from helpers import check, section, summary  # noqa: E402
from mutants import hunks, mutants, statements  # noqa: E402

SOURCE = '''\
def clamp(x, low=0, high=1):
    """Between low and high."""
    # a comment
    if x < low and not x is None:
        return low
    return min(x, high) * 2


def f(a, *, b):
    return a is not b
'''


def changed(n: int) -> set[str]:
    return {what for what, _ in mutants(SOURCE, n)}


section("mutants — one wrong version per token, and only versions that compile")
check("a comparison turns round, and/or swap, not goes", changed(4) == {"< → >=", "and → or", "not → (removed)", "is → is not"})
check("defaults move by one", changed(1) == {"0 → 1", "1 → 2"})
check("a binary * becomes /, a number moves", changed(6) == {"* → /", "2 → 3"})
check("a bare * in a signature is left alone", changed(9) == set())
check("`is not` loses its not, and is not doubled", changed(10) == {"not → (removed)"})
check("each version differs on its own line only", all(
    [a for a, b in zip(SOURCE.splitlines(), text.splitlines()) if a != b] == [SOURCE.splitlines()[3]]
    for _, text in mutants(SOURCE, 4)
))

section("statements — which added lines are code, and where they report being run")
owned = statements(SOURCE, "<test>", set(range(1, 11)))
check("comments, blank lines and docstrings are not code", not {2, 3, 7, 8} & owned.keys())
check("a line reports as its own statement", owned.get(5) == 5 and owned.get(10) == 10)
marked = SOURCE.replace("return low", "return low  # untested: a reason")
check("a line marked # untested: is left out", 5 not in statements(marked, "<test>", {5}))

section("hunks — the lines a diff adds, numbered in the new file")
patch = """\
diff --git a/videocode/a.py b/videocode/a.py
+++ b/videocode/a.py
@@ -3,0 +4,2 @@ def f():
@@ -10 +12 @@ def g():
+++ /dev/null
@@ -1,3 +0,0 @@
+++ b/videocode/notes.md
@@ -1 +1 @@
"""
check("added lines, single lines, nothing from deleted or non-Python files", hunks(patch) == {"videocode/a.py": {4, 5, 12}})

summary()
