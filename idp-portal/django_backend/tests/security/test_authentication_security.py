"""
Tests d'authentification JWT complets.
Story 15.2 - Task 1 (AC1).

Validates:
- AC1: All protected endpoints return 401 for unauthenticated requests
- AC1: Expired JWT returns 401 with appropriate error
- AC1: Invalid/malformed JWT tokens are rejected with 401
- AC1: Refresh token flow works correctly
- NFR9: Sessions expire after configured inactivity period
"""

import pytest
from django.test import override_settings
from rest_framework import status

from tests.security.conftest import make_auth_client


# ============================================================================
# Subtask 1.2: Protected endpoints return 401 without token
# ============================================================================

# Endpoints that require IsAuthenticated (return 401 without auth)
# Note: All URLs use trailing slash to avoid Django APPEND_SLASH 301 redirect
PROTECTED_ENDPOINTS = [
    ('GET', '/api/v1/auth/me/'),
    ('GET', '/api/v1/users/me/favorites/'),
    ('GET', '/api/v1/executions/'),
    ('POST', '/api/v1/executions/'),
    ('GET', '/api/v1/executions/stats/'),
    ('GET', '/api/v1/executions/timeseries/'),
    ('GET', '/api/v1/executions/tags/'),
    ('GET', '/api/v1/executions/pending-approvals/'),
    ('GET', '/api/v1/scheduled-executions/'),
    ('POST', '/api/v1/scheduled-executions/'),
    ('GET', '/api/v1/dashboard/stats/'),
    ('GET', '/api/v1/dashboard/recent/'),
    ('GET', '/api/v1/dashboard/timeseries/'),
    ('GET', '/api/v1/dashboard/stats-by-technology/'),
    ('GET', '/api/v1/dashboard/stats-by-environment/'),
    ('GET', '/api/v1/dashboard/compare/'),
    ('GET', '/api/v1/dashboard/filter-options/'),
    ('GET', '/api/v1/audit/executions/'),
    ('GET', '/api/v1/audit/export/'),
    ('GET', '/api/v1/inventory/targets/'),
    ('GET', '/api/v1/inventory/environments/'),
    # Admin endpoints (IsAuthenticated + AdminProfilePermission)
    ('GET', '/api/v1/admin/actions/'),
    ('POST', '/api/v1/admin/actions/'),
    ('GET', '/api/v1/admin/profiles/'),
    ('POST', '/api/v1/admin/profiles/'),
    ('GET', '/api/v1/admin/integrations/'),
    ('POST', '/api/v1/admin/integrations/'),
]

# Endpoints that allow anonymous access (should NOT return 401)
# Note: POST /auth/refresh returns 401 when no cookie is present (business logic),
# but the permission class is AllowAny — the 401 comes from the view, not DRF auth.
# We test refresh flow separately in TestRefreshTokenFlow.
PUBLIC_ENDPOINTS = [
    ('GET', '/api/v1/health/'),
    ('GET', '/api/v1/auth/saml/login/'),
    ('POST', '/api/v1/auth/logout/'),
    ('GET', '/api/v1/catalog/actions/'),
    ('GET', '/api/v1/tags/'),
]


