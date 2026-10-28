"""Grid of weather cells covering a buffered corridor around one or more route paths.

Cells sit on multiples of the grid step, which is itself a multiple of 0.1 degrees, so
cell centres line up with the weather client's cache grid and are shared across requests.
The step grows until the corridor fits in ``max_cells``, which bounds upstream API usage
(Open-Meteo counts every location as one call) regardless of trip length.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from .geometry import LatLon

STEP_OPTIONS_DEG = (0.1, 0.2, 0.25, 0.5, 1.0)
DEFAULT_BUFFER_DEG = 0.5  # ~35 mi either side of the route
DEFAULT_MAX_CELLS = 250


@dataclass(frozen=True)
class Grid:
    step_deg: float
    cells: tuple[LatLon, ...]  # sorted south-to-north, then west-to-east


def _densify(path: Sequence[LatLon], step: float) -> list[LatLon]:
    """Points along the path no more than ``step`` apart, so no cell is skipped."""
    if len(path) == 1:
        return list(path)
    points = []
    for (lat1, lon1), (lat2, lon2) in zip(path, path[1:]):
        n = max(1, math.ceil(max(abs(lat2 - lat1), abs(lon2 - lon1)) / step))
        points += [(lat1 + (lat2 - lat1) * k / n, lon1 + (lon2 - lon1) * k / n) for k in range(n)]
    points.append(path[-1])
    return points


def corridor_cells(
    paths: Sequence[Sequence[LatLon]], step: float, buffer_deg: float = DEFAULT_BUFFER_DEG
) -> list[LatLon]:
    """Cell centres within ``buffer_deg`` of any path (east-west buffer widened by latitude)."""
    marked: set[tuple[int, int]] = set()
    for path in paths:
        for lat, lon in _densify(path, step):
            row, col = round(lat / step), round(lon / step)
            reach_lat = buffer_deg / step
            reach_lon = reach_lat / max(math.cos(math.radians(lat)), 0.1)
            for dr in range(-math.ceil(reach_lat), math.ceil(reach_lat) + 1):
                for dc in range(-math.ceil(reach_lon), math.ceil(reach_lon) + 1):
                    if (dr / reach_lat) ** 2 + (dc / reach_lon) ** 2 <= 1:
                        marked.add((row + dr, col + dc))
    return [(round(r * step, 4), round(c * step, 4)) for r, c in sorted(marked)]


def build_corridor(
    paths: Sequence[Sequence[LatLon]],
    max_cells: int = DEFAULT_MAX_CELLS,
    buffer_deg: float = DEFAULT_BUFFER_DEG,
) -> Grid:
    """Finest grid whose corridor fits in ``max_cells`` (coarsest option as a last resort)."""
    paths = [p for p in paths if p]
    if not paths:
        raise ValueError("at least one non-empty path is required")
    cells: list[LatLon] = []
    for step in STEP_OPTIONS_DEG:
        cells = corridor_cells(paths, step, max(buffer_deg, step))
        if len(cells) <= max_cells:
            break
    return Grid(step, tuple(cells))
