"""
Integration tests for DB resilience middleware — portal and API consumer scenarios.

Story 32.3: Validates that DatabaseResilienceMiddleware protects ALL Django views
universally (portal users and external API consumers alike).

Uses RequestFactory + middleware direct invocation to test the retry logic with
realistic request parameters (URLs, headers, methods). Django wraps each middleware
with convert_exception_to_response which catches exceptions before they reach
upper middleware, so direct invocation is the correct approach for middleware tests.
"""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock, call

from django.db import OperationalError
from django.db.utils import InterfaceError
from django.http import HttpResponse, JsonResponse
from django.test import TestCase, RequestFactory, override_settings

from core.db_resilience import DatabaseResilienceMiddleware


def _ok_response(data=None):
    """Return a standard JSON response like DRF views produce."""
    if data is None:
        data = {"data": [], "pagination": {"count": 0, "limit": 50, "offset": 0}}
    return JsonResponse(data)


def _ok_201_response():
    """Return a 201 response like POST /executions/ produces."""
    return JsonResponse(
        {"data": {"id": 42, "status": "submitted"}},
        status=201,
    )


# ============================================================================
# Task 1 — Portal integration tests (AC #1, #2)
# ============================================================================

@override_settings(
    DB_RETRY_MAX_ATTEMPTS=3,
    DB_RETRY_BACKOFF_BASE=0.01,
)
class TestPortalResilience(TestCase):
    """Integration tests: portal user scenarios (browser requests).

    Subtasks 1.1 through 1.5.
    """

    def setUp(self):
        self.factory = RequestFactory()

    # --- 1.2: Portal read — GET /api/v1/catalog/actions/ ---

    @patch("core.db_resilience.time.sleep")
    @patch("core.db_resilience.close_old_connections")
    @patch("django.db.connection.ensure_connection")
    def test_catalog_read_retry_on_operational_error(
        self, mock_ensure, mock_close, mock_sleep
    ):
        """GET catalog — OperationalError on 1st call, success on 2nd → HTTP 200."""
        call_count = {"n": 0}

        def get_response(request):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise OperationalError(
                    "ORA-03113: end-of-file on communication channel"
                )
            return _ok_response()

        middleware = DatabaseResilienceMiddleware(get_response)
        request = self.factory.get("/api/v1/catalog/actions/")
        response = middleware(request)

        assert response.status_code == 200
        body = json.loads(response.content)
        assert "data" in body
        assert call_count["n"] == 2

    @patch("core.db_resilience.time.sleep")
    @patch("core.db_resilience.close_old_connections")
    @patch("django.db.connection.ensure_connection")
    def test_catalog_read_retry_on_interface_error(
        self, mock_ensure, mock_close, mock_sleep
    ):
        """GET catalog — InterfaceError on 1st call, success on 2nd → HTTP 200."""
        call_count = {"n": 0}

        def get_response(request):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise InterfaceError("connection is closed")
            return _ok_response()

        middleware = DatabaseResilienceMiddleware(get_response)
        request = self.factory.get("/api/v1/catalog/actions/")
        response = middleware(request)

        assert response.status_code == 200
        assert call_count["n"] == 2

    # --- 1.3: Portal write — POST /api/v1/executions/ ---

    @patch("core.db_resilience.time.sleep")
    @patch("core.db_resilience.close_old_connections")
    @patch("django.db.connection.ensure_connection")
    def test_execution_write_retry_on_interface_error(
        self, mock_ensure, mock_close, mock_sleep
    ):
        """POST executions — InterfaceError (pre-commit, always safe) → retry → 201."""
        call_count = {"n": 0}

        def get_response(request):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise InterfaceError("connection is closed")
            return _ok_201_response()

        middleware = DatabaseResilienceMiddleware(get_response)
        request = self.factory.post(
            "/api/v1/executions/",
            data=json.dumps({"action_id": 1, "target_names": ["srv01"]}),
            content_type="application/json",
        )
        response = middleware(request)

        assert response.status_code == 201
        body = json.loads(response.content)
        assert body["data"]["id"] == 42
        assert call_count["n"] == 2

    # --- 1.3b: Portal write mid-commit — POST → immediate 503 (no retry) ---

    @patch("core.db_resilience.time.sleep")
    @patch("core.db_resilience.close_old_connections")
    @patch("django.db.connection.ensure_connection")
    def test_execution_write_mid_commit_no_retry(
        self, mock_ensure, mock_close, mock_sleep
    ):
        """POST executions — OperationalError ORA-03113 with in_atomic_block=False
        (mid-commit detected) → immediate 503, no retry attempted."""
        call_count = {"n": 0}

        def get_response(request):
            call_count["n"] += 1
            raise OperationalError("ORA-03113: end-of-file on communication channel")

        middleware = DatabaseResilienceMiddleware(get_response)
        request = self.factory.post(
            "/api/v1/executions/",
            data=json.dumps({"action_id": 1, "target_names": ["srv01"]}),
            content_type="application/json",
        )

        # Simulate mid-commit: in_atomic_block=False → _is_mid_commit_error returns True
        with patch("core.db_resilience.connection") as mock_conn:
            mock_conn.in_atomic_block = False
            response = middleware(request)

        assert response.status_code == 503
        body = json.loads(response.content)
        assert body["error"]["code"] == "DB_UNAVAILABLE"
        # Mid-commit → retry unsafe → only 1 call to get_response (no retry)
        assert call_count["n"] == 1

    # --- 1.4: Portal failure — retries exhausted → 503 ---

    @patch("core.db_resilience.time.sleep")
    @patch("core.db_resilience.close_old_connections")
    @patch("django.db.connection.ensure_connection")
    def test_catalog_503_when_retries_exhausted(
        self, mock_ensure, mock_close, mock_sleep
    ):
        """GET catalog — all retries fail → 503 + DB_UNAVAILABLE + Retry-After: 30."""
        def get_response(request):
            raise OperationalError(
                "ORA-03113: end-of-file on communication channel"
            )

        middleware = DatabaseResilienceMiddleware(get_response)
        request = self.factory.get("/api/v1/catalog/actions/")
        response = middleware(request)

        assert response.status_code == 503
        body = json.loads(response.content)
        assert body["error"]["code"] == "DB_UNAVAILABLE"
        assert "message" in body["error"]
        assert "correlation_id" in body["error"]
        assert response["Retry-After"] == "30"

    # --- 1.5: correlation_id in response and logs ---

    @patch("core.db_resilience.get_correlation_id", return_value="test-corr-id-portal")
    @patch("core.db_resilience.time.sleep")
    @patch("core.db_resilience.close_old_connections")
    @patch("django.db.connection.ensure_connection")
    def test_503_response_contains_correlation_id(
        self, mock_ensure, mock_close, mock_sleep, mock_corr
    ):
        """503 response includes correlation_id for traceability."""
        def get_response(request):
            raise OperationalError("ORA-12541: TNS:no listener")

        middleware = DatabaseResilienceMiddleware(get_response)
        request = self.factory.get("/api/v1/catalog/actions/")
        response = middleware(request)

        assert response.status_code == 503
        body = json.loads(response.content)
        assert body["error"]["correlation_id"] == "test-corr-id-portal"

    @patch("core.db_resilience.logger")
    @patch("core.db_resilience.get_correlation_id", return_value="log-corr-id")
    @patch("core.db_resilience.time.sleep")
    @patch("core.db_resilience.close_old_connections")
    @patch("django.db.connection.ensure_connection")
    def test_correlation_id_in_logs(
        self, mock_ensure, mock_close, mock_sleep, mock_corr, mock_logger
    ):
        """Retry events are logged with correlation_id, method, and path."""
        def get_response(request):
            raise OperationalError(
                "ORA-03113: end-of-file on communication channel"
            )

        middleware = DatabaseResilienceMiddleware(get_response)
        request = self.factory.get("/api/v1/catalog/actions/")
        middleware(request)

        # db_connection_lost logged
        mock_logger.warning.assert_any_call(
            "db_connection_lost",
            correlation_id="log-corr-id",
            error_type="OperationalError",
            error_code="ORA-03113",
            error="ORA-03113: end-of-file on communication channel",
            method="GET",
            path="/api/v1/catalog/actions/",
        )

        # db_retry_exhausted logged — total_duration_ms is a dynamic value, check key presence
        exhausted_call = next(
            (c for c in mock_logger.error.call_args_list if c[0][0] == "db_retry_exhausted"),
            None,
        )
        assert exhausted_call is not None, "db_retry_exhausted event not logged"
        kwargs = exhausted_call[1]
        assert kwargs["correlation_id"] == "log-corr-id"
        assert kwargs["total_attempts"] == 3
        assert isinstance(kwargs["total_duration_ms"], (int, float))
        assert kwargs["error_type"] == "OperationalError"
        assert kwargs["error_code"] == "ORA-03113"
        assert kwargs["method"] == "GET"
        assert kwargs["path"] == "/api/v1/catalog/actions/"


