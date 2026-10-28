"""Request validation. Responses are plain dicts built by the service layer."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from routing.clients.ors import Place
from routing.services.analysis import TripRequest

INTERVAL_CHOICES = (10, 25, 50)
MAX_LOAD_LB = 150_000
MAX_DEPARTURE_AHEAD = timedelta(days=5)  # leaves room for the trip within the 7-day forecast
DEPARTURE_GRACE = timedelta(hours=1)  # tolerate "now" sent from a slightly slow clock


class PlaceField(serializers.Field):
    """Accepts free text ("Dallas, TX") or an autocomplete pick ({label, lat, lon})."""

    default_error_messages = {
        "invalid": "Enter a location as text or as an object with label, lat and lon.",
        "range": "Coordinates are out of range.",
    }

    def to_internal_value(self, data):
        if isinstance(data, str):
            if not data.strip():
                self.fail("invalid")
            return data.strip()
        if isinstance(data, dict):
            try:
                lat, lon = float(data["lat"]), float(data["lon"])
            except (KeyError, TypeError, ValueError):
                self.fail("invalid")
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                self.fail("range")
            return Place(str(data.get("label") or f"{lat:.4f}, {lon:.4f}"), lat, lon)
        self.fail("invalid")

    def to_representation(self, value):
        return value


class AnalyzeRequestSerializer(serializers.Serializer):
    origin = PlaceField()
    destination = PlaceField()
    departure = serializers.DateTimeField()
    load_lb = serializers.FloatField(min_value=0, max_value=MAX_LOAD_LB)
    interval_mi = serializers.ChoiceField(choices=INTERVAL_CHOICES)

    def validate_departure(self, value):
        now = timezone.now()
        if value < now - DEPARTURE_GRACE:
            raise serializers.ValidationError("Departure can't be in the past.")
        if value > now + MAX_DEPARTURE_AHEAD:
            raise serializers.ValidationError("Departure must be within the next 5 days.")
        return value

    def to_trip(self) -> TripRequest:
        data = self.validated_data
        return TripRequest(
            origin=data["origin"],
            destination=data["destination"],
            departure=data["departure"],
            load_lb=data["load_lb"],
            interval_mi=data["interval_mi"],
        )
