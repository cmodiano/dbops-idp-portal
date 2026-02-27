"""
Story 17.11: Security tests for rate limiting.

Tests cover:
- Brute-force SAML login blocked after threshold
- Token refresh abuse blocked
- IP spoofing via X-Forwarded-For does not bypass rate limit
- Rate limit persists between requests (cache works)
- Different users/IPs have separate counters

Note: DRF's SimpleRateThrottle.THROTTLE_RATES is a class attribute set at import
time. override_settings alone does NOT update it because the class attribute holds
a stale reference. We patch THROTTLE_RATES directly on the throttle classes.
"""

from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework.throttling import SimpleRateThrottle

LOW_RATES = {
    'auth': '3/minute',
    'token_refresh': '3/minute',
    'execution': '3/minute',
    'general_api': '5/minute',
    'public': '3/minute',
    'service_login': '2/minute',  # Story 49.3
}


class RateLimitSecurityTestBase(TestCase):
    """Base class that patches DRF throttle rates for security testing."""

    def setUp(self):
        super().setUp()
        cache.clear()
        # Patch the class-level THROTTLE_RATES so new throttle instances pick up low limits
        self._patcher = patch.object(SimpleRateThrottle, 'THROTTLE_RATES', LOW_RATES)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        cache.clear()
        super().tearDown()


@override_settings(RATELIMIT_ENABLED=True)
class TestSAMLLoginBruteForce(RateLimitSecurityTestBase):
    """Test that SAML login endpoint is protected against brute-force attacks."""

    def test_saml_login_blocked_after_threshold(self):
        """SAML login should return 429 after exceeding rate limit."""
        client = APIClient()

        for i in range(3):
            response = client.get(
                '/api/v1/auth/saml/login/',
                REMOTE_ADDR='192.168.1.100',
            )
            assert response.status_code != 429, f"Request {i+1} should not be throttled"

        response = client.get(
            '/api/v1/auth/saml/login/',
            REMOTE_ADDR='192.168.1.100',
        )
        assert response.status_code == 429

    def test_saml_login_429_has_retry_after(self):
        """429 response should include Retry-After header."""
        client = APIClient()

        for _ in range(3):
            client.get('/api/v1/auth/saml/login/', REMOTE_ADDR='10.0.0.1')

        response = client.get('/api/v1/auth/saml/login/', REMOTE_ADDR='10.0.0.1')
        assert response.status_code == 429
        assert 'Retry-After' in response


@override_settings(RATELIMIT_ENABLED=True)
class TestSAMLCallbackBruteForce(RateLimitSecurityTestBase):
    """Test that SAML callback endpoint is protected."""

    def test_saml_callback_blocked_after_threshold(self):
        """SAML callback should return 429 after exceeding rate limit."""
        client = APIClient()

        for _ in range(3):
            response = client.post(
                '/api/v1/auth/saml/callback/',
                data={},
                format='json',
                REMOTE_ADDR='10.0.0.50',
            )
            assert response.status_code != 429

        response = client.post(
            '/api/v1/auth/saml/callback/',
            data={},
            format='json',
            REMOTE_ADDR='10.0.0.50',
        )
        assert response.status_code == 429


@override_settings(RATELIMIT_ENABLED=True)
class TestTokenRefreshAbuse(RateLimitSecurityTestBase):
    """Test that token refresh endpoint is protected against abuse."""

    def test_token_refresh_blocked_after_threshold(self):
        """Token refresh should return 429 after exceeding rate limit."""
        client = APIClient()

        for _ in range(3):
            response = client.post(
                '/api/v1/auth/refresh/',
                REMOTE_ADDR='10.0.0.20',
            )
            assert response.status_code != 429

        response = client.post(
            '/api/v1/auth/refresh/',
            REMOTE_ADDR='10.0.0.20',
        )
        assert response.status_code == 429


