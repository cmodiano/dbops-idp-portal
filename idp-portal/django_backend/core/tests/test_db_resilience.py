"""
Tests for DB resilience middleware.
Story 32.1: Detection and automatic reconnection after Data Guard failover/switchover.
Story 32.2: Bounded retry with exponential backoff, idempotency protection, 503 response.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch, call

from django.db import OperationalError
from django.db.utils import DatabaseError, InterfaceError
from django.http import HttpResponse
from django.test import TestCase, RequestFactory

from core.db_resilience import (
    DatabaseResilienceMiddleware,
    _is_connection_error,
    _extract_ora_code,
    _is_mid_commit_error,
    _is_retry_safe,
    _calculate_backoff,
    CONNECTION_ERROR_CODES,
)


class TestIsConnectionError(TestCase):
    """Tests for _is_connection_error helper (Task 5.1)."""

    def test_interface_error_is_connection_error(self):
        exc = InterfaceError("connection is closed")
        assert _is_connection_error(exc) is True

    def test_operational_error_with_ora_03113(self):
        exc = OperationalError("ORA-03113: end-of-file on communication channel")
        assert _is_connection_error(exc) is True

    def test_operational_error_with_ora_03114(self):
        exc = OperationalError("ORA-03114: not connected to ORACLE")
        assert _is_connection_error(exc) is True

    def test_operational_error_with_ora_01033(self):
        exc = OperationalError("ORA-01033: ORACLE initialization or shutdown in progress")
        assert _is_connection_error(exc) is True

    def test_operational_error_with_ora_12541(self):
        exc = OperationalError("ORA-12541: TNS:no listener")
        assert _is_connection_error(exc) is True

    def test_operational_error_with_ora_12543(self):
        exc = OperationalError("ORA-12543: TNS:destination host unreachable")
        assert _is_connection_error(exc) is True

    def test_database_error_with_ora_03135(self):
        exc = DatabaseError("ORA-03135: connection lost contact")
        assert _is_connection_error(exc) is True

    def test_operational_error_generic_not_connected(self):
        exc = OperationalError("not connected to database")
        assert _is_connection_error(exc) is True

    def test_operational_error_connection_lost(self):
        exc = OperationalError("connection lost during query")
        assert _is_connection_error(exc) is True

    def test_operational_error_query_error_not_connection(self):
        """Query/logic errors should NOT be treated as connection errors."""
        exc = OperationalError("ORA-00942: table or view does not exist")
        assert _is_connection_error(exc) is False

    def test_database_error_constraint_violation_not_connection(self):
        exc = DatabaseError("ORA-00001: unique constraint violated")
        assert _is_connection_error(exc) is False

    def test_non_db_exception_not_caught(self):
        exc = ValueError("some value error")
        assert _is_connection_error(exc) is False

    def test_operational_error_ora_12170_connect_timeout(self):
        exc = OperationalError("ORA-12170: TNS:Connect timeout occurred")
        assert _is_connection_error(exc) is True

    def test_operational_error_ora_12514_service_unknown(self):
        exc = OperationalError("ORA-12514: TNS:listener does not currently know of service")
        assert _is_connection_error(exc) is True

    def test_all_known_ora_codes_detected(self):
        """Every code in CONNECTION_ERROR_CODES should be recognized."""
        for code in CONNECTION_ERROR_CODES:
            exc = OperationalError(f"ORA-{code:05d}: some error message")
            assert _is_connection_error(exc) is True, f"ORA-{code:05d} not detected"


class TestExtractOraCode(TestCase):
    """Tests for _extract_ora_code helper."""

    def test_extracts_ora_03113(self):
        exc = OperationalError("ORA-03113: end-of-file on communication channel")
        assert _extract_ora_code(exc) == "ORA-03113"

    def test_extracts_ora_12541(self):
        exc = OperationalError("ORA-12541: TNS:no listener")
        assert _extract_ora_code(exc) == "ORA-12541"

    def test_returns_none_for_unknown_code(self):
        exc = OperationalError("ORA-00942: table or view does not exist")
        assert _extract_ora_code(exc) is None

    def test_returns_none_for_no_code(self):
        exc = InterfaceError("connection closed")
        assert _extract_ora_code(exc) is None


class TestDatabaseResilienceMiddleware(TestCase):
    """Tests for DatabaseResilienceMiddleware (Story 32.1 updated for 32.2 retry logic)."""

    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get('/api/v1/health/')

    def _make_middleware(self, get_response):
        return DatabaseResilienceMiddleware(get_response)

    def test_passes_through_successful_request(self):
        """Normal requests pass through without interception."""
        response = HttpResponse("OK", status=200)
        middleware = self._make_middleware(lambda r: response)
        result = middleware(self.request)
        assert result.status_code == 200

    def test_passes_through_non_connection_db_error(self):
        """Non-connection DB errors (e.g., table not found) are not retried."""
        def failing_view(request):
            raise OperationalError("ORA-00942: table or view does not exist")

        middleware = self._make_middleware(failing_view)
        with self.assertRaises(OperationalError):
            middleware(self.request)

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_retries_on_operational_error_connection_lost(self, mock_close, mock_conn, mock_sleep):
        """Connection error triggers close_old_connections + retry."""
        mock_conn.ensure_connection.return_value = None
        call_count = 0

        def view_with_recovery(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise OperationalError("ORA-03113: end-of-file on communication channel")
            return HttpResponse("OK", status=200)

        middleware = self._make_middleware(view_with_recovery)
        result = middleware(self.request)

        assert result.status_code == 200
        assert call_count == 2
        mock_close.assert_called()

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_retries_on_interface_error(self, mock_close, mock_conn, mock_sleep):
        """InterfaceError is always treated as connection error."""
        mock_conn.ensure_connection.return_value = None
        call_count = 0

        def view_with_recovery(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise InterfaceError("connection is closed")
            return HttpResponse("OK", status=200)

        middleware = self._make_middleware(view_with_recovery)
        result = middleware(self.request)

        assert result.status_code == 200
        mock_close.assert_called()

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_retries_on_database_error_ora_03135(self, mock_close, mock_conn, mock_sleep):
        """DatabaseError with connection ORA code triggers retry."""
        mock_conn.ensure_connection.return_value = None
        call_count = 0

        def view_with_recovery(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise DatabaseError("ORA-03135: connection lost contact")
            return HttpResponse("OK", status=200)

        middleware = self._make_middleware(view_with_recovery)
        result = middleware(self.request)

        assert result.status_code == 200

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_returns_503_if_all_retries_fail(self, mock_close, mock_conn, mock_sleep):
        """If all retries fail, returns 503 with structured JSON."""
        mock_conn.ensure_connection.return_value = None

        def always_failing(request):
            raise OperationalError("ORA-03113: end-of-file on communication channel")

        middleware = self._make_middleware(always_failing)
        result = middleware(self.request)

        assert result.status_code == 503
        data = json.loads(result.content)
        assert data["error"]["code"] == "DB_UNAVAILABLE"
        assert result["Retry-After"] == "30"

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_returns_503_if_reconnect_always_fails(self, mock_close, mock_conn, mock_sleep):
        """If ensure_connection fails on every attempt, returns 503."""
        mock_conn.ensure_connection.side_effect = OperationalError("ORA-12541: no listener")

        def failing_view(request):
            raise OperationalError("ORA-03113: end-of-file on communication channel")

        middleware = self._make_middleware(failing_view)
        result = middleware(self.request)

        assert result.status_code == 503
        data = json.loads(result.content)
        assert data["error"]["code"] == "DB_UNAVAILABLE"

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.close_old_connections')
    def test_close_old_connections_called_on_connection_error(self, mock_close, mock_sleep):
        """Verifies close_old_connections is called to purge dead connections."""
        call_count = 0

        def view_with_recovery(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise InterfaceError("connection closed")
            return HttpResponse("OK", status=200)

        with patch('core.db_resilience.connection') as mock_conn:
            mock_conn.ensure_connection.return_value = None
            middleware = self._make_middleware(view_with_recovery)
            middleware(self.request)

        mock_close.assert_called()

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.logger')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_logs_db_connection_lost(self, mock_close, mock_conn, mock_logger, mock_sleep):
        """Verify db_connection_lost structlog event."""
        mock_conn.ensure_connection.return_value = None
        call_count = 0

        def view_with_recovery(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise OperationalError("ORA-03113: end-of-file on communication channel")
            return HttpResponse("OK", status=200)

        middleware = self._make_middleware(view_with_recovery)
        middleware(self.request)

        # First warning call should be db_connection_lost
        warning_calls = mock_logger.warning.call_args_list
        lost_call = warning_calls[0]
        assert lost_call[0][0] == "db_connection_lost"
        assert lost_call[1]["error_type"] == "OperationalError"
        assert lost_call[1]["error_code"] == "ORA-03113"

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.logger')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_logs_db_connection_restored(self, mock_close, mock_conn, mock_logger, mock_sleep):
        """Verify db_connection_restored structlog event."""
        mock_conn.ensure_connection.return_value = None
        call_count = 0

        def view_with_recovery(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise OperationalError("ORA-03113: end-of-file on communication channel")
            return HttpResponse("OK", status=200)

        middleware = self._make_middleware(view_with_recovery)
        middleware(self.request)

        mock_logger.info.assert_called_once()
        log_call = mock_logger.info.call_args
        assert log_call[0][0] == "db_connection_restored"
        assert log_call[1]["original_error_code"] == "ORA-03113"

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.logger')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_logs_db_retry_exhausted_on_reconnect_failure(self, mock_close, mock_conn, mock_logger, mock_sleep):
        """Verify db_retry_exhausted when reconnection always fails."""
        mock_conn.ensure_connection.side_effect = OperationalError("ORA-12541: no listener")

        def failing_view(request):
            raise OperationalError("ORA-03113: end-of-file on communication channel")

        middleware = self._make_middleware(failing_view)
        result = middleware(self.request)

        assert result.status_code == 503
        mock_logger.error.assert_called_once()
        log_call = mock_logger.error.call_args
        assert log_call[0][0] == "db_retry_exhausted"

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.logger')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_logs_db_retry_exhausted_on_repeated_failure(self, mock_close, mock_conn, mock_logger, mock_sleep):
        """Verify db_retry_exhausted when retry requests keep failing."""
        mock_conn.ensure_connection.return_value = None

        def always_failing(request):
            raise OperationalError("ORA-03113: end-of-file on communication channel")

        middleware = self._make_middleware(always_failing)
        result = middleware(self.request)

        assert result.status_code == 503
        # Should have warning (connection_lost) + warning (retry_attempts) + error (exhausted)
        assert mock_logger.error.call_args[0][0] == "db_retry_exhausted"


# ============================================================================
# Story 32.2: Retry, backoff, idempotency, 503 response
# ============================================================================

class TestRetrySuccessOnSecondAttempt(TestCase):
    """Task 4.1: Success on 2nd attempt — mock 1 error then success."""

    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get('/api/v1/actions/')

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_success_on_second_attempt(self, mock_close, mock_conn, mock_sleep):
        mock_conn.ensure_connection.return_value = None
        call_count = 0

        def view(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise OperationalError("ORA-03113: end-of-file on communication channel")
            return HttpResponse("OK", status=200)

        middleware = DatabaseResilienceMiddleware(view)
        result = middleware(self.request)

        assert result.status_code == 200
        assert call_count == 2


class TestRetrySuccessOnThirdAttempt(TestCase):
    """Task 4.2: Success on 3rd attempt — mock 2 errors then success."""

    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get('/api/v1/actions/')

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_success_on_third_attempt(self, mock_close, mock_conn, mock_sleep):
        mock_conn.ensure_connection.return_value = None
        call_count = 0

        def view(request):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise OperationalError("ORA-03113: end-of-file on communication channel")
            return HttpResponse("OK", status=200)

        middleware = DatabaseResilienceMiddleware(view)
        result = middleware(self.request)

        assert result.status_code == 200
        assert call_count == 3


class TestRetryExhausted(TestCase):
    """Task 4.3: Failure after N retries exhausted → 503 + body JSON + Retry-After."""

    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get('/api/v1/actions/')

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_503_after_exhausted_retries(self, mock_close, mock_conn, mock_sleep):
        mock_conn.ensure_connection.return_value = None

        def always_failing(request):
            raise OperationalError("ORA-03113: end-of-file on communication channel")

        middleware = DatabaseResilienceMiddleware(always_failing)
        result = middleware(self.request)

        assert result.status_code == 503
        data = json.loads(result.content)
        assert data["error"]["code"] == "DB_UNAVAILABLE"
        assert "indisponible" in data["error"]["message"]
        assert result["Retry-After"] == "30"

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_503_includes_correlation_id(self, mock_close, mock_conn, mock_sleep):
        mock_conn.ensure_connection.return_value = None

        def always_failing(request):
            raise OperationalError("ORA-03113: end-of-file on communication channel")

        with patch('core.db_resilience.get_correlation_id', return_value="test-corr-123"):
            middleware = DatabaseResilienceMiddleware(always_failing)
            result = middleware(self.request)

        data = json.loads(result.content)
        assert data["error"]["correlation_id"] == "test-corr-123"


class TestBackoffTiming(TestCase):
    """Task 4.4: Verify time.sleep called with correct intervals."""

    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get('/api/v1/actions/')

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_backoff_intervals(self, mock_close, mock_conn, mock_sleep):
        """Backoff: attempt 1 = immediate (no sleep), attempt 2 = 0.5s, attempt 3 = 1.0s."""
        mock_conn.ensure_connection.return_value = None

        def always_failing(request):
            raise OperationalError("ORA-03113: end-of-file on communication channel")

        middleware = DatabaseResilienceMiddleware(always_failing)
        middleware(self.request)

        sleep_calls = mock_sleep.call_args_list
        # Attempt 1: no sleep (immediate)
        # Attempt 2: sleep(0.5)
        # Attempt 3: sleep(1.0)
        assert len(sleep_calls) == 2
        assert sleep_calls[0] == call(0.5)
        assert sleep_calls[1] == call(1.0)

    def test_calculate_backoff_values(self):
        """Unit test for _calculate_backoff function."""
        assert _calculate_backoff(0) == 0.5   # base
        assert _calculate_backoff(1) == 1.0   # base * 2
        assert _calculate_backoff(2) == 2.0   # base * 4
        assert _calculate_backoff(3) == 4.0   # base * 8
        assert _calculate_backoff(4) == 5.0   # capped at 5s
        assert _calculate_backoff(10) == 5.0  # capped at 5s


class TestIdempotenceReadMethods(TestCase):
    """Task 4.5: GET retried without condition."""

    def setUp(self):
        self.factory = RequestFactory()

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_get_always_retried(self, mock_close, mock_conn, mock_sleep):
        mock_conn.ensure_connection.return_value = None
        request = self.factory.get('/api/v1/actions/')
        call_count = 0

        def view(r):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise OperationalError("ORA-03113: end-of-file on communication channel")
            return HttpResponse("OK", status=200)

        middleware = DatabaseResilienceMiddleware(view)
        result = middleware(request)

        assert result.status_code == 200
        assert call_count == 2

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_head_always_retried(self, mock_close, mock_conn, mock_sleep):
        mock_conn.ensure_connection.return_value = None
        request = self.factory.head('/api/v1/actions/')
        call_count = 0

        def view(r):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise InterfaceError("connection closed")
            return HttpResponse("OK", status=200)

        middleware = DatabaseResilienceMiddleware(view)
        result = middleware(request)

        assert result.status_code == 200

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_options_always_retried(self, mock_close, mock_conn, mock_sleep):
        mock_conn.ensure_connection.return_value = None
        request = self.factory.options('/api/v1/actions/')
        call_count = 0

        def view(r):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise InterfaceError("connection closed")
            return HttpResponse("OK", status=200)

        middleware = DatabaseResilienceMiddleware(view)
        result = middleware(request)

        assert result.status_code == 200


class TestIdempotenceWritePreCommit(TestCase):
    """Task 4.6: POST retried if error is pre-commit."""

    def setUp(self):
        self.factory = RequestFactory()

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_post_retried_on_interface_error(self, mock_close, mock_conn, mock_sleep):
        """InterfaceError = connection dead = pre-commit → retry safe."""
        mock_conn.ensure_connection.return_value = None
        request = self.factory.post('/api/v1/actions/', data='{}', content_type='application/json')
        call_count = 0

        def view(r):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise InterfaceError("connection is closed")
            return HttpResponse('{"id": 1}', status=201, content_type='application/json')

        middleware = DatabaseResilienceMiddleware(view)
        result = middleware(request)

        assert result.status_code == 201
        assert call_count == 2

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_put_retried_on_interface_error(self, mock_close, mock_conn, mock_sleep):
        mock_conn.ensure_connection.return_value = None
        request = self.factory.put('/api/v1/actions/1/', data='{}', content_type='application/json')
        call_count = 0

        def view(r):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise InterfaceError("connection is closed")
            return HttpResponse('{"id": 1}', status=200, content_type='application/json')

        middleware = DatabaseResilienceMiddleware(view)
        result = middleware(request)

        assert result.status_code == 200
        assert call_count == 2


class TestIdempotenceWritePatch(TestCase):
    """Review fix M3: PATCH method retry coverage (AC #2)."""

    def setUp(self):
        self.factory = RequestFactory()

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_patch_retried_on_interface_error(self, mock_close, mock_conn, mock_sleep):
        """InterfaceError on PATCH = connection dead = pre-commit → retry safe."""
        mock_conn.ensure_connection.return_value = None
        request = self.factory.patch('/api/v1/actions/1/', data='{}', content_type='application/json')
        call_count = 0

        def view(r):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise InterfaceError("connection is closed")
            return HttpResponse('{"id": 1}', status=200, content_type='application/json')

        middleware = DatabaseResilienceMiddleware(view)
        result = middleware(request)

        assert result.status_code == 200
        assert call_count == 2

    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_patch_mid_commit_returns_503(self, mock_close, mock_conn):
        """ORA-03113 on PATCH with in_atomic_block=False → mid-commit → 503."""
        mock_conn.in_atomic_block = False
        request = self.factory.patch('/api/v1/actions/1/', data='{}', content_type='application/json')

        def view(r):
            raise OperationalError("ORA-03113: end-of-file on communication channel")

        middleware = DatabaseResilienceMiddleware(view)
        result = middleware(request)

        assert result.status_code == 503
        assert "incertain" in json.loads(result.content)["error"]["message"]


class TestMidCommitDuringRetry(TestCase):
    """Review fix M4: mid-commit error detected DURING a retry attempt."""

    def setUp(self):
        self.factory = RequestFactory()

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_post_mid_commit_on_retry_returns_503(self, mock_close, mock_conn, mock_sleep):
        """First error is pre-commit (retry safe), retry error is mid-commit → 503."""
        mock_conn.ensure_connection.return_value = None
        call_count = 0

        def view(r):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise InterfaceError("connection is closed")  # pre-commit → retry safe
            # Retry attempt: mid-commit error (ORA-03113 + not in atomic block)
            raise OperationalError("ORA-03113: end-of-file on communication channel")

        # First call: InterfaceError → _is_retry_safe=True → enters retry loop
        # Retry: ORA-03113 with in_atomic_block=False → _is_retry_safe=False → 503
        mock_conn.in_atomic_block = False
        request = self.factory.post('/api/v1/actions/', data='{}', content_type='application/json')

        middleware = DatabaseResilienceMiddleware(view)
        result = middleware(request)

        assert result.status_code == 503
        data = json.loads(result.content)
        assert data["error"]["code"] == "DB_UNAVAILABLE"
        assert "incertain" in data["error"]["message"]


class TestWriteMidCommitNoRetry(TestCase):
    """Task 4.7: POST with ORA-03113 mid-commit → no retry → 503."""

    def setUp(self):
        self.factory = RequestFactory()

    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_post_mid_commit_returns_503(self, mock_close, mock_conn):
        """ORA-03113 with in_atomic_block=False → mid-commit → no retry → 503."""
        mock_conn.in_atomic_block = False  # Django cleaned up atomic → uncertain state
        request = self.factory.post('/api/v1/actions/', data='{}', content_type='application/json')

        def view(r):
            raise OperationalError("ORA-03113: end-of-file on communication channel")

        middleware = DatabaseResilienceMiddleware(view)
        result = middleware(request)

        assert result.status_code == 503
        data = json.loads(result.content)
        assert data["error"]["code"] == "DB_UNAVAILABLE"
        assert "incertain" in data["error"]["message"]
        assert result["Retry-After"] == "30"

    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_delete_mid_commit_returns_503(self, mock_close, mock_conn):
        mock_conn.in_atomic_block = False
        request = self.factory.delete('/api/v1/actions/1/')

        def view(r):
            raise OperationalError("ORA-03114: not connected to ORACLE")

        middleware = DatabaseResilienceMiddleware(view)
        result = middleware(request)

        assert result.status_code == 503
        assert "incertain" in json.loads(result.content)["error"]["message"]

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_post_pre_commit_ora_03113_retried(self, mock_close, mock_conn, mock_sleep):
        """ORA-03113 with in_atomic_block=True → pre-commit → retry safe."""
        mock_conn.in_atomic_block = True
        mock_conn.ensure_connection.return_value = None
        request = self.factory.post('/api/v1/actions/', data='{}', content_type='application/json')
        call_count = 0

        def view(r):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise OperationalError("ORA-03113: end-of-file on communication channel")
            return HttpResponse('{"id": 1}', status=201, content_type='application/json')

        middleware = DatabaseResilienceMiddleware(view)
        result = middleware(request)

        assert result.status_code == 201
        assert call_count == 2


class TestRetryLogging(TestCase):
    """Task 4.8: Verify events db_retry_attempt, db_retry_exhausted with attributes."""

    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get('/api/v1/actions/')

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.logger')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_logs_retry_attempts(self, mock_close, mock_conn, mock_logger, mock_sleep):
        mock_conn.ensure_connection.return_value = None
        call_count = 0

        def view(r):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise OperationalError("ORA-03113: end-of-file on communication channel")
            return HttpResponse("OK", status=200)

        middleware = DatabaseResilienceMiddleware(view)
        middleware(self.request)

        # Find all db_retry_attempt calls
        retry_calls = [
            c for c in mock_logger.warning.call_args_list
            if c[0][0] == "db_retry_attempt"
        ]
        # 2 errors → attempt 1 succeeds at retry, attempt 2 succeeds at retry
        # But 3rd call succeeds, so only 2 retry_attempt logs before the 3rd attempt
        # Actually: original call fails, then attempt 1 retries (fails), attempt 2 retries (succeeds)
        assert len(retry_calls) == 2  # attempts 1 and 2

        # Verify attempt 1 attributes
        assert retry_calls[0][1]["attempt_number"] == 1
        assert retry_calls[0][1]["max_attempts"] == 3
        assert retry_calls[0][1]["backoff_seconds"] == 0
        assert retry_calls[0][1]["method"] == "GET"
        assert retry_calls[0][1]["path"] == "/api/v1/actions/"

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.logger')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_logs_retry_exhausted(self, mock_close, mock_conn, mock_logger, mock_sleep):
        mock_conn.ensure_connection.return_value = None

        def always_failing(r):
            raise OperationalError("ORA-03113: end-of-file on communication channel")

        middleware = DatabaseResilienceMiddleware(always_failing)
        middleware(self.request)

        exhausted_calls = [
            c for c in mock_logger.error.call_args_list
            if c[0][0] == "db_retry_exhausted"
        ]
        assert len(exhausted_calls) == 1
        attrs = exhausted_calls[0][1]
        assert attrs["total_attempts"] == 3
        assert "total_duration_ms" in attrs
        assert attrs["method"] == "GET"
        assert attrs["path"] == "/api/v1/actions/"


class TestRetrySettings(TestCase):
    """Task 4.9: Verify settings are read from DB_RETRY_MAX_ATTEMPTS / DB_RETRY_BACKOFF_BASE."""

    def test_settings_exist(self):
        import idp_backend.settings as prod_settings
        assert hasattr(prod_settings, 'DB_RETRY_MAX_ATTEMPTS')
        assert isinstance(prod_settings.DB_RETRY_MAX_ATTEMPTS, int)
        assert prod_settings.DB_RETRY_MAX_ATTEMPTS >= 1
        assert hasattr(prod_settings, 'DB_RETRY_BACKOFF_BASE')
        assert isinstance(prod_settings.DB_RETRY_BACKOFF_BASE, float)
        assert prod_settings.DB_RETRY_BACKOFF_BASE > 0

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_custom_max_attempts(self, mock_close, mock_conn, mock_sleep):
        """With DB_RETRY_MAX_ATTEMPTS=1, only 1 attempt is made."""
        mock_conn.ensure_connection.return_value = None
        call_count = 0

        def always_failing(r):
            nonlocal call_count
            call_count += 1
            raise OperationalError("ORA-03113: end-of-file on communication channel")

        factory = RequestFactory()
        request = factory.get('/api/v1/actions/')

        with self.settings(DB_RETRY_MAX_ATTEMPTS=1):
            middleware = DatabaseResilienceMiddleware(always_failing)
            result = middleware(request)

        assert result.status_code == 503
        # 1 original call + 1 retry attempt = 2 total calls
        assert call_count == 2


class TestRetrocompatibility(TestCase):
    """Task 4.10: Verify that existing 32.1 behavior still works."""

    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get('/api/v1/health/')

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_single_error_then_recovery(self, mock_close, mock_conn, mock_sleep):
        """Basic 32.1 scenario: one error, then recovery."""
        mock_conn.ensure_connection.return_value = None
        call_count = 0

        def view(r):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise OperationalError("ORA-03113: end-of-file on communication channel")
            return HttpResponse("OK", status=200)

        middleware = DatabaseResilienceMiddleware(view)
        result = middleware(self.request)

        assert result.status_code == 200
        mock_close.assert_called()

    def test_non_connection_error_not_caught(self):
        """Non-connection DB errors are NOT retried."""
        def view(r):
            raise OperationalError("ORA-00942: table or view does not exist")

        middleware = DatabaseResilienceMiddleware(view)
        with self.assertRaises(OperationalError):
            middleware(self.request)

    def test_is_connection_error_helper_unchanged(self):
        """_is_connection_error still works for all known codes."""
        for code in CONNECTION_ERROR_CODES:
            exc = OperationalError(f"ORA-{code:05d}: test")
            assert _is_connection_error(exc) is True

    def test_extract_ora_code_helper_unchanged(self):
        """_extract_ora_code still extracts correctly."""
        exc = OperationalError("ORA-03113: end-of-file")
        assert _extract_ora_code(exc) == "ORA-03113"


class TestIsMidCommitError(TestCase):
    """Unit tests for _is_mid_commit_error helper."""

    @patch('core.db_resilience.connection')
    def test_interface_error_never_mid_commit(self, mock_conn):
        """InterfaceError = connection dead = always pre-commit."""
        exc = InterfaceError("connection is closed")
        assert _is_mid_commit_error(exc) is False

    @patch('core.db_resilience.connection')
    def test_ora_03135_not_mid_commit(self, mock_conn):
        """ORA-03135 is not in MID_COMMIT_ORA_CODES → not mid-commit."""
        exc = OperationalError("ORA-03135: connection lost contact")
        assert _is_mid_commit_error(exc) is False

    @patch('core.db_resilience.connection')
    def test_ora_03113_in_atomic_block_not_mid_commit(self, mock_conn):
        """ORA-03113 with in_atomic_block=True → pre-commit → not mid-commit."""
        mock_conn.in_atomic_block = True
        exc = OperationalError("ORA-03113: end-of-file on communication channel")
        assert _is_mid_commit_error(exc) is False

    @patch('core.db_resilience.connection')
    def test_ora_03113_not_in_atomic_block_is_mid_commit(self, mock_conn):
        """ORA-03113 with in_atomic_block=False → mid-commit."""
        mock_conn.in_atomic_block = False
        exc = OperationalError("ORA-03113: end-of-file on communication channel")
        assert _is_mid_commit_error(exc) is True


class TestIsRetrySafe(TestCase):
    """Unit tests for _is_retry_safe helper."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_safe_methods_always_safe(self):
        for method_name in ('get', 'head', 'options'):
            method = getattr(self.factory, method_name)
            request = method('/api/v1/test/')
            exc = OperationalError("ORA-03113: end-of-file")
            assert _is_retry_safe(request, exc) is True, f"{method_name.upper()} should be safe"

    @patch('core.db_resilience.connection')
    def test_post_with_interface_error_is_safe(self, mock_conn):
        request = self.factory.post('/api/v1/test/', data='{}', content_type='application/json')
        exc = InterfaceError("connection closed")
        assert _is_retry_safe(request, exc) is True

    @patch('core.db_resilience.connection')
    def test_post_with_mid_commit_error_not_safe(self, mock_conn):
        mock_conn.in_atomic_block = False
        request = self.factory.post('/api/v1/test/', data='{}', content_type='application/json')
        exc = OperationalError("ORA-03113: end-of-file on communication channel")
        assert _is_retry_safe(request, exc) is False


class TestSettingsConfiguration(TestCase):
    """Tests for DB settings configuration (Task 5.3).

    Verifies that the production settings.py reads DB resilience
    env vars and applies them to DATABASES['default'].
    """

    def test_conn_max_age_in_production_settings(self):
        """settings.py defines CONN_MAX_AGE from DB_CONN_MAX_AGE env var."""
        import idp_backend.settings as prod_settings
        # Verify the setting exists and is an integer
        assert hasattr(prod_settings, 'DB_CONN_MAX_AGE')
        assert isinstance(prod_settings.DB_CONN_MAX_AGE, int)
        assert prod_settings.DATABASES['default']['CONN_MAX_AGE'] == prod_settings.DB_CONN_MAX_AGE

    def test_conn_health_checks_in_production_settings(self):
        """settings.py defines CONN_HEALTH_CHECKS from DB_CONN_HEALTH_CHECKS env var."""
        import idp_backend.settings as prod_settings
        assert hasattr(prod_settings, 'DB_CONN_HEALTH_CHECKS')
        assert isinstance(prod_settings.DB_CONN_HEALTH_CHECKS, bool)
        assert prod_settings.DATABASES['default']['CONN_HEALTH_CHECKS'] == prod_settings.DB_CONN_HEALTH_CHECKS

    def test_resilience_middleware_in_middleware_stack(self):
        """DatabaseResilienceMiddleware is registered in MIDDLEWARE."""
        import idp_backend.settings as prod_settings
        assert 'core.db_resilience.DatabaseResilienceMiddleware' in prod_settings.MIDDLEWARE

    def test_resilience_middleware_after_correlation_id(self):
        """DatabaseResilienceMiddleware is placed after CorrelationIdMiddleware."""
        import idp_backend.settings as prod_settings
        mw = prod_settings.MIDDLEWARE
        corr_idx = mw.index('core.middleware.CorrelationIdMiddleware')
        resil_idx = mw.index('core.db_resilience.DatabaseResilienceMiddleware')
        assert resil_idx > corr_idx, "Resilience middleware must be after CorrelationIdMiddleware"


class TestHealthCheckDbPoolStatus(TestCase):
    """Tests for health check db_pool_status field (Task 4)."""

    def setUp(self):
        from django.test import Client
        self.client = Client()
        self.url = '/api/v1/health/'

    @patch('core.views.connection')
    def test_health_check_includes_db_pool_status(self, mock_connection):
        """Health check response includes db_pool_status."""
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_connection.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_connection.is_usable.return_value = True

        response = self.client.get(self.url)

        assert response.status_code == 200
        data = response.json()['data']
        assert 'db_pool_status' in data
        pool = data['db_pool_status']
        assert 'conn_max_age' in pool
        assert 'conn_health_checks' in pool
        assert 'connection_usable' in pool
        assert pool['connection_usable'] is True

    @patch('core.views.connection')
    def test_health_check_db_pool_status_on_failure(self, mock_connection):
        """Health check includes db_pool_status even when DB is down."""
        mock_connection.cursor.side_effect = Exception("ORA-12541: no listener")

        response = self.client.get(self.url)

        assert response.status_code == 503
        data = response.json()['data']
        assert 'db_pool_status' in data
        assert data['db_pool_status']['connection_usable'] is False
