"""OpenRouteService client: geocoding, autocomplete and HGV (truck) directions.

All parsing is done by module-level functions that take plain JSON, so they can be tested
against recorded payloads without any HTTP.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import requests

from routing.domain.geometry import LatLon, RouteGeometry, Step, detour_point, similar

logger = logging.getLogger(__name__)

# ORS error code returned when a request exceeds server limits, e.g. alternative routes
# on trips longer than ~100 km on the public API.
ORS_LIMIT_EXCEEDED = 2004
DETOUR_FRACTIONS = (0.12, 0.25)  # tried left and right of the direct line, nearest first


class RoutingError(Exception):
    """A problem the user should see (bad address, no route, service down).

    ``status`` is the HTTP status the API layer should answer with: 422 for problems with
    the user's input, 502/503 when the upstream service failed or isn't configured.
    """

    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class Place:
    label: str
    lat: float
    lon: float

    @property
    def latlon(self) -> LatLon:
        return (self.lat, self.lon)


def parse_places(payload: dict[str, Any]) -> list[Place]:
    places = []
    for feature in payload.get("features", []):
        lon, lat = feature["geometry"]["coordinates"][:2]
        places.append(Place(feature["properties"].get("label", ""), lat, lon))
    return places


def parse_directions(payload: dict[str, Any]) -> list[RouteGeometry]:
    """GeoJSON directions response -> routes. Multi-segment routes (via points) are merged."""
    routes = []
    for feature in payload.get("features", []):
        props = feature["properties"]
        steps = tuple(
            Step(step["way_points"][0], step["way_points"][1], float(step["duration"]))
            for segment in props.get("segments", [])
            for step in segment.get("steps", [])
        )
        routes.append(
            RouteGeometry(
                coordinates=tuple(
                    (lat, lon) for lon, lat, *_ in feature["geometry"]["coordinates"]
                ),
                steps=steps,
                distance_mi=float(props["summary"].get("distance", 0.0)),
                duration_s=float(props["summary"].get("duration", 0.0)),
            )
        )
    return routes


def _error_code(response: requests.Response) -> int | None:
    try:
        return int(response.json()["error"]["code"])
    except (ValueError, KeyError, TypeError):
        return None


def _error_message(response: requests.Response) -> str:
    try:
        error = response.json()["error"]
        return error["message"] if isinstance(error, dict) else str(error)
    except (ValueError, KeyError, TypeError):
        return response.text[:200]


class OrsClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openrouteservice.org",
        timeout: float = 15,
        session: requests.Session | None = None,
    ):
        if not api_key:
            raise RoutingError("Routing is not configured (ORS_API_KEY is missing).", 503)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update({"Authorization": api_key})

    # --- geocoding ------------------------------------------------------------------

    def geocode(self, text: str) -> Place:
        places = self._search("/geocode/search", text, size=1)
        if not places:
            raise RoutingError(f"Couldn't find a location for '{text}'.")
        return places[0]

    def autocomplete(self, text: str, size: int = 5) -> list[Place]:
        return self._search("/geocode/autocomplete", text, size=size)

    def _search(self, path: str, text: str, size: int) -> list[Place]:
        params = {"text": text, "size": size, "boundary.country": "US,CA"}
        response = self._send("GET", path, params=params)
        if not response.ok:
            raise RoutingError(f"Geocoding failed: {_error_message(response)}", 502)
        return parse_places(response.json())

    # --- directions -----------------------------------------------------------------

    def routes(self, origin: Place, destination: Place, count: int = 3) -> list[RouteGeometry]:
        """Up to ``count`` distinct truck routes, fastest-first as returned by the API.

        Native alternatives are tried first. The public API rejects them on long trips, so
        we fall back to a single route plus detours through points either side of the
        midpoint, discarding detours that duplicate a route we already have.
        """
        ends = [origin.latlon, destination.latlon]
        routes = self._directions(ends, alternatives=count)
        if routes is None:
            routes = self._directions(ends) or []
        if not routes:
            raise RoutingError("No truck route found between these locations.")

        for fraction in DETOUR_FRACTIONS:
            for side in (1, -1):
                if len(routes) >= count:
                    return routes
                via = detour_point(origin.latlon, destination.latlon, side, fraction)
                for candidate in self._directions([ends[0], via, ends[1]]) or []:
                    if not any(similar(candidate, existing) for existing in routes):
                        routes.append(candidate)
        return routes[:count]

    def _directions(
        self, points: list[LatLon], alternatives: int = 0
    ) -> list[RouteGeometry] | None:
        """Routes for ``points``; None if the request hit a server limit or wasn't routable."""
        body: dict[str, Any] = {
            "coordinates": [[lon, lat] for lat, lon in points],
            "units": "mi",
            "instructions": True,
            "radiuses": [-1] * len(points),  # snap to the nearest road however far away
        }
        if alternatives > 1:
            body["alternative_routes"] = {
                "target_count": alternatives,
                "weight_factor": 1.6,
                "share_factor": 0.6,
            }
        response = self._send("POST", "/v2/directions/driving-hgv/geojson", json=body)
        if response.ok:
            return parse_directions(response.json())

        is_via_request = len(points) > 2
        if _error_code(response) == ORS_LIMIT_EXCEEDED or (
            is_via_request and response.status_code in (400, 404)
        ):
            logger.info("ORS declined request: %s", _error_message(response))
            return None
        raise RoutingError(f"Routing failed: {_error_message(response)}")

    def _send(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        try:
            return self.session.request(
                method, self.base_url + path, timeout=self.timeout, **kwargs
            )
        except requests.RequestException as exc:
            raise RoutingError("Routing service is unreachable. Please try again.", 502) from exc
