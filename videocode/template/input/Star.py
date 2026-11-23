#!/usr/bin/env python3

from __future__ import annotations

import math

from videocode import *
from videocode.utils.decorators import prop


class Star(Polygon):
    """
    A star with `points` branches: a `Polygon` of `2 * points` vertices
    alternating between the `outer` radius (the tips) and the `inner` radius
    (the notches between them), centred on its origin.

    The first vertex is the tip straight up at `(0, outer)`; the rest follow
    clockwise, the winding the other polygons use. Changing `points`,
    `outer` or `inner` after creation rebuilds the geometry.
    """

    def __init__(
        self,
        points: int = 5,
        outer: wufloat = 1,
        inner: wufloat = 0.4,
        fillColor: paint = YELLOW,
        strokeColor: rgba = TRANSPARENT,
        strokeWidth: wufloat = 0,
        cornerRadius: percent = 0,
    ):
        self.starPoints = points
        self.outer = outer
        self.inner = inner

        super().__init__(
            vertices=self.generateVertices(),
            fillColor=fillColor,
            strokeColor=strokeColor,
            strokeWidth=strokeWidth,
            cornerRadius=cornerRadius,
        )

    def generateVertices(self) -> list[point]:
        """
        The `2 * starPoints` vertices, tips on `outer` and notches on
        `inner`, starting at the top tip `(0, outer)` and going clockwise.
        """
        step = math.pi / self.starPoints
        vertices: list[point] = []
        for i in range(2 * self.starPoints):
            r = self.outer if i % 2 == 0 else self.inner
            angle = math.pi / 2 - i * step
            vertices.append((r * math.cos(angle), r * math.sin(angle)))
        return vertices

    # `points` is taken by Polygon (the built control points sent to C++).
    @prop(onSet=Polygon.updatePoints)
    def starPoints() -> int:
        """Number of branches (tips); the polygon has twice as many vertices."""
        ...

    @prop(onSet=Polygon.updatePoints)
    def outer() -> wufloat:
        """Radius of the tips, from the centre."""
        ...

    @prop(onSet=Polygon.updatePoints)
    def inner() -> wufloat:
        """Radius of the notches between the tips, from the centre."""
        ...
