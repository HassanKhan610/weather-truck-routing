"""Distance-weighted route scoring and lexicographic ranking.

Each checkpoint represents the stretch of road between the midpoints to its neighbours
(the first starts at mile 0, the last ends at the destination). "Severe miles" is therefore
a length of road, not a count of checkpoints, so it doesn't depend on the sampling interval.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .risk import RiskLevel

# Float noise must not decide a ranking: compare miles to 0.1 mi and average risk to 0.001.
MILES_PRECISION = 1
AVERAGE_PRECISION = 3


def segment_lengths(positions_mi: Sequence[float], total_mi: float) -> list[float]:
    """Length of road each checkpoint represents. Positions must be ascending within [0, total]."""
    if not positions_mi:
        return []
    if any(b < a for a, b in zip(positions_mi, positions_mi[1:])):
        raise ValueError("checkpoint positions must be ascending")
    if positions_mi[0] < 0 or positions_mi[-1] > total_mi:
        raise ValueError("checkpoint positions must lie within the route")

    edges = [0.0]
    edges += [(a + b) / 2 for a, b in zip(positions_mi, positions_mi[1:])]
    edges.append(total_mi)
    return [end - start for start, end in zip(edges, edges[1:])]


@dataclass(frozen=True)
class ScoredCheckpoint:
    position_mi: float
    level: RiskLevel | None  # None when the forecast doesn't cover the ETA


@dataclass(frozen=True)
class RouteScore:
    route_id: str
    duration_s: float
    distance_mi: float
    severe_miles: float  # Severe *or worse* (No Travel counts here too)
    high_miles: float
    no_travel_miles: float
    unknown_miles: float
    average_risk: float | None  # mile-weighted mean of RiskLevel values over known miles

    @property
    def has_no_travel(self) -> bool:
        return self.no_travel_miles > 0

    def sort_key(self) -> tuple:
        """Spec priority, with any No Travel route forced last."""
        return (
            self.has_no_travel,
            round(self.severe_miles, MILES_PRECISION),
            round(self.high_miles, MILES_PRECISION),
            round(self.average_risk if self.average_risk is not None else 0.0, AVERAGE_PRECISION),
            self.duration_s,
        )


def score_route(
    route_id: str,
    checkpoints: Sequence[ScoredCheckpoint],
    distance_mi: float,
    duration_s: float,
) -> RouteScore:
    lengths = segment_lengths([c.position_mi for c in checkpoints], distance_mi)
    severe = high = no_travel = unknown = weighted = 0.0
    for checkpoint, miles in zip(checkpoints, lengths):
        level = checkpoint.level
        if level is None:
            unknown += miles
            continue
        weighted += int(level) * miles
        if level >= RiskLevel.SEVERE:
            severe += miles
        if level == RiskLevel.NO_TRAVEL:
            no_travel += miles
        if level == RiskLevel.HIGH:
            high += miles

    known = sum(lengths) - unknown
    return RouteScore(
        route_id=route_id,
        duration_s=duration_s,
        distance_mi=distance_mi,
        severe_miles=severe,
        high_miles=high,
        no_travel_miles=no_travel,
        unknown_miles=unknown,
        average_risk=weighted / known if known > 0 else None,
    )


def rank(scores: Sequence[RouteScore]) -> list[RouteScore]:
    """Best first. ``sorted`` is stable, so exact ties keep the routing API's order."""
    return sorted(scores, key=RouteScore.sort_key)


def _hours(seconds: float) -> str:
    minutes = round(seconds / 60)
    return f"{minutes // 60}h {minutes % 60:02d}m"


def explain(ranked: Sequence[RouteScore]) -> str:
    """One-sentence reason the first route beats the runner-up, naming the deciding criterion."""
    if not ranked:
        return "No routes to compare."
    best = ranked[0]
    if best.has_no_travel:
        return "Every route crosses a No Travel checkpoint; delay the trip or change the load."
    if len(ranked) == 1:
        return "Only one route was available."

    other = ranked[1]
    a, b = best.sort_key(), other.sort_key()
    if a[0] != b[0]:
        return f"Recommended because {other.route_id} crosses a No Travel checkpoint."
    if a[1] != b[1]:
        return (
            f"Fewest Severe-or-worse miles: {best.severe_miles:.1f} mi vs "
            f"{other.severe_miles:.1f} mi on {other.route_id}."
        )
    if a[2] != b[2]:
        return (
            f"Same Severe exposure, fewer High-risk miles: {best.high_miles:.1f} mi vs "
            f"{other.high_miles:.1f} mi on {other.route_id}."
        )
    if a[3] != b[3]:
        return (
            f"Same Severe and High exposure, lower average risk: {a[3]:.2f} vs {b[3]:.2f} "
            f"on {other.route_id}."
        )
    if a[4] != b[4]:
        return (
            f"Weather risk is equivalent, so the faster route wins: {_hours(best.duration_s)} vs "
            f"{_hours(other.duration_s)} on {other.route_id}."
        )
    return f"Equivalent to {other.route_id} on every criterion; kept the routing API's order."
