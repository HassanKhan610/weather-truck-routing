from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from routing import views
from routing.clients.ors import Place, RoutingError
from tests.services.test_analysis import FakeRouting, FakeWeather, line, with_distance


@pytest.fixture
def fakes(monkeypatch):
    routing = FakeRouting([with_distance(line(0.5, 2), 100)])
    routing.autocomplete = lambda q: [Place("Dallas, TX, USA", 32.8, -96.8)]
    monkeypatch.setattr(views, "routing_client", lambda: routing)
    monkeypatch.setattr(
        views,
        "weather_client",
        lambda: FakeWeather(hours=24 * 7, start=timezone.now() - timedelta(hours=1)),
    )
    return routing


def body(**overrides):
    data = {
        "origin": "Dallas",
        "destination": {"label": "Waco", "lat": 1.0, "lon": 0.0},
        "departure": (timezone.now() + timedelta(minutes=5)).isoformat(),
        "load_lb": 35000,
        "interval_mi": 25,
    }
    return {**data, **overrides}


def post(data):
    return APIClient().post("/api/analyze/", data, format="json")


def test_analyze_happy_path(fakes):
    response = post(body())
    assert response.status_code == 200
    data = response.json()
    assert data["recommended_route_id"] == "Route A"
    assert data["interval_mi"] == 25
    assert data["destination"]["label"] == "Waco"
    assert fakes.geocoded == ["Dallas"]


@pytest.mark.parametrize(
    "overrides, field",
    [
        ({"interval_mi": 30}, "interval_mi"),
        ({"load_lb": -1}, "load_lb"),
        ({"load_lb": 200_000}, "load_lb"),
        ({"origin": ""}, "origin"),
        ({"origin": {"lat": 100, "lon": 0}}, "origin"),
        ({"departure": "2020-01-01T00:00:00Z"}, "departure"),
        ({"departure": (timezone.now() + timedelta(days=6)).isoformat()}, "departure"),
    ],
)
def test_analyze_validation(fakes, overrides, field):
    response = post(body(**overrides))
    assert response.status_code == 400
    assert field in response.json()


def test_upstream_errors_map_to_their_status(fakes, monkeypatch):
    def fail(*args, **kwargs):
        raise RoutingError("Couldn't find a location for 'Atlantis'.")

    monkeypatch.setattr(fakes, "geocode", fail)
    response = post(body())
    assert response.status_code == 422
    assert "Atlantis" in response.json()["detail"]


def test_missing_key_returns_503(monkeypatch, settings):
    settings.ORS_API_KEY = ""
    response = post(body())
    assert response.status_code == 503


def test_geocode_autocomplete(fakes):
    response = APIClient().get("/api/geocode/", {"q": "Dall"})
    assert response.json() == {"results": [{"label": "Dallas, TX, USA", "lat": 32.8, "lon": -96.8}]}


def test_geocode_ignores_short_queries(fakes):
    assert APIClient().get("/api/geocode/", {"q": "Da"}).json() == {"results": []}
