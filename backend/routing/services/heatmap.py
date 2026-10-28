"""Use case: hourly risk frames over the trip corridor for the heatmap slider.

All 49 frames (hours 0-48) are returned at once in a columnar layout (cell coordinates
once, then one flat value array per hour), so the client can switch frames without
refetching and the JSON stays small.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta

from routing.domain.corridor import build_corridor
from routing.domain.geometry import LatLon
from routing.domain.risk import risk_index
from routing.services.analysis import WeatherClient

HOURS = 48
VALUE_DECIMALS = 2


def build_heatmap(
    paths: Sequence[Sequence[LatLon]], start: datetime, load_lb: float, weather: WeatherClient
) -> dict:
    grid = build_corridor(paths)
    first_hour = start.replace(minute=0, second=0, microsecond=0)
    forecasts = weather.forecasts(list(grid.cells))

    frames = []
    for hour in range(HOURS + 1):
        when = first_hour + timedelta(hours=hour)
        frame = []
        for cell in grid.cells:
            sample = forecasts[cell].at(when)
            frame.append(
                None if sample is None else round(risk_index(sample, load_lb), VALUE_DECIMALS)
            )
        frames.append(frame)

    return {
        "start": first_hour.isoformat(),
        "hours": HOURS,
        "step_deg": grid.step_deg,
        "lat": [lat for lat, _ in grid.cells],
        "lon": [lon for _, lon in grid.cells],
        "frames": frames,
        "value_range": [0, 4],
    }
