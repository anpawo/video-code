#!/usr/bin/env python3

from __future__ import annotations

import math

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable, Generator, overload
from videocode.constants import FRAMERATE, number
from videocode.ty import Arithmetic, sec, index

if TYPE_CHECKING:
    from videocode.input.input import Input


class RateFunc(ABC):
    """
    A function `t in [0, 1] -> m` mapping animation progress to interpolation
    weight, used by `range`/`rangeIdx` as `start + (end - start) * self(t)`.
    """

    @abstractmethod
    def __call__(self, t: float) -> float: ...

    @overload
    def range(self, start: int, end: int, duration: sec) -> Generator[float, Any, None]: ...
    @overload
    def range[T: Arithmetic](self, start: T, end: T, duration: sec) -> Generator[T, Any, None]: ...
    def range(self, start: Any, end: Any, duration: sec) -> Generator[Any, Any, None]:
        n = int(duration * FRAMERATE)
        for i in range(0, n):
            t = i / (n - 1) if n > 1 else 0.0
            yield start + (end - start) * self(t)

    @overload
    def rangeIdx(self, start: int, end: int, duration: sec) -> Generator[tuple[float, index], Any, None]: ...
    @overload
    def rangeIdx[T: Arithmetic](self, start: T, end: T, duration: sec) -> Generator[tuple[T, index], Any, None]: ...
    def rangeIdx(self, start: Any, end: Any, duration: sec) -> Generator[tuple[Any, index], Any, None]:
        # An animation of n frames must ARRIVE on its last one. At n == 1 that
        # last frame is also the first, so it carries the destination, not the
        # start — the old 0.0 meant a one-frame move emitted where it began and
        # never got anywhere, and `duration=0` produced n == 0 and no frames at
        # all: an author asking for an instant move got silence.
        n = max(1, int(duration * FRAMERATE))
        for i in range(0, n):
            t = i / (n - 1) if n > 1 else 1.0
            yield start + (end - start) * self(t), i


class CubicBezier(RateFunc):
    def __init__(
        self,
        #
        x1: number,
        y1: number,
        x2: number,
        y2: number,
    ) -> None:
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2

    def bezier(self, t, p0, p1, p2, p3):
        return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t**2 * p2 + t**3 * p3

    def derivative(self, t, p0, p1, p2, p3):
        return 3 * (1 - t) ** 2 * (p1 - p0) + 6 * (1 - t) * t * (p2 - p1) + 3 * t**2 * (p3 - p2)

    def solveTForX(self, x):
        """
        Newton-Raphson
        """
        t = x
        for _ in range(8):
            x_t = self.bezier(t, 0, self.x1, self.x2, 1)
            dx_dt = self.derivative(t, 0, self.x1, self.x2, 1)
            if dx_dt == 0:
                break
            t -= (x_t - x) / dx_dt
            t = max(0, min(t, 1))
        return t

    def getValueAtX(self, x: float):
        t = self.solveTForX(x)
        return self.bezier(t, 0, self.y1, self.y2, 1)

    def __call__(self, x: float) -> float:
        return self.getValueAtX(x)


class Func(RateFunc):
    """
    Wraps an arbitrary `t in [0, 1] -> m` function as a `RateFunc` —
    used for rate functions that aren't expressible as a `CubicBezier`
    from (0, 0) to (1, 1), e.g. non-monotonic ones like `Easing.ThereAndBack`
    or `Easing.Wiggle`.
    """

    def __init__(self, fn: Callable[[float], float]) -> None:
        self.fn = fn

    def __call__(self, t: float) -> float:
        return self.fn(t)


def _smooth(t: float, inflection: float = 10.0) -> float:
    """Manim's sigmoid-based `smooth` rate function."""
    if t <= 0:
        return 0.0
    if t >= 1:
        return 1.0
    error = 1 / (1 + math.exp(inflection / 2))
    raw = 1 / (1 + math.exp(-inflection * (t - 0.5)))
    return min(max((raw - error) / (1 - 2 * error), 0.0), 1.0)


def _rushInto(t: float) -> float:
    return 2 * _smooth(t / 2)


