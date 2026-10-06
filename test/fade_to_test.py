#!/usr/bin/env python3
"""
`fadeTo(o)` reaches an opacity from wherever the element stands, and `at=`
says when in the film.

Run directly: `python3 test/fade_to_test.py`
"""
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "test")
from helpers import check, section, summary

from videocode import *


def opacityAt(i: Input, frame: int) -> float:
    return Context.stateAt(i.meta.index, frame)["Opacity"]


section("fadeTo reaches an opacity from where the element stands")

dimmed = Square(side=1).fadeTo(80)
check("from opaque: twelve frames, the last one on the value, and it stays",
      [opacityAt(dimmed, f) for f in (0, 11, 20)] == [255, 80, 80])

raised = Square(side=1).opacity(40).fadeTo(200)
check(f"from where it stands, not from 255 ({opacityAt(raised, 0)} → {opacityAt(raised, 11)})",
      opacityAt(raised, 0) < 60 and opacityAt(raised, 11) == 200)

later = Square(side=1)
wait(2)
later.fadeTo(0, at=1)
check("at= counts from the start of the film: untouched before, reached twelve frames in",
      [opacityAt(later, f) for f in (29, 41)] == [255, 0])

summary()
