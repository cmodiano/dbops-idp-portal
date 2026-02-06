"""
Tests des headers de sécurité et middleware.
Story 15.2 - Task 5 (AC1, AC2).

Validates:
- AC1/AC2: Security headers present on all responses
- AC1: Cache-Control no-store on API endpoints
- AC1: Correlation ID propagation in responses
- NFR10: Audit middleware logs 401 on auth endpoints
"""

import uuid

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from tests.security.conftest import make_auth_client


# ============================================================================
# Subtask 5.2: Security headers present
# ============================================================================

@pytest.mark.django_db
@pytest.mark.security
class TestSecurityHeaders:
    """Security headers are present on all API responses."""

    def test_x_content_type_options_nosniff(self, anon_client):
        """X-Content-Type-Options: nosniff is present."""
        response = anon_client.get('/api/v1/health')
        assert response.get('X-Content-Type-Options') == 'nosniff'

    def test_x_frame_options_deny(self, anon_client):
        """X-Frame-Options: DENY is present."""
        response = anon_client.get('/api/v1/health')
        assert response.get('X-Frame-Options') == 'DENY'

    def test_x_xss_protection(self, anon_client):
        """X-XSS-Protection: 1; mode=block is present."""
        response = anon_client.get('/api/v1/health')
        assert response.get('X-XSS-Protection') == '1; mode=block'

    def test_referrer_policy(self, anon_client):
        """Referrer-Policy: strict-origin-when-cross-origin is present."""
        response = anon_client.get('/api/v1/health')
        assert response.get('Referrer-Policy') == 'strict-origin-when-cross-origin'

    def test_headers_on_401_response(self, anon_client):
        """Security headers are present even on 401 responses."""
        response = anon_client.get('/api/v1/auth/me')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.get('X-Content-Type-Options') == 'nosniff'
        assert response.get('X-Frame-Options') == 'DENY'

    def test_headers_on_authenticated_response(self, sec_dba_token):
        """Security headers are present on authenticated responses."""
        client = make_auth_client(sec_dba_token)
        response = client.get('/api/v1/auth/me')
        assert response.status_code == status.HTTP_200_OK
        assert response.get('X-Content-Type-Options') == 'nosniff'
        assert response.get('X-Frame-Options') == 'DENY'
        assert response.get('X-XSS-Protection') == '1; mode=block'
        assert response.get('Referrer-Policy') == 'strict-origin-when-cross-origin'


# ============================================================================
# Subtask 5.3: Cache-Control no-store on API endpoints
# ============================================================================

@pytest.mark.django_db
@pytest.mark.security
class TestCacheControl:
    """API endpoints have Cache-Control: no-store."""

    def test_api_response_no_store(self, anon_client):
        """API responses include Cache-Control: no-store."""
        response = anon_client.get('/api/v1/health')
        cache_control = response.get('Cache-Control', '')
        assert 'no-store' in cache_control

    def test_api_response_pragma_no_cache(self, anon_client):
        """API responses include Pragma: no-cache."""
        response = anon_client.get('/api/v1/health')
        assert response.get('Pragma') == 'no-cache'

    def test_authenticated_api_no_store(self, sec_dba_token):
        """Authenticated API responses also have Cache-Control: no-store."""
        client = make_auth_client(sec_dba_token)
        response = client.get('/api/v1/auth/me')
        cache_control = response.get('Cache-Control', '')
        assert 'no-store' in cache_control

    def test_cache_control_on_error_response(self, anon_client):
        """Error responses also have Cache-Control: no-store."""
        response = anon_client.get('/api/v1/auth/me')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        cache_control = response.get('Cache-Control', '')
        assert 'no-store' in cache_control


# ============================================================================
# Subtask 5.4: Correlation ID propagation
# ============================================================================

@pytest.mark.django_db
@pytest.mark.security
class TestCorrelationIdPropagation:
    """X-Idp-Request-Id is generated and propagated in responses."""

    def test_correlation_id_in_response(self, anon_client):
        """Response contains X-Idp-Request-Id header."""
        response = anon_client.get('/api/v1/health')
        correlation_id = response.get('X-Idp-Request-Id')
        assert correlation_id is not None
        assert len(correlation_id) > 0

    def test_correlation_id_is_uuid_format(self, anon_client):
        """Correlation ID is a valid UUID."""
        response = anon_client.get('/api/v1/health')
        correlation_id = response.get('X-Idp-Request-Id')
        # Should be parseable as UUID
        parsed = uuid.UUID(correlation_id)
        assert str(parsed) == correlation_id

    def test_custom_correlation_id_propagated(self, anon_client):
        """When X-Idp-Request-Id is provided, it is echoed back."""
        custom_id = str(uuid.uuid4())
        response = anon_client.get(
            '/api/v1/health',
            HTTP_X_IDP_REQUEST_ID=custom_id,
        )
        assert response.get('X-Idp-Request-Id') == custom_id

    def test_correlation_id_on_error(self, anon_client):
        """Correlation ID is present even on error responses."""
        response = anon_client.get('/api/v1/auth/me')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.get('X-Idp-Request-Id') is not None

    def test_unique_correlation_per_request(self, anon_client):
        """Each request gets a unique correlation ID."""
        r1 = anon_client.get('/api/v1/health')
        r2 = anon_client.get('/api/v1/health')
        id1 = r1.get('X-Idp-Request-Id')
        id2 = r2.get('X-Idp-Request-Id')
        assert id1 != id2


# ============================================================================
# Subtask 5.5: Audit middleware on 401/403
# ============================================================================

@pytest.mark.django_db
@pytest.mark.security
class TestAuditMiddleware:
    """AuditAuthMiddleware logs 401 on /api/v1/auth paths."""

    def test_401_on_auth_endpoint_logged(self, anon_client, caplog):
        """401 on /api/v1/auth/* triggers audit log."""
        import structlog
        # Use caplog to capture structlog output
        with caplog.at_level('WARNING'):
            response = anon_client.get('/api/v1/auth/me')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        # AuditAuthMiddleware logs "auth_unauthorized_access" at WARNING level
        assert any(
            'auth_unauthorized_access' in record.message
            for record in caplog.records
        )

    def test_401_on_non_auth_endpoint_not_logged(self, anon_client, caplog):
        """401 on non-auth endpoint does NOT trigger AuditAuthMiddleware."""
        with caplog.at_level('WARNING'):
            response = anon_client.get('/api/v1/executions')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        # AuditAuthMiddleware only logs for /api/v1/auth paths
        auth_audit_records = [
            r for r in caplog.records
            if 'auth_unauthorized_access' in r.message
        ]
        assert len(auth_audit_records) == 0
