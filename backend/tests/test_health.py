from django.test import override_settings
from rest_framework.test import APIClient


def test_health_reports_ok_without_routing_key():
    with override_settings(ORS_API_KEY=""):
        response = APIClient().get("/api/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "routing_configured": False}


def test_health_reports_routing_configured_when_key_present():
    with override_settings(ORS_API_KEY="test-key"):
        response = APIClient().get("/api/health/")
    assert response.json()["routing_configured"] is True
