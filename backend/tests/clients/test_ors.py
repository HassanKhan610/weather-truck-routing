import json

import pytest
import requests

from routing.clients.ors import (
    OrsClient,
    Place,
    RoutingError,
    parse_directions,
    parse_places,
)

DALLAS = Place("Dallas", 32.78, -96.80)
WACO = Place("Waco", 31.55, -97.15)


def make_response(status=200, payload=None):
    response = requests.Response()
    response.status_code = status
    response._content = json.dumps(payload or {}).encode()
    return response


def ors_error(code, message="nope"):
    return {"error": {"code": code, "message": message}}


class FakeSession:
    """Returns queued responses in order and records each request."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []
        self.headers = {}

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def client(*responses):
    session = FakeSession(*responses)
    return OrsClient("key", session=session), session


def single_route(load_fixture, index=0):
    payload = load_fixture("ors_directions_alternatives.json")
    payload["features"] = [payload["features"][index]]
    return payload


# --- parsing -------------------------------------------------------------------------


def test_parse_directions_converts_lonlat_and_collects_steps(load_fixture):
    routes = parse_directions(load_fixture("ors_directions_alternatives.json"))
    assert len(routes) == 2
    first = routes[0]
    assert first.coordinates[0] == (32.78, -96.80)
    assert (first.distance_mi, first.duration_s) == (90.0, 5400.0)
    assert [(s.start_index, s.end_index) for s in first.steps] == [(0, 2), (2, 5), (5, 5)]


def test_parse_directions_merges_steps_across_via_segments():
    payload = {
        "features": [
            {
                "geometry": {"coordinates": [[0, 0], [0, 1], [0, 2]]},
                "properties": {
                    "summary": {"distance": 2, "duration": 20},
                    "segments": [
                        {"steps": [{"way_points": [0, 1], "duration": 10}]},
                        {"steps": [{"way_points": [1, 2], "duration": 10}]},
                    ],
                },
            }
        ]
    }
    assert len(parse_directions(payload)[0].steps) == 2


def test_parse_places(load_fixture):
    places = parse_places(load_fixture("ors_geocode.json"))
    assert places[0] == Place("Dallas, TX, USA", 32.7767, -96.7970)


# --- client behaviour ----------------------------------------------------------------


def test_missing_key_is_a_clear_error():
    with pytest.raises(RoutingError, match="ORS_API_KEY"):
        OrsClient("")


def test_api_key_sent_as_header():
    _, session = client()
    assert session.headers["Authorization"] == "key"


def test_geocode_returns_best_match(load_fixture):
    ors, session = client(make_response(200, load_fixture("ors_geocode.json")))
    assert ors.geocode("Dallas").label == "Dallas, TX, USA"
    method, url, kwargs = session.calls[0]
    assert url.endswith("/geocode/search") and kwargs["params"]["size"] == 1


def test_geocode_with_no_match_raises():
    ors, _ = client(make_response(200, {"features": []}))
    with pytest.raises(RoutingError, match="Couldn't find"):
        ors.geocode("zzzz")


def test_native_alternatives_used_when_available(load_fixture):
    payload = load_fixture("ors_directions_alternatives.json")
    ors, session = client(
        make_response(200, payload), make_response(200, single_route(load_fixture))
    )
    routes = ors.routes(DALLAS, WACO, count=2)
    assert len(routes) == 2
    assert len(session.calls) == 1
    body = session.calls[0][2]["json"]
    assert body["alternative_routes"]["target_count"] == 2
    assert body["coordinates"][0] == [-96.80, 32.78]  # ORS wants lon,lat
    assert session.calls[0][1].endswith("/driving-hgv/geojson")


def test_long_trip_falls_back_to_detours_and_skips_duplicates(load_fixture):
    ors, session = client(
        make_response(400, ors_error(2004, "alternative routes limited to 100 km")),
        make_response(200, single_route(load_fixture, 0)),  # plain route
        make_response(200, single_route(load_fixture, 0)),  # left detour duplicates it
        make_response(404, ors_error(2010, "unroutable point")),  # right detour fails
        make_response(200, single_route(load_fixture, 1)),  # wider left detour is new
    )
    routes = ors.routes(DALLAS, WACO, count=2)
    assert [r.distance_mi for r in routes] == [90.0, 101.5]
    assert "alternative_routes" not in session.calls[1][2]["json"]
    assert len(session.calls[2][2]["json"]["coordinates"]) == 3  # origin, via, destination


def test_returns_fewer_routes_when_no_distinct_detour_exists(load_fixture):
    same = make_response(200, single_route(load_fixture))
    ors, _ = client(
        make_response(400, ors_error(2004)),
        same,
        *[make_response(200, single_route(load_fixture)) for _ in range(4)],
    )
    assert len(ors.routes(DALLAS, WACO, count=3)) == 1


def test_unroutable_trip_raises_with_api_message():
    ors, _ = client(make_response(404, ors_error(2009, "Route could not be found")))
    with pytest.raises(RoutingError, match="Route could not be found"):
        ors.routes(DALLAS, WACO)


def test_network_failure_is_wrapped():
    ors, _ = client(requests.ConnectionError("down"))
    with pytest.raises(RoutingError, match="unreachable"):
        ors.routes(DALLAS, WACO)