def _rushFrom(t: float) -> float:
    return 2 * _smooth(t / 2 + 0.5) - 1


def _slowInto(t: float) -> float:
    return math.sqrt(1 - (1 - t) ** 2)


def _doubleSmooth(t: float) -> float:
    if t < 0.5:
        return 0.5 * _smooth(2 * t)
    return 0.5 * (1 + _smooth(2 * t - 1))


def _thereAndBack(t: float) -> float:
    return _smooth(2 * t if t < 0.5 else 2 * (1 - t))


def _thereAndBackWithPause(t: float, pauseRatio: float = 1 / 3) -> float:
    a = 1 / pauseRatio
    if t < 0.5 - pauseRatio / 2:
        return _smooth(a * t)
    if t > 0.5 + pauseRatio / 2:
        return _smooth(a - a * t)
    return 1.0


def _wiggle(t: float) -> float:
    return _thereAndBack(t) * math.sin(2 * math.pi * t)


def _backOut(t: float, overshoot: float = 1.70158) -> float:
    """Standard easeOutBack — overshoots past 1 (~10%) then settles back."""
    c3 = overshoot + 1
    return 1 + c3 * (t - 1) ** 3 + overshoot * (t - 1) ** 2


def _elasticOut(t: float) -> float:
    """Standard easeOutElastic — springs past 1 and oscillates into place."""
    if t <= 0:
        return 0.0
    if t >= 1:
        return 1.0
    c4 = (2 * math.pi) / 3
    return math.pow(2, -10 * t) * math.sin((t * 10 - 0.75) * c4) + 1


def _bounceOut(t: float) -> float:
    """Standard easeOutBounce — lands and bounces like a dropped ball."""
    n1 = 7.5625
    d1 = 2.75
    if t < 1 / d1:
        return n1 * t * t
    if t < 2 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    if t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    t -= 2.625 / d1
    return n1 * t * t + 0.984375


def _exponentialDecay(t: float, halfLife: float = 0.1) -> float:
    return 1 - math.exp(-t / halfLife)


def _exponential(t: float, halfLife: float = 0.1) -> float:
    denom = math.exp(1 / halfLife) - 1
    return (math.exp(t / halfLife) - 1) / denom if denom else t


