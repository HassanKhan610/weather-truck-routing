"""Walking a route polyline to place checkpoints with interpolated ETAs.

Pure functions over plain data. The routing API gives us a polyline plus "steps" (each with
a duration and a vertex range). We spread each step's duration over its vertices by length,
which tells us how long the truck takes to reach any point on the line. Checkpoints are then
placed every N miles and their elapsed time is interpolated, so a checkpoint's ETA reflects
slow city streets vs. fast highway rather than assuming a constant speed.
"""

from __future__ import annotations

import math
from bisect import bisect_left
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

EARTH_RADIUS_MI = 3958.8

LatLon = tuple[float, float]


def haversine_mi(a: LatLon, b: LatLon) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(h))


@dataclass(frozen=True)
class Step:
    start_index: int  # vertex indices into RouteGeometry.coordinates (inclusive)
    end_index: int
    duration_s: float


@dataclass(frozen=True)
class RouteGeometry:
    coordinates: tuple[LatLon, ...]
    steps: tuple[Step, ...]
    distance_mi: float  # odometer distance reported by the routing API
    duration_s: float


@dataclass(frozen=True)
class Checkpoint:
    position_mi: float
    lat: float
    lon: float
    elapsed_s: float
    eta: datetime


def vertex_profile(route: RouteGeometry) -> tuple[list[float], list[float]]:
    """Cumulative miles and seconds at every vertex, scaled to the API's totals.

    Great-circle length of the polyline is slightly shorter than the odometer distance, so
    miles are rescaled to match ``distance_mi``; seconds are rescaled to ``duration_s`` so
    that steps the API reports with zero length (e.g. "arrive") can't lose time.
    """
    coords = route.coordinates
    edge_mi = [haversine_mi(a, b) for a, b in zip(coords, coords[1:])]
    edge_s = [0.0] * len(edge_mi)

    for step in route.steps:
        edges = range(step.start_index, min(step.end_index, len(edge_mi)))
        length = sum(edge_mi[i] for i in edges)
        for i in edges:
            edge_s[i] += step.duration_s * (edge_mi[i] / length) if length else 0.0

    if not any(edge_s):  # no usable steps: fall back to constant speed
        edge_s = list(edge_mi)

    cum_mi, cum_s = _cumulative(edge_mi), _cumulative(edge_s)
    return _rescale(cum_mi, route.distance_mi), _rescale(cum_s, route.duration_s)


def _cumulative(values: Sequence[float]) -> list[float]:
    out = [0.0]
    for v in values:
        out.append(out[-1] + v)
    return out


def _rescale(values: list[float], total: float) -> list[float]:
    if values[-1] <= 0:
        return values
    scaled = [v * total / values[-1] for v in values]
    scaled[-1] = total  # exact: float error must not push the destination past the route end
    return scaled


def checkpoint_positions(total_mi: float, interval_mi: float) -> list[float]:
    """0, interval, 2*interval, ... and always the destination itself."""
    if interval_mi <= 0:
        raise ValueError("interval must be positive")
    count = math.floor(total_mi / interval_mi + 1e-9)
    positions = [i * interval_mi for i in range(count + 1)]
    if total_mi - positions[-1] > 1e-6:
        positions.append(total_mi)
    return positions


def _interpolate(xs: Sequence[float], x: float) -> tuple[int, float]:
    """Index of the edge containing x and the fraction along it."""
    i = min(max(bisect_left(xs, x), 1), len(xs) - 1)
    span = xs[i] - xs[i - 1]
    return i - 1, (x - xs[i - 1]) / span if span else 0.0


def generate_checkpoints(
    route: RouteGeometry, interval_mi: float, departure: datetime
) -> list[Checkpoint]:
    if len(route.coordinates) < 2:
        raise ValueError("route needs at least two coordinates")
    cum_mi, cum_s = vertex_profile(route)
    checkpoints = []
    for position in checkpoint_positions(cum_mi[-1], interval_mi):
        i, t = _interpolate(cum_mi, position)
        (lat1, lon1), (lat2, lon2) = route.coordinates[i], route.coordinates[i + 1]
        elapsed = cum_s[i] + t * (cum_s[i + 1] - cum_s[i])
        checkpoints.append(
            Checkpoint(
                position_mi=position,
                lat=lat1 + t * (lat2 - lat1),
                lon=lon1 + t * (lon2 - lon1),
                elapsed_s=elapsed,
                eta=departure + timedelta(seconds=elapsed),
            )
        )
    return checkpoints


def detour_point(origin: LatLon, destination: LatLon, side: int, fraction: float) -> LatLon:
    """Point offset perpendicular from the midpoint by ``fraction`` of the trip length.

    ``side`` is +1 (left of travel) or -1 (right). Used to force genuinely different
    alternatives when the routing API can't provide them. Flat-earth math is fine here:
    the point is only a hint that the router snaps to the nearest road.
    """
    (lat1, lon1), (lat2, lon2) = origin, destination
    mid_lat, mid_lon = (lat1 + lat2) / 2, (lon1 + lon2) / 2
    scale = math.cos(math.radians(mid_lat))
    dx, dy = (lon2 - lon1) * scale, lat2 - lat1  # dx in "latitude degrees"
    return (mid_lat + side * dx * fraction, mid_lon - side * dy * fraction / scale)


def similar(a: RouteGeometry, b: RouteGeometry, tolerance: float = 0.02) -> bool:
    """Routes within ``tolerance`` on both distance and duration are treated as duplicates."""

    def close(x: float, y: float) -> bool:
        return abs(x - y) <= tolerance * max(x, y, 1e-9)

    return close(a.distance_mi, b.distance_mi) and close(a.duration_s, b.duration_s)
