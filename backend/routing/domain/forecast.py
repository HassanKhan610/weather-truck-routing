"""Hourly forecast series and lookup at an arbitrary ETA.

Values between hourly stamps are linearly interpolated. An ETA outside the series, or next
to a missing (null) value, returns None: "forecast unavailable" is reported explicitly
rather than silently scored as Low.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from .risk import Weather

HOUR = timedelta(hours=1)


@dataclass(frozen=True)
class HourlyForecast:
    start: datetime  # timezone-aware time of index 0; samples are exactly one hour apart
    wind_mph: tuple[float | None, ...]
    rain_in_hr: tuple[float | None, ...]
    snow_in_hr: tuple[float | None, ...]

    def __post_init__(self) -> None:
        if not (len(self.wind_mph) == len(self.rain_in_hr) == len(self.snow_in_hr)):
            raise ValueError("hourly series must have equal lengths")
        if self.start.tzinfo is None:
            raise ValueError("start must be timezone-aware")

    @property
    def hours(self) -> int:
        return len(self.wind_mph)

    @property
    def end(self) -> datetime:
        return self.start + (self.hours - 1) * HOUR

    def at(self, when: datetime) -> Weather | None:
        offset = (when - self.start) / HOUR
        if self.hours == 0 or offset < 0 or offset > self.hours - 1:
            return None
        i = min(math.floor(offset), self.hours - 2) if self.hours > 1 else 0
        t = offset - i
        values = []
        for series in (self.wind_mph, self.rain_in_hr, self.snow_in_hr):
            a = series[i]
            b = series[i + 1] if t > 0 else a
            if a is None or b is None:
                return None
            values.append(a + t * (b - a))
        return Weather(*values)

    def frame(self, hour: int) -> Weather | None:
        """Exact values at ``start + hour`` hours (used by the heatmap)."""
        return self.at(self.start + hour * HOUR) if 0 <= hour < self.hours else None
