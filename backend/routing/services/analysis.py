"""Use case: analyse a trip end-to-end.

Orchestrates the clients and the pure domain; contains no HTTP or Django code, so it is
tested with fake clients. The output is a plain dict ready for JSON.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from routing.clients.ors import Place
from routing.domain.forecast import HourlyForecast
from routing.domain.geometry import (
    Checkpoint,
    LatLon,
    RouteGeometry,
    generate_checkpoints,
    simplify,
)
from routing.domain.risk import RiskLevel, assess
from routing.domain.scoring import ScoredCheckpoint, explain, rank, score_route

ROUTE_NAMES = ("Route A", "Route B", "Route C")
COORD_DECIMALS = 5  # ~1 m; keeps the geometry payload small
# ~50 m: invisible at the zooms a whole route is viewed at, and cuts a cross-country
# polyline from thousands of points to a few hundred for faster drawing and transfer.
DISPLAY_TOLERANCE_DEG = 0.0005


class RoutingClient(Protocol):
    def geocode(self, text: str) -> Place: ...

    def routes(self, origin: Place, destination: Place, count: int = 3) -> list[RouteGeometry]: ...


class WeatherClient(Protocol):
    def forecasts(self, points: list[LatLon]) -> dict[LatLon, HourlyForecast]: ...


@dataclass(frozen=True)
class TripRequest:
    origin: Place | str
    destination: Place | str
    departure: datetime
    load_lb: float
    interval_mi: float


def _resolve(place: Place | str, routing: RoutingClient) -> Place:
    return place if isinstance(place, Place) else routing.geocode(place)


def _checkpoint_payload(checkpoint: Checkpoint, forecast: HourlyForecast | None, load_lb: float):
    weather = forecast.at(checkpoint.eta) if forecast else None
    payload = {
        "position_mi": round(checkpoint.position_mi, 2),
        "lat": round(checkpoint.lat, COORD_DECIMALS),
        "lon": round(checkpoint.lon, COORD_DECIMALS),
        "eta": checkpoint.eta.isoformat(),
        "weather": None,
        "level": None,
        "level_label": "Forecast unavailable",
        "reasons": [],
    }
    if weather is None:
        return payload, None
    result = assess(weather, load_lb)
    payload.update(
        weather={
            "wind_mph": round(weather.wind_mph, 1),
            "rain_in_hr": round(weather.rain_in_hr, 3),
            "snow_in_hr": round(weather.snow_in_hr, 3),
        },
        level=int(result.level),
        level_label=result.level.label,
        reasons=list(result.reasons),
    )
    return payload, result.level


def analyze_trip(trip: TripRequest, routing: RoutingClient, weather: WeatherClient) -> dict:
    origin = _resolve(trip.origin, routing)
    destination = _resolve(trip.destination, routing)
    geometries = routing.routes(origin, destination, count=len(ROUTE_NAMES))

    all_checkpoints = [
        generate_checkpoints(geometry, trip.interval_mi, trip.departure) for geometry in geometries
    ]
    forecasts = weather.forecasts([(c.lat, c.lon) for cps in all_checkpoints for c in cps])

    routes, scores = {}, []
    for name, geometry, checkpoints in zip(ROUTE_NAMES, geometries, all_checkpoints):
        cp_payloads, scored = [], []
        for checkpoint in checkpoints:
            forecast = forecasts.get((checkpoint.lat, checkpoint.lon))
            payload, level = _checkpoint_payload(checkpoint, forecast, trip.load_lb)
            cp_payloads.append(payload)
            scored.append(ScoredCheckpoint(checkpoint.position_mi, level))

        score = score_route(name, scored, geometry.distance_mi, geometry.duration_s)
        scores.append(score)
        known = [level for level in (s.level for s in scored) if level is not None]
        routes[name] = {
            "id": name,
            "distance_mi": round(geometry.distance_mi, 2),
            "duration_s": round(geometry.duration_s),
            "arrival": checkpoints[-1].eta.isoformat(),
            "geometry": [
                [round(lat, COORD_DECIMALS), round(lon, COORD_DECIMALS)]
                for lat, lon in simplify(geometry.coordinates, DISPLAY_TOLERANCE_DEG)
            ],
            "checkpoints": cp_payloads,
            "worst_level": int(max(known)) if known else None,
            "score": {
                "severe_miles": round(score.severe_miles, 1),
                "high_miles": round(score.high_miles, 1),
                "no_travel_miles": round(score.no_travel_miles, 1),
                "unknown_miles": round(score.unknown_miles, 1),
                "average_risk": (
                    round(score.average_risk, 3) if score.average_risk is not None else None
                ),
                "has_no_travel": score.has_no_travel,
            },
        }

    ranked = rank(scores)
    for position, score in enumerate(ranked, start=1):
        routes[score.route_id]["rank"] = position
    best = ranked[0]
    recommended = None if best.has_no_travel else best.route_id
    for route in routes.values():
        route["recommended"] = route["id"] == recommended

    return {
        "origin": _place_payload(origin),
        "destination": _place_payload(destination),
        "departure": trip.departure.isoformat(),
        "load_lb": trip.load_lb,
        "interval_mi": trip.interval_mi,
        "recommended_route_id": recommended,
        "explanation": explain(ranked),
        "risk_levels": [{"value": int(level), "label": level.label} for level in RiskLevel],
        "routes": [routes[s.route_id] for s in ranked],
    }


def _place_payload(place: Place) -> dict:
    return {"label": place.label, "lat": place.lat, "lon": place.lon}