class Easing:
    # fmt: off
    Linear = CubicBezier(0.0, 0.0, 1.0, 1.0)     # constant speed
    In = CubicBezier(0.42, 0.0, 1.0, 1.0)        # slow start, fast end
    Out = CubicBezier(0.0, 0.0, 0.58, 1.0)       # fast start, slow end
    InOut = CubicBezier(0.42, 0.0, 0.58, 1.0)    # slow start & end, fast middle

    # The easings.net families, with the cubic-bezier control points it
    # publishes. A cubic-bezier only APPROXIMATES these curves — Sine, Expo
    # and Circ have no cubic form, and even Quart is a fit: at t=0.5 each is
    # within 0.01 of its formula (InExpo gives 0.028 against 2^-5 = 0.031).
    # Close enough to feel the same, and it keeps them draggable as curves.
    InSine = CubicBezier(0.12, 0.0, 0.39, 0.0)       # gentlest ease-in
    OutSine = CubicBezier(0.61, 1.0, 0.88, 1.0)      # gentlest ease-out
    InOutSine = CubicBezier(0.37, 0.0, 0.63, 1.0)    # gentlest ease-in-out
    InQuad = CubicBezier(0.11, 0.0, 0.5, 0.0)        # t^2 ease-in
    OutQuad = CubicBezier(0.5, 1.0, 0.89, 1.0)       # t^2 ease-out
    InOutQuad = CubicBezier(0.45, 0.0, 0.55, 1.0)    # t^2 ease-in-out
    InCubic = CubicBezier(0.32, 0.0, 0.67, 0.0)      # t^3 ease-in
    OutCubic = CubicBezier(0.33, 1.0, 0.68, 1.0)     # t^3 ease-out
    InOutCubic = CubicBezier(0.65, 0.0, 0.35, 1.0)   # t^3 ease-in-out
    InQuart = CubicBezier(0.5, 0.0, 0.75, 0.0)       # t^4 ease-in
    OutQuart = CubicBezier(0.25, 1.0, 0.5, 1.0)      # t^4 ease-out
    InOutQuart = CubicBezier(0.76, 0.0, 0.24, 1.0)   # t^4 ease-in-out
    InExpo = CubicBezier(0.7, 0.0, 0.84, 0.0)        # 2^(10t-10) ease-in — near-still, then a rush
    OutExpo = CubicBezier(0.16, 1.0, 0.3, 1.0)       # 1-2^(-10t) ease-out — a rush, then near-still
    InOutExpo = CubicBezier(0.87, 0.0, 0.13, 1.0)    # exponential ease-in-out — sharpest middle
    InCirc = CubicBezier(0.55, 0.0, 1.0, 0.45)       # quarter-circle ease-in — steepest at the end
    OutCirc = CubicBezier(0.0, 0.55, 0.45, 1.0)      # quarter-circle ease-out — steepest at the start
    InOutCirc = CubicBezier(0.85, 0.0, 0.15, 1.0)    # two quarter-circles

    # Manim-inspired rate functions. ThereAndBack, ThereAndBackWithPause and
    # Wiggle end back at t=0 (not t=1) — in range(0, 100, ...) they animate
    # out and back to the start value.
    Smooth = Func(_smooth)                                # sigmoid S-curve — flatter shoulders than InOut
    RushInto = Func(_rushInto)                            # smooth only first half — decelerates into end
    RushFrom = Func(_rushFrom)                            # smooth only second half — accelerates from start
    SlowInto = Func(_slowInto)                            # quarter-circle arc — decelerates at end
    DoubleSmooth = Func(_doubleSmooth)                    # two S-curves chained — extra smooth
    ThereAndBack = Func(_thereAndBack)                    # goes to 1 then returns to 0
    ThereAndBackWithPause = Func(_thereAndBackWithPause)  # goes to 1, holds 1/3, returns to 0
    Wiggle = Func(_wiggle)                                # oscillates positive/negative, ends at 0
    ExponentialDecay = Func(_exponentialDecay)            # jumps instantly then asymptotes to 1 (very good)
    Exponential = Func(_exponential)                      # start slow then boom to 1 (very good)

    # Editor-style overshoot easings (CSS/AE conventions). Back and Elastic
    # exceed 1 mid-animation — with range(start, end, ...) the value briefly
    # passes the target before settling; the classic "pop" feel.
    Back = Func(_backOut)                                 # overshoots ~10% past target, settles back
    Elastic = Func(_elasticOut)                           # springs past target, oscillates into place
    Bounce = Func(_bounceOut)                             # lands on target and bounces like a ball
    # fmt: on


def curves() -> dict[str, tuple[number, number, number, number]]:
    """
    Every `Easing` preset that IS a curve, spelled the way a scene writes it.

    `{"Easing.Out": (0.0, 0.0, 0.58, 1.0), ...}` — the four control points
    behind each named preset. A preset and a curve pulled by hand are the same
    `CubicBezier`, which is what lets the editor open its curve ON `Easing.Out`
    and drag away from it; read from the class rather than listed, so a preset
    added above reaches the editor with no second edit.

    The `Func` easings are absent on purpose: `Easing.Wiggle` is a function, and
    a function has no handles to show.
    """
    return {
        f"Easing.{name}": (curve.x1, curve.y1, curve.x2, curve.y2)
        for name, curve in vars(Easing).items()
        if isinstance(curve, CubicBezier)
    }


type easing = RateFunc


def animate(duration: sec, easing: easing, apply: Callable[[number, int], None]):
    # Same arrival rule as `rangeIdx`, for the same reason: `duration=0` is an
    # author asking for an instant change, not for silence, and the one frame it
    # gets carries the destination.
    n = max(1, int(duration * FRAMERATE))

    for i in range(n):
        t = i / (n - 1) if n > 1 else 1.0
        m = easing(t)
        apply(m, i)
