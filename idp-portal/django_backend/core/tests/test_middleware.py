"""
Tests for core middleware.
Story M.8 - Task 10: Tests for RequestResponseLoggingMiddleware.
"""

import uuid
from unittest.mock import patch, MagicMock

import pytest
from django.test import TestCase, RequestFactory
from django.http import HttpResponse, HttpResponseServerError

from core.middleware import (
    CorrelationIdMiddleware,
    RequestResponseLoggingMiddleware,
    SecurityHeadersMiddleware,
    get_correlation_id,
    set_correlation_id,
    get_client_ip,
)


class TestCorrelationIdMiddleware(TestCase):
    """Tests for CorrelationIdMiddleware."""

    def setUp(self):
        self.factory = RequestFactory()
        self.get_response = MagicMock(return_value=HttpResponse("OK"))
        self.middleware = CorrelationIdMiddleware(self.get_response)

    def tearDown(self):
        # Clear thread-local after each test
        set_correlation_id(None)

    def test_generates_correlation_id_if_absent(self):
        """Test that correlation ID is generated when not present in request."""
        request = self.factory.get('/api/v1/test')

        response = self.middleware(request)

        # Should have correlation ID header in response
        assert 'X-Correlation-ID' in response
        # Should be a valid UUID format
        correlation_id = response['X-Correlation-ID']
        uuid.UUID(correlation_id)  # Will raise if not valid UUID

    def test_preserves_correlation_id_from_header(self):
        """Test that correlation ID from X-Correlation-ID request header is preserved."""
        existing_id = 'test-correlation-id-12345'
        request = self.factory.get(
            '/api/v1/test',
            HTTP_X_CORRELATION_ID=existing_id
        )

        response = self.middleware(request)

        assert response['X-Correlation-ID'] == existing_id

    def test_correlation_id_available_in_thread_local(self):
        """Test that correlation ID is available via get_correlation_id() during request."""
        request = self.factory.get('/api/v1/test')

        captured_id = None
        def capture_correlation_id(req):
            nonlocal captured_id
            captured_id = get_correlation_id()
            return HttpResponse("OK")

        middleware = CorrelationIdMiddleware(capture_correlation_id)
        response = middleware(request)

        assert captured_id is not None
        assert response['X-Correlation-ID'] == captured_id

    def test_correlation_id_cleared_after_request(self):
        """Test that correlation ID is cleared from thread-local after request."""
        request = self.factory.get('/api/v1/test')

        self.middleware(request)

        # After request completes, thread-local should be cleared
        assert get_correlation_id() is None

    def test_correlation_id_attached_to_request(self):
        """Test that correlation ID is attached to request object."""
        request = self.factory.get('/api/v1/test')

        captured_request = None
        def capture_request(req):
            nonlocal captured_request
            captured_request = req
            return HttpResponse("OK")

        middleware = CorrelationIdMiddleware(capture_request)
        middleware(request)

        assert hasattr(captured_request, 'correlation_id')
        assert captured_request.correlation_id is not None


