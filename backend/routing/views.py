"""HTTP layer. Views stay thin: validate input, call services, serialize output."""

from __future__ import annotations

from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response


@api_view(["GET"])
def health(request: Request) -> Response:
    """Liveness probe for Render, and a quick check that the routing key is configured."""
    return Response({"status": "ok", "routing_configured": bool(settings.ORS_API_KEY)})
