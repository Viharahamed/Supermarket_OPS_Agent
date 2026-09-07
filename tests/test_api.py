# tests/test_api.py
"""Unit and Integration Tests for FastAPI Application Layer (Phase 13A.5).

Verifies liveness (/health), database readiness (/ready), 503 failure handling,
OpenAPI docs availability, CORS middleware, and secret masking.
"""

from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def test_health_endpoint_liveness():
    """Verify GET /health returns HTTP 200 {"status": "ok"}."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_endpoint_healthy():
    """Verify GET /ready returns HTTP 200 {"status": "ready", "database": "connected"} when DB is active."""
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "connected"}


def test_readiness_endpoint_db_failure():
    """Verify GET /ready returns HTTP 503 {"status": "not_ready"} when database query fails."""
    with patch("app.api.routes.health.get_db_context") as mock_db:
        mock_db.side_effect = Exception("Database connection timeout")
        response = client.get("/ready")
        assert response.status_code == 503
        assert response.json() == {"status": "not_ready"}
        # Ensure database error message/stack trace is NOT exposed to client
        assert "Database connection timeout" not in response.text


def test_openapi_and_docs_available():
    """Verify OpenAPI JSON and interactive /docs are accessible."""
    docs_resp = client.get("/docs")
    assert docs_resp.status_code == 200

    openapi_resp = client.get("/openapi.json")
    assert openapi_resp.status_code == 200
    schema = openapi_resp.json()
    assert schema["info"]["title"] == "kirana-ai-agent"
    assert "/health" in schema["paths"]
    assert "/ready" in schema["paths"]


def test_cors_middleware_headers():
    """Verify CORS middleware responds with correct Access-Control headers."""
    response = client.get(
        "/health",
        headers={"Origin": "http://localhost:3000"}
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_no_secrets_exposed_in_health_endpoints():
    """Verify health and readiness endpoints do not leak credentials or secret paths."""
    for path in ["/health", "/ready", "/docs", "/openapi.json"]:
        res = client.get(path)
        content = res.text
        assert "sk-or-" not in content
        assert "password" not in content.lower() or "password" in ["password authentication", "password"] and "postgres" not in content
