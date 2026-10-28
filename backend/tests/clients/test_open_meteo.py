from datetime import timedelta

import pytest
import requests
from django.core.cache.backends.locmem import LocMemCache

from routing.clients import open_meteo
from routing.clients.open_meteo import (
    OpenMeteoClient,
    WeatherError,
    cache_key,
    parse_forecast,
    snap,
)
from tests.clients.test_ors import make_response


class FakeSession:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append(params)
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


@pytest.fixture
def cache():
    store = LocMemCache("test-weather", {})
    yield store
    store.clear()


def location(load_fixture, index=0):
    return load_fixture("open_meteo_two_locations.json")[index]


def test_snap_to_tenth_degree():
    assert snap((32.7767, -96.797)) == (32.8, -96.8)
    assert cache_key(snap((32.7767, -96.797))) == "om:32.8:-96.8"


def test_parse_recorded_forecast(load_fixture):
    raw = location(load_fixture)
    forecast = parse_forecast(raw)
    assert forecast.hours == len(raw["hourly"]["time"])
    assert forecast.start.utcoffset() == timedelta(0)
    first = forecast.frame(0)
    assert first.wind_mph == raw["hourly"]["wind_speed_10m"][0]
    assert first.rain_in_hr == pytest.approx(raw["hourly"]["rain"][0] + raw["hourly"]["showers"][0])


def test_irregular_times_rejected(load_fixture):
    raw = location(load_fixture)
    raw["hourly"]["time"][1] += 60
    with pytest.raises(WeatherError):
        parse_forecast(raw)


def test_nearby_points_share_one_request_and_location(load_fixture, cache):
    session = FakeSession(make_response(200, [location(load_fixture), location(load_fixture, 1)]))
    client = OpenMeteoClient(cache, session=session)
    points = [(32.78, -96.80), (32.81, -96.79), (39.7, -105.0)]  # first two snap together
    result = client.forecasts(points)
    assert len(session.calls) == 1
    assert session.calls[0]["latitude"] == "32.8,39.7"
    assert session.calls[0]["wind_speed_unit"] == "mph"
    assert set(result) == set(points)
    assert result[points[0]] is result[points[1]]


def test_second_call_is_served_from_cache(load_fixture, cache):
    session = FakeSession(make_response(200, location(load_fixture)))  # single object form
    client = OpenMeteoClient(cache, session=session)
    client.forecasts([(32.8, -96.8)])
    client.forecasts([(32.79, -96.81)])
    assert len(session.calls) == 1


def test_large_batches_are_chunked(load_fixture, cache, monkeypatch):
    monkeypatch.setattr(open_meteo, "MAX_LOCATIONS_PER_REQUEST", 2)
    loc = location(load_fixture)
    session = FakeSession(make_response(200, [loc, loc]), make_response(200, [loc]))
    OpenMeteoClient(cache, session=session).forecasts([(30, -90), (31, -90), (32, -90)])
    assert [c["latitude"] for c in session.calls] == ["30.0,31.0", "32.0"]


@pytest.mark.parametrize(
    "response",
    [
        make_response(500, {"reason": "boom"}),
        make_response(200, []),  # wrong number of locations
        requests.Timeout("slow"),
    ],
)
def test_upstream_failures_raise_weather_error(response, cache):
    client = OpenMeteoClient(cache, session=FakeSession(response))
    with pytest.raises(WeatherError):
        client.forecasts([(30, -90)])


def test_malformed_location_raises_weather_error():
    with pytest.raises(WeatherError):
        parse_forecast({"latitude": 1})