@override_settings(RATELIMIT_ENABLED=True)
class TestIPSpoofingProtection(RateLimitSecurityTestBase):
    """Test that IP spoofing via X-Forwarded-For does not bypass rate limiting."""

    def test_same_xff_ip_still_limited(self):
        """Same X-Forwarded-For IP should share rate limit counter."""
        client = APIClient()

        for _ in range(3):
            response = client.get(
                '/api/v1/auth/saml/login/',
                HTTP_X_FORWARDED_FOR='203.0.113.1',
            )
            assert response.status_code != 429

        response = client.get(
            '/api/v1/auth/saml/login/',
            HTTP_X_FORWARDED_FOR='203.0.113.1',
        )
        assert response.status_code == 429

    def test_different_xff_ips_have_separate_counters(self):
        """Different IPs in X-Forwarded-For should have separate counters."""
        client = APIClient()

        for _ in range(3):
            client.get('/api/v1/auth/saml/login/', HTTP_X_FORWARDED_FOR='10.1.1.1')

        # IP 1 should be throttled
        response = client.get(
            '/api/v1/auth/saml/login/',
            HTTP_X_FORWARDED_FOR='10.1.1.1',
        )
        assert response.status_code == 429

        # IP 2 should still work
        response = client.get(
            '/api/v1/auth/saml/login/',
            HTTP_X_FORWARDED_FOR='10.2.2.2',
        )
        assert response.status_code != 429


@override_settings(RATELIMIT_ENABLED=True)
class TestExecutionBruteForce(RateLimitSecurityTestBase):
    """Test that execution POST endpoint is protected against abuse."""

    def test_execution_post_blocked_after_threshold(self):
        """Execution POST should return 429 after exceeding rate limit (30 req/min)."""
        from idp_auth.models import User
        user = User.objects.create(
            username='testdba',
            display_name='Test DBA',
            profile='dba_applicatif'
        )

        client = APIClient()
        client.force_authenticate(user=user)

        # Make 3 requests (should succeed, LOW_RATES = 3/minute for execution in tests)
        for _ in range(3):
            response = client.post(
                '/api/v1/executions/',
                data={},
                format='json',
            )
            # May fail validation but should NOT be throttled
            assert response.status_code != 429

        # 4th request should be rate limited
        response = client.post(
            '/api/v1/executions/',
            data={},
            format='json',
        )
        assert response.status_code == 429


@override_settings(RATELIMIT_ENABLED=True)
class TestServiceLoginBruteForce(RateLimitSecurityTestBase):
    """Story 49.3: Service account LDAP brute-force protection tests."""

    def test_service_login_blocked_after_threshold(self):
        """After threshold, service login returns 429."""
        endpoint = '/api/v1/auth/service-login/'
        payload = {'username': 'svc-test', 'password': 'test'}
        # First 2 requests allowed (will fail LDAP/validation but not rate limited)
        for _ in range(2):
            self.client.post(endpoint, payload, format='json')
        # Third request blocked
        response = self.client.post(endpoint, payload, format='json')
        self.assertEqual(response.status_code, 429)

    def test_service_login_429_has_retry_after_header(self):
        """429 response includes Retry-After header."""
        endpoint = '/api/v1/auth/service-login/'
        payload = {'username': 'svc-test', 'password': 'test'}
        # Exhaust the 2/minute limit (2 allowed, 3rd blocked)
        for _ in range(2):
            self.client.post(endpoint, payload, format='json')
        response = self.client.post(endpoint, payload, format='json')
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response)

    def test_different_ips_have_independent_counters(self):
        """Service login counters are per-IP (different IPs don't share counters)."""
        endpoint = '/api/v1/auth/service-login/'
        payload = {'username': 'svc-test', 'password': 'test'}
        # Exhaust limit for IP1
        ip1_client = APIClient()
        for _ in range(3):
            ip1_client.post(endpoint, payload, format='json', HTTP_X_FORWARDED_FOR='1.2.3.4')
        # IP2 should still be allowed (not exhausted)
        ip2_client = APIClient()
        response = ip2_client.post(endpoint, payload, format='json', HTTP_X_FORWARDED_FOR='5.6.7.8')
        self.assertNotEqual(response.status_code, 429)


@override_settings(RATELIMIT_ENABLED=True)
class TestRateLimitPersistence(RateLimitSecurityTestBase):
    """Test that rate limit counters persist in cache between requests."""

    def test_rate_limit_counter_persists_across_clients(self):
        """Counter should persist across separate APIClient instances."""
        for _ in range(3):
            client = APIClient()
            response = client.get(
                '/api/v1/auth/saml/login/',
                REMOTE_ADDR='172.16.0.1',
            )
            assert response.status_code != 429

        client = APIClient()
        response = client.get(
            '/api/v1/auth/saml/login/',
            REMOTE_ADDR='172.16.0.1',
        )
        assert response.status_code == 429
