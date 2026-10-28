"""HTTP layer. Views stay thin: validate input, call services, serialize output."""

from __future__ import annotations

from django.conf import settings
from django.core.cache import cache
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from routing.clients.open_meteo import OpenMeteoClient, WeatherError
from routing.clients.ors import OrsClient, RoutingError
from routing.serializers import AnalyzeRequestSerializer, HeatmapRequestSerializer
from routing.services.analysis import analyze_trip
from routing.services.heatmap import build_heatmap

MIN_AUTOCOMPLETE_CHARS = 3


def routing_client() -> OrsClient:
    return OrsClient(
        settings.ORS_API_KEY, settings.ORS_BASE_URL, timeout=settings.HTTP_TIMEOUT_SECONDS
    )


def weather_client() -> OpenMeteoClient:
    return OpenMeteoClient(
        cache,
        settings.OPEN_METEO_BASE_URL,
        ttl_seconds=settings.WEATHER_CACHE_TTL_SECONDS,
        timeout=settings.HTTP_TIMEOUT_SECONDS,
    )


def _error(exc: RoutingError | WeatherError) -> Response:
    return Response({"detail": str(exc)}, status=exc.status)


@api_view(["GET"])
def health(request: Request) -> Response:
    """Liveness probe for Render, and a quick check that the routing key is configured."""
    return Response({"status": "ok", "routing_configured": bool(settings.ORS_API_KEY)})


@api_view(["GET"])
def geocode(request: Request) -> Response:
    """Autocomplete suggestions for the trip form."""
    query = request.query_params.get("q", "").strip()
    if len(query) < MIN_AUTOCOMPLETE_CHARS:
        return Response({"results": []})
    try:
        places = routing_client().autocomplete(query)
    except RoutingError as exc:
        return _error(exc)
    return Response({"results": [{"label": p.label, "lat": p.lat, "lon": p.lon} for p in places]})


@api_view(["POST"])
def analyze(request: Request) -> Response:
    serializer = AnalyzeRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    try:
        result = analyze_trip(serializer.to_trip(), routing_client(), weather_client())
    except (RoutingError, WeatherError) as exc:
        return _error(exc)
    return Response(result)


@api_view(["POST"])
def heatmap(request: Request) -> Response:
    """Risk frames for hours 0-48 over the corridor around the given route paths.

    POST rather than GET because the route paths are too large for a query string.
    """
    serializer = HeatmapRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    data = serializer.validated_data
    try:
        result = build_heatmap(data["paths"], data["start"], data["load_lb"], weather_client())
    except WeatherError as exc:
        return _error(exc)
    return Response(result)
