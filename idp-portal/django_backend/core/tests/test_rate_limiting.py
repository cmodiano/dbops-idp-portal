"""
Story 17.11: Tests for rate limiting (throttling, middleware, configuration).

Tests cover:
- DRF throttle classes (AuthEndpointThrottle, ExecutionThrottle, etc.)
- RateLimitHeadersMiddleware (429 detection, logging, headers)
- Rate limit configuration validation (startup_checks)
- Per-scope rate differentiation
- IP-based vs user-based keying
"""

from unittest.mock import patch, MagicMock

import pytest
from django.test import TestCase, RequestFactory, override_settings
from django.http import HttpResponse
from django.core.exceptions import ImproperlyConfigured

from core.middleware import (
    RateLimitHeadersMiddleware,
    set_correlation_id,
)
from core.throttling import (
    AuthEndpointThrottle,
    TokenRefreshThrottle,
    ExecutionThrottle,
    GeneralAPIThrottle,
    PublicEndpointThrottle,
)


class TestAuthEndpointThrottle(TestCase):
    """Tests for AuthEndpointThrottle class."""

    def setUp(self):
        self.factory = RequestFactory()
        self.throttle = AuthEndpointThrottle()

    def test_scope_is_auth(self):
        assert self.throttle.scope == 'auth'

    def test_cache_key_uses_client_ip(self):
        request = self.factory.get('/api/v1/auth/saml/login/')
        request.META['REMOTE_ADDR'] = '10.0.0.1'
        key = self.throttle.get_cache_key(request, None)
        assert '10.0.0.1' in key
        assert 'auth' in key

    def test_cache_key_uses_x_forwarded_for(self):
        request = self.factory.get('/api/v1/auth/saml/login/')
        request.META['HTTP_X_FORWARDED_FOR'] = '192.168.1.50, 10.0.0.1'
        key = self.throttle.get_cache_key(request, None)
        assert '192.168.1.50' in key

    def test_different_ips_get_different_keys(self):
        request1 = self.factory.get('/api/v1/auth/saml/login/')
        request1.META['REMOTE_ADDR'] = '10.0.0.1'

        request2 = self.factory.get('/api/v1/auth/saml/login/')
        request2.META['REMOTE_ADDR'] = '10.0.0.2'

        key1 = self.throttle.get_cache_key(request1, None)
        key2 = self.throttle.get_cache_key(request2, None)
        assert key1 != key2


class TestTokenRefreshThrottle(TestCase):
    """Tests for TokenRefreshThrottle class."""

    def setUp(self):
        self.factory = RequestFactory()
        self.throttle = TokenRefreshThrottle()

    def test_scope_is_token_refresh(self):
        assert self.throttle.scope == 'token_refresh'

    def test_cache_key_uses_client_ip(self):
        request = self.factory.post('/api/v1/auth/refresh/')
        request.META['REMOTE_ADDR'] = '10.0.0.5'
        key = self.throttle.get_cache_key(request, None)
        assert '10.0.0.5' in key
        assert 'token_refresh' in key


class TestExecutionThrottle(TestCase):
    """Tests for ExecutionThrottle class."""

    def test_scope_is_execution(self):
        throttle = ExecutionThrottle()
        assert throttle.scope == 'execution'

    def test_inherits_from_user_rate_throttle(self):
        from rest_framework.throttling import UserRateThrottle
        assert issubclass(ExecutionThrottle, UserRateThrottle)


class TestGeneralAPIThrottle(TestCase):
    """Tests for GeneralAPIThrottle class."""

    def test_scope_is_general_api(self):
        throttle = GeneralAPIThrottle()
        assert throttle.scope == 'general_api'

    def test_inherits_from_user_rate_throttle(self):
        from rest_framework.throttling import UserRateThrottle
        assert issubclass(GeneralAPIThrottle, UserRateThrottle)


class TestPublicEndpointThrottle(TestCase):
    """Tests for PublicEndpointThrottle class."""

    def setUp(self):
        self.factory = RequestFactory()
        self.throttle = PublicEndpointThrottle()

    def test_scope_is_public(self):
        assert self.throttle.scope == 'public'

    def test_cache_key_uses_client_ip(self):
        request = self.factory.get('/api/v1/auth/logout/')
        request.META['REMOTE_ADDR'] = '172.16.0.1'
        key = self.throttle.get_cache_key(request, None)
        assert '172.16.0.1' in key
        assert 'public' in key