# ============================================================================
# Task 2 — API consumer integration tests (AC #1, #3)
# ============================================================================

@override_settings(
    DB_RETRY_MAX_ATTEMPTS=3,
    DB_RETRY_BACKOFF_BASE=0.01,
)
class TestAPIConsumerResilience(TestCase):
    """Integration tests: external API consumer scenarios (JWT Bearer auth).

    Verifies that the middleware applies identically to API consumers
    as it does to portal users (AC #1, #3).
    """

    def setUp(self):
        self.factory = RequestFactory()

    def _api_get(self, path):
        """Create GET request with API consumer JWT auth headers."""
        return self.factory.get(
            path,
            HTTP_AUTHORIZATION="Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.test",
            HTTP_ACCEPT="application/json",
        )

    def _api_post(self, path, data):
        """Create POST request with API consumer JWT auth headers."""
        return self.factory.post(
            path,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.test",
            HTTP_ACCEPT="application/json",
        )

    # --- 2.1: API read — GET /api/v1/scheduled-executions/ with JWT ---

    @patch("core.db_resilience.time.sleep")
    @patch("core.db_resilience.close_old_connections")
    @patch("django.db.connection.ensure_connection")
    def test_api_read_retry_on_db_failure(
        self, mock_ensure, mock_close, mock_sleep
    ):
        """GET scheduled-executions with JWT — retry on OperationalError → 200."""
        call_count = {"n": 0}

        def get_response(request):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise OperationalError(
                    "ORA-03113: end-of-file on communication channel"
                )
            return _ok_response()

        middleware = DatabaseResilienceMiddleware(get_response)
        request = self._api_get("/api/v1/scheduled-executions/")
        response = middleware(request)

        assert response.status_code == 200
        assert call_count["n"] == 2

    # --- 2.2: API write — POST /api/v1/executions/ with JWT ---

    @patch("core.db_resilience.time.sleep")
    @patch("core.db_resilience.close_old_connections")
    @patch("django.db.connection.ensure_connection")
    def test_api_write_retry_on_interface_error(
        self, mock_ensure, mock_close, mock_sleep
    ):
        """POST executions with JWT — InterfaceError → retry → 201."""
        call_count = {"n": 0}

        def get_response(request):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise InterfaceError("connection is closed")
            return _ok_201_response()

        middleware = DatabaseResilienceMiddleware(get_response)
        request = self._api_post(
            "/api/v1/executions/",
            data={"action_id": 1, "target_names": ["srv01"]},
        )
        response = middleware(request)

        assert response.status_code == 201
        assert call_count["n"] == 2

    # --- 2.3: API failure — retries exhausted → 503 ---

    @patch("core.db_resilience.time.sleep")
    @patch("core.db_resilience.close_old_connections")
    @patch("django.db.connection.ensure_connection")
    def test_api_503_when_retries_exhausted(
        self, mock_ensure, mock_close, mock_sleep
    ):
        """API consumer: all retries exhausted → 503 with standardised body."""
        def get_response(request):
            raise OperationalError("ORA-03135: connection lost contact")

        middleware = DatabaseResilienceMiddleware(get_response)
        request = self._api_get("/api/v1/scheduled-executions/")
        response = middleware(request)

        assert response.status_code == 503
        body = json.loads(response.content)
        assert body["error"]["code"] == "DB_UNAVAILABLE"
        assert "message" in body["error"]
        assert "correlation_id" in body["error"]
        assert response["Retry-After"] == "30"

    # --- 2.4: Same 503 format for portal and API ---

    @patch("core.db_resilience.time.sleep")
    @patch("core.db_resilience.close_old_connections")
    @patch("django.db.connection.ensure_connection")
    def test_503_format_identical_portal_and_api(
        self, mock_ensure, mock_close, mock_sleep
    ):
        """503 response structure is identical regardless of request origin."""
        def get_response(request):
            raise OperationalError(
                "ORA-03113: end-of-file on communication channel"
            )

        middleware = DatabaseResilienceMiddleware(get_response)

        # Portal request (no auth)
        portal_request = self.factory.get("/api/v1/catalog/actions/")
        portal_response = middleware(portal_request)

        # API consumer request (JWT auth)
        api_request = self._api_get("/api/v1/catalog/actions/")
        api_response = middleware(api_request)

        # Both 503
        assert portal_response.status_code == 503
        assert api_response.status_code == 503

        portal_body = json.loads(portal_response.content)
        api_body = json.loads(api_response.content)

        # Same error structure keys
        assert set(portal_body["error"].keys()) == set(api_body["error"].keys())
        assert portal_body["error"]["code"] == api_body["error"]["code"] == "DB_UNAVAILABLE"

        # Same Retry-After header
        assert portal_response["Retry-After"] == api_response["Retry-After"] == "30"

        # Same message
        assert portal_body["error"]["message"] == api_body["error"]["message"]


