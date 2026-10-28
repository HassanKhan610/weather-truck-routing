"""Open-Meteo client: batched hourly forecasts for many points with a short TTL cache.

Points are snapped to a 0.1° grid (~7 mi), which is close to the forecast model's own
resolution. Nearby checkpoints then share one forecast, every cache key is stable across
requests, and a whole analysis costs one request per ``MAX_LOCATIONS_PER_REQUEST`` points.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any, Protocol

import requests

from routing.domain.forecast import HourlyForecast
from routing.domain.geometry import LatLon

logger = logging.getLogger(__name__)

GRID_DEGREES = 0.1
MAX_LOCATIONS_PER_REQUEST = 100  # keeps the query string comfortably short
FORECAST_DAYS = 7
HOURLY_VARIABLES = "wind_speed_10m,rain,showers,snowfall"


class WeatherError(Exception):
    status = 502


class Cache(Protocol):
    def get_many(self, keys: Iterable[str]) -> dict[str, Any]: ...

    def set_many(self, data: dict[str, Any], timeout: int | None = ...) -> Any: ...


def snap(point: LatLon) -> LatLon:
    lat, lon = point
    return (
        round(round(lat / GRID_DEGREES) * GRID_DEGREES, 1),
        round(round(lon / GRID_DEGREES) * GRID_DEGREES, 1),
    )


def cache_key(point: LatLon) -> str:
    return "om:{:.1f}:{:.1f}".format(*point)


def _sum(a: float | None, b: float | None) -> float | None:
    return None if a is None or b is None else a + b


def parse_forecast(location: dict[str, Any]) -> HourlyForecast:
    """One Open-Meteo location (``timeformat=unixtime``) -> HourlyForecast.

    Rain risk uses rain + showers (both liquid, inches over the preceding hour, i.e. in/hr).
    Snowfall is already in inches when ``precipitation_unit=inch``.
    """
    try:
        hourly = location["hourly"]
        times = hourly["time"]
        wind, rain, showers, snow = (
            hourly[k] for k in ("wind_speed_10m", "rain", "showers", "snowfall")
        )
    except (KeyError, TypeError) as exc:
        raise WeatherError("Weather service returned an unexpected response.") from exc
    if not times or any(b - a != 3600 for a, b in zip(times, times[1:])):
        raise WeatherError("Weather service returned irregular hourly data.")
    return HourlyForecast(
        start=datetime.fromtimestamp(times[0], tz=timezone.utc),
        wind_mph=tuple(wind),
        rain_in_hr=tuple(_sum(r, s) for r, s in zip(rain, showers)),
        snow_in_hr=tuple(snow),
    )


class OpenMeteoClient:
    def __init__(
        self,
        cache: Cache,
        base_url: str = "https://api.open-meteo.com",
        ttl_seconds: int = 600,
        timeout: float = 15,
        session: requests.Session | None = None,
    ):
        self.cache = cache
        self.base_url = base_url.rstrip("/")
        self.ttl = ttl_seconds
        self.timeout = timeout
        self.session = session or requests.Session()

    def forecasts(self, points: Iterable[LatLon]) -> dict[LatLon, HourlyForecast]:
        """Forecast for each requested point (nearby points share one snapped forecast)."""
        points = list(points)
        snapped = list(dict.fromkeys(snap(p) for p in points))
        cached = self.cache.get_many([cache_key(p) for p in snapped])
        by_cell = {p: cached[cache_key(p)] for p in snapped if cache_key(p) in cached}

        missing = [p for p in snapped if p not in by_cell]
        for start in range(0, len(missing), MAX_LOCATIONS_PER_REQUEST):
            chunk = missing[start : start + MAX_LOCATIONS_PER_REQUEST]
            fetched = dict(zip(chunk, self._fetch(chunk)))
            self.cache.set_many({cache_key(p): f for p, f in fetched.items()}, self.ttl)
            by_cell.update(fetched)
        return {p: by_cell[snap(p)] for p in points}

    def _fetch(self, points: list[LatLon]) -> list[HourlyForecast]:
        params = {
            "latitude": ",".join(f"{lat:.1f}" for lat, _ in points),
            "longitude": ",".join(f"{lon:.1f}" for _, lon in points),
            "hourly": HOURLY_VARIABLES,
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timeformat": "unixtime",
            "timezone": "GMT",
            "forecast_days": FORECAST_DAYS,
        }
        try:
            response = self.session.get(
                f"{self.base_url}/v1/forecast", params=params, timeout=self.timeout
            )
        except requests.RequestException as exc:
            raise WeatherError("Weather service is unreachable. Please try again.") from exc
        if not response.ok:
            logger.warning("Open-Meteo %s: %s", response.status_code, response.text[:200])
            raise WeatherError("Weather service returned an error.")

        payload = response.json()
        locations = payload if isinstance(payload, list) else [payload]
        if len(locations) != len(points):
            raise WeatherError("Weather service returned an unexpected number of locations.")
        return [parse_forecast(location) for location in locations]
