from datetime import datetime, timedelta, timezone

import pytest

from routing.clients.ors import Place, RoutingError
from routing.domain.forecast import HourlyForecast
from routing.domain.geometry import RouteGeometry, Step
from routing.services.analysis import TripRequest, analyze_trip

DEPART = datetime(2026, 11, 2, 6, 0, tzinfo=timezone.utc)
ORIGIN = Place("Origin", 0.0, 0.0)
DEST = Place("Destination", 1.0, 0.0)


def line(lon, duration_h):
    """Straight ~69 mi route north from the equator, offset east by ``lon``."""
    coords = ((0.0, 0.0), (0.0, lon), (1.0, lon), (1.0, 0.0))
    return RouteGeometry(coords, (Step(0, 3, duration_h * 3600),), 0, duration_h * 3600)


def with_distance(route, miles):
    return RouteGeometry(route.coordinates, route.steps, miles, route.duration_s)


class FakeRouting:
    def __init__(self, routes):
        self._routes = routes
        self.geocoded = []

    def geocode(self, text):
        self.geocoded.append(text)
        return {"Dallas": ORIGIN, "Waco": DEST}[text]

    def routes(self, origin, destination, count=3):
        return self._routes


class FakeWeather:
    """Same forecast everywhere, except a stormy band east of ``storm_lon``."""

    def __init__(self, calm=10, storm=40, storm_lon=None, hours=48, start=None):
        self.calls = 0
        self.make = lambda wind: HourlyForecast(
            start or DEPART - timedelta(hours=1), (wind,) * hours, (0.0,) * hours, (0.0,) * hours
        )
        self.calm, self.storm, self.storm_lon = calm, storm, storm_lon

    def forecasts(self, points):
        self.calls += 1
        return {
            p: self.make(
                self.storm if self.storm_lon is not None and p[1] >= self.storm_lon else self.calm
            )
            for p in points
        }


def trip(load=20_000, interval=10, origin="Dallas", destination="Waco"):
    return TripRequest(origin, destination, DEPART, load, interval)


def test_safer_route_is_recommended_over_faster_one():
    fast_stormy = with_distance(line(0.5, 3), 130)
    slow_calm = with_distance(line(-0.5, 4), 140)
    weather = FakeWeather(storm_lon=0.4)
    result = analyze_trip(trip(), FakeRouting([fast_stormy, slow_calm]), weather)

    assert result["recommended_route_id"] == "Route B"
    assert [r["id"] for r in result["routes"]] == ["Route B", "Route A"]
    assert [r["rank"] for r in result["routes"]] == [1, 2]
    assert result["routes"][0]["recommended"] is True
    assert result["routes"][1]["score"]["high_miles"] > 0
    assert "High-risk miles" in result["explanation"]
    assert weather.calls == 1  # all routes' checkpoints in one batch


def test_heavy_load_escalates_risk():
    route = with_distance(line(0.5, 3), 100)
    weather = FakeWeather(calm=40)
    light = analyze_trip(trip(load=20_000), FakeRouting([route]), weather)
    heavy = analyze_trip(trip(load=45_000), FakeRouting([route]), weather)
    assert light["routes"][0]["worst_level"] == 2  # High
    assert heavy["routes"][0]["worst_level"] == 3  # Severe
    assert heavy["routes"][0]["checkpoints"][0]["reasons"] == ["wind 40 mph with 45,000 lb load"]


def test_no_travel_everywhere_means_no_recommendation():
    result = analyze_trip(trip(), FakeRouting([with_distance(line(0.5, 3), 100)]), FakeWeather(60))
    assert result["recommended_route_id"] is None
    assert result["routes"][0]["recommended"] is False
    assert "No Travel" in result["explanation"]


def test_checkpoints_beyond_forecast_are_marked_unavailable():
    long_trip = with_distance(line(0.5, 10), 100)  # forecast covers only ~4h of it
    result = analyze_trip(trip(), FakeRouting([long_trip]), FakeWeather(hours=5))
    checkpoints = result["routes"][0]["checkpoints"]
    assert checkpoints[0]["level"] == 0
    assert checkpoints[-1]["level"] is None
    assert checkpoints[-1]["level_label"] == "Forecast unavailable"
    assert result["routes"][0]["score"]["unknown_miles"] > 0


def test_checkpoint_payload_shape_and_eta():
    route = with_distance(line(0.5, 2), 100)
    result = analyze_trip(trip(interval=50), FakeRouting([route]), FakeWeather())
    cps = result["routes"][0]["checkpoints"]
    assert [c["position_mi"] for c in cps] == [0, 50, 100]
    assert cps[1]["eta"] == (DEPART + timedelta(hours=1)).isoformat()
    assert set(cps[1]) == {
        "position_mi",
        "lat",
        "lon",
        "eta",
        "weather",
        "level",
        "level_label",
        "reasons",
    }
    assert result["routes"][0]["arrival"] == (DEPART + timedelta(hours=2)).isoformat()


def test_place_objects_skip_geocoding():
    routing = FakeRouting([with_distance(line(0.5, 1), 50)])
    analyze_trip(trip(origin=ORIGIN, destination=DEST), routing, FakeWeather())
    assert routing.geocoded == []


def test_routing_errors_propagate():
    class Failing(FakeRouting):
        def routes(self, *args, **kwargs):
            raise RoutingError("No truck route found")

    with pytest.raises(RoutingError):
        analyze_trip(trip(), Failing([]), FakeWeather())
