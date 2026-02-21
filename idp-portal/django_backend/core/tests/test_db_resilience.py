"""
Tests for DB resilience middleware.
Story 32.1: Detection and automatic reconnection after Data Guard failover/switchover.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch, call

from django.db import OperationalError
from django.db.utils import DatabaseError, InterfaceError
from django.http import HttpResponse, HttpRequest
from django.test import TestCase, RequestFactory, override_settings

from core.db_resilience import (
    DatabaseResilienceMiddleware,
    _is_connection_error,
    _extract_ora_code,
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
    """Tests for DatabaseResilienceMiddleware (Tasks 5.1, 5.2, 5.4)."""

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

    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_retries_on_operational_error_connection_lost(self, mock_close, mock_conn):
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
        mock_close.assert_called_once()

    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_retries_on_interface_error(self, mock_close, mock_conn):
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
        mock_close.assert_called_once()

    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_retries_on_database_error_ora_03135(self, mock_close, mock_conn):
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

    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_raises_if_retry_also_fails(self, mock_close, mock_conn):
        """If retry also fails, the error is propagated."""
        mock_conn.ensure_connection.return_value = None

        def always_failing(request):
            raise OperationalError("ORA-03113: end-of-file on communication channel")

        middleware = self._make_middleware(always_failing)
        with self.assertRaises(OperationalError):
            middleware(self.request)

    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_raises_if_reconnect_fails(self, mock_close, mock_conn):
        """If ensure_connection fails, original error is raised."""
        mock_conn.ensure_connection.side_effect = OperationalError("ORA-12541: no listener")

        def failing_view(request):
            raise OperationalError("ORA-03113: end-of-file on communication channel")

        middleware = self._make_middleware(failing_view)
        with self.assertRaises(OperationalError) as ctx:
            middleware(self.request)
        assert "ORA-03113" in str(ctx.exception)

    @patch('core.db_resilience.close_old_connections')
    def test_close_old_connections_called_on_connection_error(self, mock_close):
        """Verifies close_old_connections is called to purge dead connections (Task 5.2)."""
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

        mock_close.assert_called_once()

    @patch('core.db_resilience.logger')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_logs_db_connection_lost(self, mock_close, mock_conn, mock_logger):
        """Task 5.4: Verify db_connection_lost structlog event."""
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

        mock_logger.warning.assert_called_once()
        log_call = mock_logger.warning.call_args
        assert log_call[0][0] == "db_connection_lost"
        assert log_call[1]["error_type"] == "OperationalError"
        assert log_call[1]["error_code"] == "ORA-03113"

    @patch('core.db_resilience.logger')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_logs_db_connection_restored(self, mock_close, mock_conn, mock_logger):
        """Task 5.4: Verify db_connection_restored structlog event."""
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

    @patch('core.db_resilience.logger')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_logs_db_connection_retry_failed_on_reconnect(self, mock_close, mock_conn, mock_logger):
        """Task 5.4: Verify db_connection_retry_failed when reconnection fails."""
        mock_conn.ensure_connection.side_effect = OperationalError("ORA-12541: no listener")

        def failing_view(request):
            raise OperationalError("ORA-03113: end-of-file on communication channel")

        middleware = self._make_middleware(failing_view)
        with self.assertRaises(OperationalError):
            middleware(self.request)

        mock_logger.error.assert_called_once()
        log_call = mock_logger.error.call_args
        assert log_call[0][0] == "db_connection_retry_failed"

    @patch('core.db_resilience.logger')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_logs_db_connection_retry_failed_on_second_failure(self, mock_close, mock_conn, mock_logger):
        """Task 5.4: Verify db_connection_retry_failed when retry request fails."""
        mock_conn.ensure_connection.return_value = None

        def always_failing(request):
            raise OperationalError("ORA-03113: end-of-file on communication channel")

        middleware = self._make_middleware(always_failing)
        with self.assertRaises(OperationalError):
            middleware(self.request)

        # Should have warning (connection_lost) + error (retry_failed)
        mock_logger.warning.assert_called_once()
        mock_logger.error.assert_called_once()
        assert mock_logger.error.call_args[0][0] == "db_connection_retry_failed"


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