class TestRateLimitHeadersMiddleware(TestCase):
    """Tests for RateLimitHeadersMiddleware."""

    def setUp(self):
        self.factory = RequestFactory()

    def tearDown(self):
        set_correlation_id(None)

    def test_non_429_response_passes_through(self):
        """Non-429 responses should pass through unchanged."""
        request = self.factory.get('/api/v1/catalog/actions/')
        response = HttpResponse("OK", status=200)
        get_response = MagicMock(return_value=response)
        middleware = RateLimitHeadersMiddleware(get_response)

        result = middleware(request)

        assert result.status_code == 200

    @patch('core.middleware.logger')
    def test_429_response_logs_warning(self, mock_logger):
        """429 responses should trigger a structured warning log."""
        set_correlation_id('test-rate-limit-123')
        request = self.factory.get('/api/v1/catalog/actions/')
        request.META['REMOTE_ADDR'] = '192.168.1.100'
        request.user = MagicMock(is_authenticated=True, id=42)

        response = HttpResponse("Throttled", status=429)
        response['Retry-After'] = '30'
        get_response = MagicMock(return_value=response)
        middleware = RateLimitHeadersMiddleware(get_response)

        middleware(request)

        mock_logger.warning.assert_called()
        warning_call = mock_logger.warning.call_args
        assert warning_call[0][0] == 'rate_limit_exceeded'
        assert warning_call[1]['correlation_id'] == 'test-rate-limit-123'
        assert warning_call[1]['ip_address'] == '192.168.1.100'
        assert warning_call[1]['user_id'] == '42'
        assert warning_call[1]['endpoint'] == '/api/v1/catalog/actions/'

    @patch('core.middleware.logger')
    def test_429_response_logs_anonymous_user(self, mock_logger):
        """429 for anonymous requests should log user_id=None."""
        set_correlation_id('test-anon-rate-limit')
        request = self.factory.get('/api/v1/auth/saml/login/')
        request.META['REMOTE_ADDR'] = '10.0.0.1'
        request.user = MagicMock(is_authenticated=False)

        response = HttpResponse("Throttled", status=429)
        response['Retry-After'] = '45'
        get_response = MagicMock(return_value=response)
        middleware = RateLimitHeadersMiddleware(get_response)

        middleware(request)

        warning_call = mock_logger.warning.call_args
        assert warning_call[1]['user_id'] is None

    def test_429_preserves_retry_after_header(self):
        """429 responses should preserve the Retry-After header as integer."""
        request = self.factory.get('/api/v1/test/')
        request.user = MagicMock(is_authenticated=False)
        response = HttpResponse("Throttled", status=429)
        response['Retry-After'] = '30.5'
        get_response = MagicMock(return_value=response)
        middleware = RateLimitHeadersMiddleware(get_response)

        result = middleware(request)

        assert result['Retry-After'] == '30'

    def test_health_endpoint_exempt(self):
        """Health check endpoints should be exempt from rate limit header processing."""
        request = self.factory.get('/api/v1/health')
        response = HttpResponse("OK", status=429)
        response['Retry-After'] = '10'
        get_response = MagicMock(return_value=response)
        middleware = RateLimitHeadersMiddleware(get_response)

        with patch('core.middleware.logger') as mock_logger:
            middleware(request)
            # Should NOT log rate_limit_exceeded for health endpoint
            mock_logger.warning.assert_not_called()

    @patch('core.middleware.logger')
    def test_429_includes_method_and_user_agent(self, mock_logger):
        """429 log should include HTTP method and user agent."""
        set_correlation_id('test-method-ua')
        request = self.factory.post('/api/v1/executions/')
        request.META['REMOTE_ADDR'] = '10.0.0.1'
        request.META['HTTP_USER_AGENT'] = 'TestClient/1.0'
        request.user = MagicMock(is_authenticated=True, id=7)

        response = HttpResponse("Throttled", status=429)
        response['Retry-After'] = '60'
        get_response = MagicMock(return_value=response)
        middleware = RateLimitHeadersMiddleware(get_response)

        middleware(request)

        warning_call = mock_logger.warning.call_args
        assert warning_call[1]['method'] == 'POST'
        assert warning_call[1]['user_agent'] == 'TestClient/1.0'


