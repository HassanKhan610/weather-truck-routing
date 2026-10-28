"""Per-checkpoint weather risk classification.

Pure Python, no framework imports. The rules from the spec are expressed as data:

* ``THRESHOLDS`` maps each weather factor to an ascending table of band boundaries.
* ``LOAD_RULES`` is a list of small functions that can only *raise* a checkpoint's level
  based on wind and load weight.

A checkpoint's level is the maximum over all factors after load rules are applied.
Boundary interpretation is documented in the README (ASSUMPTIONS) and pinned by tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Callable, Optional


class RiskLevel(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").title()


@dataclass(frozen=True)
class Boundary:
    """A value at or above ``value`` (or strictly above, if not ``inclusive``) is ``level``."""

    value: float
    level: RiskLevel
    inclusive: bool = True

    def reached_by(self, measurement: float) -> bool:
        return measurement >= self.value if self.inclusive else measurement > self.value


# Lower-inclusive bands, except where the spec explicitly says ">" (rain and snow No Travel).
THRESHOLDS: dict[str, tuple[Boundary, ...]] = {
    "wind_mph": (
        Boundary(25, RiskLevel.MODERATE),
        Boundary(35, RiskLevel.HIGH),
        Boundary(45, RiskLevel.SEVERE),
        Boundary(55, RiskLevel.NO_TRAVEL),
    ),
    "rain_in_hr": (
        Boundary(0.10, RiskLevel.MODERATE),
        Boundary(0.25, RiskLevel.HIGH),
        Boundary(0.50, RiskLevel.SEVERE),
        Boundary(1.00, RiskLevel.NO_TRAVEL, inclusive=False),
    ),
    "snow_in_hr": (
        Boundary(0.5, RiskLevel.MODERATE),
        Boundary(1.0, RiskLevel.HIGH),
        Boundary(2.0, RiskLevel.SEVERE),
        Boundary(3.0, RiskLevel.NO_TRAVEL, inclusive=False),
    ),
}

FACTOR_LABELS = {"wind_mph": "wind", "rain_in_hr": "rain", "snow_in_hr": "snow"}


@dataclass(frozen=True)
class Weather:
    wind_mph: float
    rain_in_hr: float
    snow_in_hr: float


def classify(factor: str, value: float) -> RiskLevel:
    """Highest band whose boundary the value reaches; LOW if none."""
    level = RiskLevel.LOW
    for boundary in THRESHOLDS[factor]:
        if boundary.reached_by(value):
            level = boundary.level
    return level


# A load rule returns the minimum level it imposes, or None when it doesn't apply.
LoadRule = Callable[[Weather, float], Optional[RiskLevel]]


def _rule(min_wind: float, max_wind: float | None, over_lb: float, level: RiskLevel) -> LoadRule:
    def apply(weather: Weather, load_lb: float) -> RiskLevel | None:
        in_band = weather.wind_mph >= min_wind and (max_wind is None or weather.wind_mph < max_wind)
        return level if in_band and load_lb > over_lb else None

    apply.__doc__ = f"wind {min_wind}-{max_wind} mph with load > {over_lb:,.0f} lb -> {level.label}"
    return apply


LOAD_RULES: tuple[LoadRule, ...] = (
    _rule(55, None, 0, RiskLevel.NO_TRAVEL),  # any load (an empty truck still has weight > 0)
    _rule(45, 55, 30_000, RiskLevel.NO_TRAVEL),
    _rule(35, 45, 40_000, RiskLevel.SEVERE),
)


@dataclass(frozen=True)
class Assessment:
    level: RiskLevel
    reasons: tuple[str, ...]  # human-readable drivers of the final level


def assess(weather: Weather, load_lb: float) -> Assessment:
    """Classify each factor, apply load rules, and keep whichever reasons reach the max level."""
    candidates: list[tuple[RiskLevel, str]] = []
    for factor, label in FACTOR_LABELS.items():
        value = getattr(weather, factor)
        unit = "mph" if factor == "wind_mph" else "in/hr"
        candidates.append((classify(factor, value), f"{label} {value:g} {unit}"))

    for rule in LOAD_RULES:
        imposed = rule(weather, load_lb)
        if imposed is not None:
            candidates.append(
                (imposed, f"wind {weather.wind_mph:g} mph with {load_lb:,.0f} lb load")
            )

    level = max(level for level, _ in candidates)
    if level == RiskLevel.LOW:
        return Assessment(level, ())
    reasons = tuple(dict.fromkeys(reason for lvl, reason in candidates if lvl == level))
    return Assessment(level, reasons)


def _band_position(value: float, boundaries: tuple[Boundary, ...]) -> float:
    """Level of the band ``value`` is in, plus how far through that band it is (0..1)."""
    edges = [0.0] + [b.value for b in boundaries]
    if value >= edges[-1]:
        return float(RiskLevel.NO_TRAVEL)
    for level, (low, high) in enumerate(zip(edges, edges[1:])):
        if value < high:
            return level + max(0.0, value - low) / (high - low)
    return float(RiskLevel.NO_TRAVEL)  # unreachable; keeps type checkers happy


def risk_index(weather: Weather, load_lb: float) -> float:
    """Continuous 0-4 risk used to shade the heatmap.

    ``floor(risk_index(w, load)) == assess(w, load).level`` always holds, so the heatmap
    can never disagree with the checkpoint colours; the fraction only adds smooth shading.
    """
    level = assess(weather, load_lb).level
    position = max(_band_position(getattr(weather, f), b) for f, b in THRESHOLDS.items())
    if level == RiskLevel.NO_TRAVEL:
        return float(RiskLevel.NO_TRAVEL)
    return min(max(position, float(level)), level + 0.99)
