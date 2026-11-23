#!/usr/bin/env python3

"""
Assertion-based smoke tests for `Star`
(`videocode/template/input/Star.py`) — a `Polygon` whose `2 * points`
vertices alternate between the outer and the inner radius, the first one at
the top.
Run directly: `python3 test/star_test.py`
"""

import math
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "test")
from helpers import check, section, summary

from videocode import Polygon
from videocode.template.input._inputs import Star

def approx(a: float, b: float, tol: float = 1e-6) -> bool:
    return abs(a - b) < tol

# ── default: 5 points, outer=1, inner=0.4 ────────────────────────────────────
section("Star(): default 5-point star")
s = Star()
check("is a Polygon", isinstance(s, Polygon))
check("vertex count == 2 * points", len(s.vertices) == 10)
check("first vertex at the top", approx(s.vertices[0][0], 0) and approx(s.vertices[0][1], 1))
check("first vertex is the highest", all(s.vertices[0][1] >= v[1] for v in s.vertices))
radii = [math.hypot(x, y) for x, y in s.vertices]
check("even vertices on the outer radius", all(approx(r, 1) for r in radii[0::2]))
check("odd vertices on the inner radius", all(approx(r, 0.4) for r in radii[1::2]))
check("second vertex is clockwise of the first (x > 0)", s.vertices[1][0] > 0)
expected = [(r * math.cos(math.pi / 2 - i * math.pi / 5), r * math.sin(math.pi / 2 - i * math.pi / 5)) for i, r in enumerate([1, 0.4] * 5)]
check("vertex i sits at 90° minus i tenths of a turn", all(approx(x, ex) and approx(y, ey) for (x, y), (ex, ey) in zip(s.vertices, expected)))
check("no stroke and sharp corners by default", s.strokeWidth == 0 and s.cornerRadius == 0)

# ── custom points/radii ──────────────────────────────────────────────────────
section("Star(points=7, outer=2, inner=0.5)")
s7 = Star(points=7, outer=2, inner=0.5)
check("vertex count == 2 * points", len(s7.vertices) == 14)
check("first vertex at the top", approx(s7.vertices[0][0], 0) and approx(s7.vertices[0][1], 2))
check("inner radius used", all(approx(math.hypot(x, y), 0.5) for x, y in s7.vertices[1::2]))

# ── geometry rebuilds on change ──────────────────────────────────────────────
section("Star: changing starPoints rebuilds the vertices")
s.starPoints = 6
check("vertex count follows starPoints", len(s.vertices) == 12)
s.outer = 3
check("first vertex follows outer", approx(s.vertices[0][1], 3))
s.inner = 1
check("generateVertices() follows inner", all(approx(math.hypot(x, y), 1) for x, y in s.generateVertices()[1::2]))

# ── summary ──────────────────────────────────────────────────────────────────
summary()