class TestRequestResponseLoggingMiddleware(TestCase):
    """Tests for RequestResponseLoggingMiddleware."""

    def setUp(self):
        self.factory = RequestFactory()

    def tearDown(self):
        set_correlation_id(None)

    @patch('core.middleware.logger')
    def test_logs_request_received(self, mock_logger):
        """Test that request_received is logged with correct fields."""
        set_correlation_id('test-correlation-123')
        request = self.factory.get('/api/v1/catalog/actions')
        request.user = MagicMock(is_authenticated=False)

        get_response = MagicMock(return_value=HttpResponse("OK"))
        middleware = RequestResponseLoggingMiddleware(get_response)

        middleware(request)

        # Check request_received was logged
        request_received_call = mock_logger.info.call_args_list[0]
        assert request_received_call[0][0] == 'request_received'
        assert request_received_call[1]['method'] == 'GET'
        assert request_received_call[1]['path'] == '/api/v1/catalog/actions'
        assert request_received_call[1]['correlation_id'] == 'test-correlation-123'

    @patch('core.middleware.logger')
    def test_logs_request_completed_success(self, mock_logger):
        """Test that request_completed is logged for successful responses."""
        set_correlation_id('test-correlation-456')
        request = self.factory.get('/api/v1/test')
        request.user = MagicMock(is_authenticated=False)

        response = HttpResponse("OK", status=200)
        get_response = MagicMock(return_value=response)
        middleware = RequestResponseLoggingMiddleware(get_response)

        middleware(request)

        # Check request_completed was logged with info level
        request_completed_call = mock_logger.info.call_args_list[1]
        assert request_completed_call[0][0] == 'request_completed'
        assert request_completed_call[1]['status_code'] == 200
        assert 'duration_ms' in request_completed_call[1]

    @patch('core.middleware.logger')
    def test_logs_request_completed_client_error(self, mock_logger):
        """Test that 4xx responses are logged with warning level."""
        set_correlation_id('test-correlation-789')
        request = self.factory.get('/api/v1/not-found')
        request.user = MagicMock(is_authenticated=False)

        response = HttpResponse("Not Found", status=404)
        get_response = MagicMock(return_value=response)
        middleware = RequestResponseLoggingMiddleware(get_response)

        middleware(request)

        # Check request_completed was logged with warning level
        assert mock_logger.warning.called
        warning_call = mock_logger.warning.call_args
        assert warning_call[0][0] == 'request_completed'
        assert warning_call[1]['status_code'] == 404

    @patch('core.middleware.logger')
    def test_logs_request_completed_server_error(self, mock_logger):
        """Test that 5xx responses are logged with error level."""
        set_correlation_id('test-correlation-error')
        request = self.factory.get('/api/v1/error')
        request.user = MagicMock(is_authenticated=False)

        response = HttpResponseServerError("Server Error")
        get_response = MagicMock(return_value=response)
        middleware = RequestResponseLoggingMiddleware(get_response)

        middleware(request)

        # Check request_completed was logged with error level
        assert mock_logger.error.called
        error_call = mock_logger.error.call_args
        assert error_call[0][0] == 'request_completed'
        assert error_call[1]['status_code'] == 500

    @patch('core.middleware.logger')
    def test_logs_request_failed_on_exception(self, mock_logger):
        """Test that exceptions are logged with request_failed event."""
        set_correlation_id('test-correlation-exception')
        request = self.factory.get('/api/v1/error')
        request.user = MagicMock(is_authenticated=False)

        def raise_exception(req):
            raise ValueError("Test exception")

        middleware = RequestResponseLoggingMiddleware(raise_exception)

        with pytest.raises(ValueError):
            middleware(request)

        # Check request_failed was logged with error level
        assert mock_logger.error.called
        error_call = mock_logger.error.call_args
        assert error_call[0][0] == 'request_failed'
        assert 'exception' in error_call[1]
        assert error_call[1]['exc_info'] is True

    @patch('core.middleware.logger')
    def test_includes_user_id_when_authenticated(self, mock_logger):
        """Test that user_id is included in logs for authenticated users."""
        set_correlation_id('test-auth-user')
        request = self.factory.get('/api/v1/test')
        request.user = MagicMock(is_authenticated=True, id=42)

        get_response = MagicMock(return_value=HttpResponse("OK"))
        middleware = RequestResponseLoggingMiddleware(get_response)

        middleware(request)

        # Check user_id in request_completed log
        request_completed_call = mock_logger.info.call_args_list[1]
        assert request_completed_call[1]['user_id'] == '42'

    @patch('core.middleware.logger')
    def test_duration_ms_calculated_correctly(self, mock_logger):
        """Test that duration_ms is calculated and included."""
        set_correlation_id('test-duration')
        request = self.factory.get('/api/v1/test')
        request.user = MagicMock(is_authenticated=False)

        get_response = MagicMock(return_value=HttpResponse("OK"))
        middleware = RequestResponseLoggingMiddleware(get_response)

        middleware(request)

        # Check duration_ms is present and is a number
        request_completed_call = mock_logger.info.call_args_list[1]
        duration_ms = request_completed_call[1]['duration_ms']
        assert isinstance(duration_ms, int)
        assert duration_ms >= 0


class TestGetClientIp(TestCase):
    """Tests for get_client_ip helper function."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_returns_remote_addr(self):
        """Test that REMOTE_ADDR is returned when no X-Forwarded-For."""
        request = self.factory.get('/test')
        request.META['REMOTE_ADDR'] = '192.168.1.100'

        ip = get_client_ip(request)

        assert ip == '192.168.1.100'

    def test_returns_first_ip_from_x_forwarded_for(self):
        """Test that first IP from X-Forwarded-For is returned."""
        request = self.factory.get('/test')
        request.META['HTTP_X_FORWARDED_FOR'] = '10.0.0.1, 10.0.0.2, 10.0.0.3'

        ip = get_client_ip(request)

        assert ip == '10.0.0.1'

    def test_handles_single_x_forwarded_for(self):
        """Test handling single IP in X-Forwarded-For."""
        request = self.factory.get('/test')
        request.META['HTTP_X_FORWARDED_FOR'] = '10.0.0.1'

        ip = get_client_ip(request)

        assert ip == '10.0.0.1'


class TestSecurityHeadersMiddleware(TestCase):
    """Tests for SecurityHeadersMiddleware."""

    def setUp(self):
        self.factory = RequestFactory()
        self.get_response = MagicMock(return_value=HttpResponse("OK"))
        self.middleware = SecurityHeadersMiddleware(self.get_response)

    def test_adds_security_headers(self):
        """Test that security headers are added to response."""
        request = self.factory.get('/test')

        response = self.middleware(request)

        assert response['X-Content-Type-Options'] == 'nosniff'
        assert response['X-Frame-Options'] == 'DENY'
        assert response['X-XSS-Protection'] == '1; mode=block'
        assert response['Referrer-Policy'] == 'strict-origin-when-cross-origin'

    def test_adds_cache_control_for_api_paths(self):
        """Test that Cache-Control is added for API paths."""
        request = self.factory.get('/api/v1/catalog/actions')

        response = self.middleware(request)

        assert 'no-store' in response['Cache-Control']
        assert response['Pragma'] == 'no-cache'

    def test_no_cache_control_for_non_api_paths(self):
        """Test that Cache-Control is not added for non-API paths."""
        request = self.factory.get('/static/file.js')

        response = self.middleware(request)

        assert 'Cache-Control' not in response
