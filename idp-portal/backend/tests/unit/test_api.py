"""Tests for FastAPI application and API endpoints (AC #1, #7, #8)."""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.exceptions import IdpError, NotFoundError


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_app_title():
    """AC #1: FastAPI app has correct title and version."""
    assert app.title == "IDP Portal API"
    assert app.version == "0.1.0"


@pytest.mark.asyncio
async def test_health_endpoint_no_oracle(client):
    """AC #1: Health endpoint returns 503 when Oracle is not available."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 503
    data = response.json()
    assert data["data"]["status"] == "degraded"
    assert data["data"]["oracle"] == "disconnected"


@pytest.mark.asyncio
async def test_idp_error_handler(client):
    """AC #8: IdpError is handled and returns structured error response."""

    @app.get("/test-error")
    async def raise_error():
        raise NotFoundError("TEST_NOT_FOUND", "Test resource not found", {"id": 123})

    response = await client.get("/test-error")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "TEST_NOT_FOUND"
    assert body["error"]["message"] == "Test resource not found"
    assert body["error"]["details"]["id"] == 123


@pytest.mark.asyncio
async def test_idp_error_handler_no_details(client):
    """AC #8: IdpError without details omits details field."""

    @app.get("/test-error-no-details")
    async def raise_simple_error():
        raise IdpError(400, "BAD_REQUEST", "Bad request")

    response = await client.get("/test-error-no-details")
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "BAD_REQUEST"
    assert "details" not in body["error"]


@pytest.mark.asyncio
async def test_correlation_id_header(client):
    """Correlation ID middleware adds X-Idp-Request-Id header."""
    response = await client.get("/api/v1/health")
    assert "x-idp-request-id" in response.headers


@pytest.mark.asyncio
async def test_correlation_id_propagation(client):
    """Correlation ID middleware propagates provided ID."""
    response = await client.get(
        "/api/v1/health",
        headers={"X-Idp-Request-Id": "test-correlation-123"},
    )
    assert response.headers["x-idp-request-id"] == "test-correlation-123"
