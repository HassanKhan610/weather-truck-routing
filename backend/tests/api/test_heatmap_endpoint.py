from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from routing import views
from routing.clients.open_meteo import WeatherError
from routing.domain.forecast import HourlyForecast


class FlatWeather:
    def forecasts(self, points):
        start = timezone.now().replace(minute=0, second=0, microsecond=0)
        series = HourlyForecast(start, (30.0,) * 72, (0.0,) * 72, (0.0,) * 72)
        return {p: series for p in points}


@pytest.fixture
def weather(monkeypatch):
    monkeypatch.setattr(views, "weather_client", FlatWeather)


def body(**overrides):
    data = {
        "paths": [[[32.8, -96.8], [33.0, -97.0]], [[32.8, -96.8], [32.9, -97.1]]],
        "start": (timezone.now() + timedelta(minutes=5)).isoformat(),
        "load_lb": 20000,
    }
    return {**data, **overrides}


def post(data, **headers):
    return APIClient().post("/api/heatmap/", data, format="json", **headers)


def test_heatmap_happy_path(weather):
    response = post(body())
    assert response.status_code == 200
    data = response.json()
    assert len(data["frames"]) == 49
    assert data["frames"][0][0] == 1.5


def test_heatmap_is_gzipped_when_accepted(weather):
    response = post(body(), HTTP_ACCEPT_ENCODING="gzip")
    assert response["Content-Encoding"] == "gzip"


@pytest.mark.parametrize(
    "overrides",
    [
        {"paths": []},
        {"paths": [[[100, 0]]]},
        {"paths": [[[1, 2, 3]]]},
        {"paths": [[[1, 2]]] * 4},
        {"load_lb": -5},
        {"start": "2020-01-01T00:00:00Z"},
    ],
)
def test_heatmap_validation(weather, overrides):
    assert post(body(**overrides)).status_code == 400


def test_heatmap_weather_failure_returns_502(monkeypatch):
    class Down:
        def forecasts(self, points):
            raise WeatherError("down")

    monkeypatch.setattr(views, "weather_client", Down)
    assert post(body()).status_code == 502
