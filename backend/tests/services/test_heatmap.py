from datetime import datetime, timezone

from routing.domain.forecast import HourlyForecast
from routing.services.heatmap import HOURS, build_heatmap

START = datetime(2026, 11, 2, 6, 40, tzinfo=timezone.utc)
PATH = [(30.0, -90.0), (30.5, -90.0)]


class RampWeather:
    """Wind rises 1 mph per hour everywhere; the forecast covers ``hours`` hours."""

    def __init__(self, hours=72):
        self.hours = hours
        self.requested = None

    def forecasts(self, points):
        self.requested = points
        n = self.hours
        base = START.replace(minute=0)
        series = HourlyForecast(base, tuple(float(h) for h in range(n)), (0.0,) * n, (0.0,) * n)
        return {p: series for p in points}


def test_payload_is_columnar_with_one_frame_per_hour():
    weather = RampWeather()
    result = build_heatmap([PATH], START, 0, weather)
    assert result["hours"] == HOURS
    assert len(result["frames"]) == HOURS + 1
    assert len(result["lat"]) == len(result["lon"]) == len(weather.requested)
    assert all(len(frame) == len(result["lat"]) for frame in result["frames"])


def test_frames_start_on_the_hour_and_advance_hourly():
    result = build_heatmap([PATH], START, 0, RampWeather())
    assert result["start"] == "2026-11-02T06:00:00+00:00"
    assert result["frames"][0][0] == 0.0  # 0 mph
    assert result["frames"][25][0] == 1.0  # 25 mph -> start of Moderate
    assert result["frames"][40][0] == 2.5  # 40 mph -> halfway through High


def test_load_changes_shading():
    light = build_heatmap([PATH], START, 0, RampWeather())
    heavy = build_heatmap([PATH], START, 45_000, RampWeather())
    assert light["frames"][36][0] < 3 <= heavy["frames"][36][0]


def test_hours_beyond_forecast_are_null():
    result = build_heatmap([PATH], START, 0, RampWeather(hours=10))
    assert result["frames"][9][0] is not None
    assert result["frames"][10][0] is None


def test_start_is_floored_not_rounded():
    late = START.replace(minute=59)
    assert build_heatmap([PATH], late, 0, RampWeather())["start"].startswith("2026-11-02T06:00")