@pytest.mark.django_db
@pytest.mark.security
class TestProtectedEndpointsRequireAuth:
    """All protected endpoints must return 401 for unauthenticated requests."""

    @pytest.mark.parametrize('method,url', PROTECTED_ENDPOINTS)
    def test_unauthenticated_returns_401(self, anon_client, method, url):
        """Protected endpoint returns 401 without Authorization header."""
        response = getattr(anon_client, method.lower())(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, (
            f'{method} {url} returned {response.status_code}, expected 401'
        )

    @pytest.mark.parametrize('method,url', PUBLIC_ENDPOINTS)
    def test_public_endpoint_does_not_require_auth(self, anon_client, method, url):
        """Public endpoints do not return 401."""
        response = getattr(anon_client, method.lower())(url)
        assert response.status_code != status.HTTP_401_UNAUTHORIZED, (
            f'{method} {url} returned 401 but should be accessible without auth'
        )


# ============================================================================
# Subtask 1.3: Expired JWT tokens return 401
# ============================================================================

@pytest.mark.django_db
@pytest.mark.security
class TestExpiredTokenRejected:
    """Expired JWT tokens must be rejected with 401."""

    def test_expired_access_token_returns_401(self, expired_access_token):
        """An expired access token must return 401."""
        client = make_auth_client(expired_access_token)
        response = client.get('/api/v1/auth/me/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_expired_token_error_message(self, expired_access_token):
        """Expired token 401 response contains an error message."""
        client = make_auth_client(expired_access_token)
        response = client.get('/api/v1/auth/me/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        # Custom exception handler wraps errors in {'error': {'code': ..., 'message': ...}}
        assert 'error' in data
        assert 'message' in data['error']


# ============================================================================
# Subtask 1.4: Invalid/malformed JWT tokens
# ============================================================================

@pytest.mark.django_db
@pytest.mark.security
class TestMalformedTokenRejected:
    """Invalid or malformed JWT tokens must be rejected with 401."""

    def test_wrong_signature_returns_401(self, wrong_signature_token):
        """Token signed with a different key is rejected."""
        client = make_auth_client(wrong_signature_token)
        response = client.get('/api/v1/auth/me/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_corrupted_token_returns_401(self, corrupted_token):
        """Garbage / non-JWT string is rejected."""
        client = make_auth_client(corrupted_token)
        response = client.get('/api/v1/auth/me/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_token_as_access_returns_401(self, refresh_used_as_access_token):
        """A refresh token used in Authorization header is rejected (type mismatch)."""
        client = make_auth_client(refresh_used_as_access_token)
        response = client.get('/api/v1/auth/me/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_tampered_payload_nonexistent_user_returns_401(self, tampered_payload_token):
        """Token with a valid signature but non-existent user_id returns 401."""
        client = make_auth_client(tampered_payload_token)
        response = client.get('/api/v1/auth/me/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_empty_bearer_returns_401(self, anon_client):
        """Bearer header with empty token value."""
        anon_client.credentials(HTTP_AUTHORIZATION='Bearer ')
        response = anon_client.get('/api/v1/auth/me/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_no_bearer_prefix_ignored(self, anon_client, sec_dba_token):
        """Token without 'Bearer ' prefix is not recognized (returns 401)."""
        anon_client.credentials(HTTP_AUTHORIZATION=sec_dba_token)
        response = anon_client.get('/api/v1/auth/me/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ============================================================================
# Subtask 1.5: Refresh token flow
# ============================================================================

@pytest.mark.django_db
@pytest.mark.security
class TestRefreshTokenFlow:
    """Refresh token exchange via httpOnly cookie."""

    def test_valid_refresh_returns_new_access_token(self, anon_client, sec_dba_refresh_token):
        """POST /auth/refresh with valid refresh cookie returns new access token."""
        anon_client.cookies['refresh_token'] = sec_dba_refresh_token
        response = anon_client.post('/api/v1/auth/refresh/')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert 'data' in data
        assert 'access_token' in data['data']
        assert data['data']['token_type'] == 'bearer'

    def test_new_access_token_is_usable(self, anon_client, sec_dba_refresh_token):
        """New access token obtained via refresh can authenticate requests."""
        anon_client.cookies['refresh_token'] = sec_dba_refresh_token
        response = anon_client.post('/api/v1/auth/refresh/')
        new_token = response.json()['data']['access_token']

        auth_client = make_auth_client(new_token)
        me_response = auth_client.get('/api/v1/auth/me/')
        assert me_response.status_code == status.HTTP_200_OK

    def test_missing_refresh_cookie_returns_401(self, anon_client):
        """POST /auth/refresh without cookie returns 401."""
        response = anon_client.post('/api/v1/auth/refresh/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_invalid_refresh_cookie_returns_401(self, anon_client):
        """POST /auth/refresh with garbage cookie returns 401."""
        anon_client.cookies['refresh_token'] = 'not-a-valid-refresh-token'
        response = anon_client.post('/api/v1/auth/refresh/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_access_token_as_refresh_returns_401(self, anon_client, sec_dba_token):
        """Using an access token as refresh token (type mismatch) returns 401."""
        anon_client.cookies['refresh_token'] = sec_dba_token
        response = anon_client.post('/api/v1/auth/refresh/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ============================================================================
# Subtask 1.6: Session expiration after inactivity (NFR9)
# ============================================================================

@pytest.mark.django_db
@pytest.mark.security
class TestSessionExpiration:
    """NFR9: Sessions expire after configured inactivity period."""

    def test_default_access_token_ttl_is_30_minutes(self, settings):
        """Verify configured token TTL matches NFR9 requirement."""
        assert settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES == 30

    def test_expired_token_simulates_session_timeout(self, expired_access_token):
        """After token expiration (simulating inactivity), requests are rejected."""
        client = make_auth_client(expired_access_token)
        response = client.get('/api/v1/auth/me/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_negative_ttl_immediately_expires(self, sec_dba_user, settings):
        """Token created with negative delta is already expired."""
        from datetime import timedelta
        from idp_auth.jwt_utils import create_access_token
        token = create_access_token(
            {
                'sub': str(sec_dba_user.id),
                'username': sec_dba_user.username,
                'profile': sec_dba_user.profile,
                'ad_groups': ['dba'],
            },
            expires_delta=timedelta(seconds=-1),
        )
        client = make_auth_client(token)
        response = client.get('/api/v1/auth/me/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ============================================================================
# Subtask 1.7: Dev bypass token
# ============================================================================

@pytest.mark.django_db
@pytest.mark.security
class TestDevBypassToken:
    """AUTH_DEV_BYPASS mode allows dev-mock-token-for-testing."""

    @override_settings(AUTH_DEV_BYPASS=True)
    def test_dev_bypass_token_accepted_when_enabled(self, anon_client):
        """dev-mock-token is accepted when AUTH_DEV_BYPASS=True."""
        anon_client.credentials(HTTP_AUTHORIZATION='Bearer dev-mock-token-for-testing')
        response = anon_client.get('/api/v1/auth/me/')
        assert response.status_code == status.HTTP_200_OK

    @override_settings(AUTH_DEV_BYPASS=False)
    def test_dev_bypass_token_rejected_when_disabled(self, anon_client):
        """dev-mock-token is rejected when AUTH_DEV_BYPASS=False."""
        anon_client.credentials(HTTP_AUTHORIZATION='Bearer dev-mock-token-for-testing')
        response = anon_client.get('/api/v1/auth/me/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @override_settings(AUTH_DEV_BYPASS=True)
    def test_dev_bypass_user_has_dbops_profile(self, anon_client):
        """Dev bypass user is created with dbops profile."""
        anon_client.credentials(HTTP_AUTHORIZATION='Bearer dev-mock-token-for-testing')
        response = anon_client.get('/api/v1/auth/me/')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()['data']
        assert data['profile'] == 'dbops'

    @override_settings(AUTH_DEV_BYPASS=False)
    def test_random_mock_token_always_rejected(self, anon_client):
        """A random string that is not the known mock token is always rejected."""
        anon_client.credentials(HTTP_AUTHORIZATION='Bearer some-other-mock-token')
        response = anon_client.get('/api/v1/auth/me/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