# ============================================================================
# Middleware universality — AC #1 validation
# ============================================================================

class TestMiddlewareUniversality(TestCase):
    """Verify the middleware is universally applied (AC #1)."""

    def test_middleware_in_settings(self):
        """DatabaseResilienceMiddleware is in MIDDLEWARE settings."""
        from django.conf import settings
        assert "core.db_resilience.DatabaseResilienceMiddleware" in settings.MIDDLEWARE

    def test_middleware_after_correlation_id(self):
        """DatabaseResilienceMiddleware is after CorrelationIdMiddleware."""
        from django.conf import settings
        mw = settings.MIDDLEWARE
        corr_idx = mw.index("core.middleware.CorrelationIdMiddleware")
        db_idx = mw.index("core.db_resilience.DatabaseResilienceMiddleware")
        assert db_idx > corr_idx, (
            "DatabaseResilienceMiddleware must be after CorrelationIdMiddleware"
        )

    def test_middleware_before_request_logging(self):
        """DatabaseResilienceMiddleware is before RequestResponseLoggingMiddleware."""
        from django.conf import settings
        mw = settings.MIDDLEWARE
        db_idx = mw.index("core.db_resilience.DatabaseResilienceMiddleware")
        log_idx = mw.index("core.middleware.RequestResponseLoggingMiddleware")
        assert db_idx < log_idx, (
            "DatabaseResilienceMiddleware must be before RequestResponseLoggingMiddleware"
        )