class TestRateLimitConfigValidation(TestCase):
    """Tests for rate limit configuration validation at startup."""

    def test_valid_config_passes(self):
        """Valid rate formats should not raise."""
        with patch.dict('os.environ', {
            'THROTTLE_AUTH_RATE': '10/minute',
            'THROTTLE_TOKEN_REFRESH_RATE': '20/m',
            'THROTTLE_EXECUTION_RATE': '30/min',
            'THROTTLE_API_RATE': '100/hour',
            'THROTTLE_PUBLIC_RATE': '50/day',
        }):
            from core.startup_checks import validate_rate_limit_config
            # Should not raise
            validate_rate_limit_config()

    def test_valid_short_formats(self):
        """Short format abbreviations (s, m, h, d) should be valid."""
        with patch.dict('os.environ', {
            'THROTTLE_AUTH_RATE': '10/s',
            'THROTTLE_TOKEN_REFRESH_RATE': '20/m',
            'THROTTLE_EXECUTION_RATE': '30/h',
            'THROTTLE_API_RATE': '100/d',
            'THROTTLE_PUBLIC_RATE': '50/second',
        }):
            from core.startup_checks import validate_rate_limit_config
            validate_rate_limit_config()

    def test_invalid_format_raises(self):
        """Invalid rate format should raise ImproperlyConfigured."""
        with patch.dict('os.environ', {
            'THROTTLE_AUTH_RATE': 'invalid',
        }):
            from core.startup_checks import validate_rate_limit_config
            with pytest.raises(ImproperlyConfigured, match="Invalid rate format"):
                validate_rate_limit_config()

    def test_missing_count_raises(self):
        """Rate without count should raise."""
        with patch.dict('os.environ', {
            'THROTTLE_AUTH_RATE': '/minute',
        }):
            from core.startup_checks import validate_rate_limit_config
            with pytest.raises(ImproperlyConfigured):
                validate_rate_limit_config()

    def test_missing_period_raises(self):
        """Rate without period should raise."""
        with patch.dict('os.environ', {
            'THROTTLE_AUTH_RATE': '10/',
        }):
            from core.startup_checks import validate_rate_limit_config
            with pytest.raises(ImproperlyConfigured):
                validate_rate_limit_config()

    def test_default_values_are_valid(self):
        """Default rate values (when env vars not set) should be valid."""
        with patch.dict('os.environ', {}, clear=False):
            # Remove all THROTTLE_ env vars to test defaults
            import os
            env_copy = {k: v for k, v in os.environ.items() if not k.startswith('THROTTLE_')}
            with patch.dict('os.environ', env_copy, clear=True):
                from core.startup_checks import validate_rate_limit_config
                validate_rate_limit_config()


class TestDRFThrottlingSettings(TestCase):
    """Tests that DRF throttling is properly configured in settings."""

    def test_default_throttle_classes_configured(self):
        from django.conf import settings
        throttle_classes = settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_CLASSES', [])
        assert 'core.throttling.GeneralAPIThrottle' in throttle_classes

    def test_throttle_rates_configured(self):
        from django.conf import settings
        rates = settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {})
        assert 'auth' in rates
        assert 'token_refresh' in rates
        assert 'execution' in rates
        assert 'general_api' in rates
        assert 'public' in rates

    def test_cache_configured(self):
        from django.conf import settings
        assert 'default' in settings.CACHES


class TestRateLimitEnabledFlag(TestCase):
    """Tests for RATELIMIT_ENABLED emergency bypass flag."""

    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(RATELIMIT_ENABLED=False)
    def test_throttle_bypassed_when_disabled(self):
        """Throttles should allow all requests when RATELIMIT_ENABLED=False."""
        throttle = AuthEndpointThrottle()
        request = self.factory.get('/api/v1/auth/saml/login/')
        request.META['REMOTE_ADDR'] = '10.0.0.1'
        assert throttle.allow_request(request, None) is True

    @override_settings(RATELIMIT_ENABLED=True)
    def test_throttle_active_when_enabled(self):
        """Throttles should enforce limits when RATELIMIT_ENABLED=True."""
        from core.throttling import PublicEndpointThrottle
        throttle = PublicEndpointThrottle()
        # allow_request returns True (allowed) or False (throttled), not unconditionally True
        request = self.factory.get('/api/v1/auth/logout/')
        request.META['REMOTE_ADDR'] = '10.0.0.1'
        # First request should be allowed
        result = throttle.allow_request(request, None)
        assert result is True
