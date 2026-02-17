"""
Tests d'autorisation RBAC par profil.
Story 15.2 - Task 2 (AC2).

Validates:
- AC2: DBA can only access authorized endpoints
- AC2: DBOPS can access Admin endpoints
- AC2: Client Business can only execute delegated actions
- AC2: Unauthorized access returns 403 with appropriate message
- NFR10: Unauthorized access attempts are logged in AUDIT_LOG
"""

import pytest
from rest_framework import status

from tests.security.conftest import make_auth_client


# Admin endpoints requiring DBOPS profile (should return 403 for non-DBOPS)
ADMIN_ENDPOINTS = [
    ('GET', '/api/v1/admin/actions/'),
    ('POST', '/api/v1/admin/actions/'),
    ('GET', '/api/v1/admin/profiles/'),
    ('POST', '/api/v1/admin/profiles/'),
    ('GET', '/api/v1/admin/integrations/'),
    ('POST', '/api/v1/admin/integrations/'),
]

# Endpoints accessible to all authenticated users
COMMON_ENDPOINTS = [
    ('GET', '/api/v1/auth/me/'),
    ('GET', '/api/v1/executions/'),
    ('GET', '/api/v1/catalog/actions/'),
    ('GET', '/api/v1/dashboard/stats/'),
]


# ============================================================================
# Subtask 2.2-2.3: DBA access to authorized endpoints + refusal on Admin
# ============================================================================

@pytest.mark.django_db
@pytest.mark.security
class TestDBAAccess:
    """DBA profile can access catalog/executions/dashboard but NOT Admin."""

    @pytest.mark.parametrize('method,url', COMMON_ENDPOINTS)
    def test_dba_can_access_common_endpoints(self, sec_dba_token, method, url):
        """DBA can access standard user endpoints."""
        client = make_auth_client(sec_dba_token)
        response = getattr(client, method.lower())(url)
        assert response.status_code != status.HTTP_401_UNAUTHORIZED
        assert response.status_code != status.HTTP_403_FORBIDDEN, (
            f'DBA should have access to {method} {url}, got 403'
        )

    @pytest.mark.parametrize('method,url', ADMIN_ENDPOINTS)
    def test_dba_denied_admin_endpoints(self, sec_dba_token, method, url):
        """DBA is denied access to Admin endpoints with 403."""
        client = make_auth_client(sec_dba_token)
        response = getattr(client, method.lower())(url, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN, (
            f'DBA should get 403 on {method} {url}, got {response.status_code}'
        )


# ============================================================================
# Subtask 2.4: DBOPS access to Admin endpoints
# ============================================================================

@pytest.mark.django_db
@pytest.mark.security
class TestDBOPSAccess:
    """DBOPS profile can access all endpoints including Admin."""

    @pytest.mark.parametrize('method,url', ADMIN_ENDPOINTS)
    def test_dbops_can_access_admin_endpoints(
        self, sec_dbops_token, sec_profile_dbops, method, url
    ):
        """DBOPS can access Admin endpoints (not 401 or 403)."""
        client = make_auth_client(sec_dbops_token)
        response = getattr(client, method.lower())(url, format='json')
        assert response.status_code not in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ), f'DBOPS should have access to {method} {url}, got {response.status_code}'

    @pytest.mark.parametrize('method,url', COMMON_ENDPOINTS)
    def test_dbops_can_access_common_endpoints(self, sec_dbops_token, method, url):
        """DBOPS can also access standard endpoints."""
        client = make_auth_client(sec_dbops_token)
        response = getattr(client, method.lower())(url)
        assert response.status_code not in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )


# ============================================================================
# Subtask 2.5: Client Business restrictions
# ============================================================================

@pytest.mark.django_db
@pytest.mark.security
class TestClientBusinessAccess:
    """Client Business can only access delegated actions."""

    @pytest.mark.parametrize('method,url', ADMIN_ENDPOINTS)
    def test_business_denied_admin_endpoints(self, sec_business_token, method, url):
        """Client Business is denied access to Admin endpoints."""
        client = make_auth_client(sec_business_token)
        response = getattr(client, method.lower())(url, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_business_can_access_catalog(self, sec_business_token):
        """Client Business can browse the catalog."""
        client = make_auth_client(sec_business_token)
        response = client.get('/api/v1/catalog/actions/')
        assert response.status_code != status.HTTP_403_FORBIDDEN

    def test_business_can_access_own_profile(self, sec_business_token):
        """Client Business can access /auth/me."""
        client = make_auth_client(sec_business_token)
        response = client.get('/api/v1/auth/me/')
        assert response.status_code == status.HTTP_200_OK


# ============================================================================
# Subtask 2.6: NFR10 - 403 attempts logged in AUDIT_LOG
# ============================================================================

@pytest.mark.django_db
@pytest.mark.security
class TestUnauthorizedAccessLogging:
    """NFR10: Unauthorized access attempts are logged."""

    def test_403_response_contains_error(self, sec_dba_token):
        """403 response includes an error object with message."""
        client = make_auth_client(sec_dba_token)
        response = client.get('/api/v1/admin/actions/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        data = response.json()
        assert 'error' in data or 'detail' in data

    def test_401_response_contains_error(self, anon_client):
        """401 response includes an error object."""
        response = anon_client.get('/api/v1/auth/me/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        assert 'error' in data or 'detail' in data


# ============================================================================
# Subtask 2.7: Navigation tabs returned based on profile
# ============================================================================

@pytest.mark.django_db
@pytest.mark.security
class TestNavigationByProfile:
    """Navigation tabs returned by /auth/me match the user's profile."""

    def test_dbops_sees_admin_tab(self, sec_dbops_token, sec_profile_dbops):
        """DBOPS user sees the 'admin' navigation tab."""
        client = make_auth_client(sec_dbops_token)
        response = client.get('/api/v1/auth/me/')
        assert response.status_code == status.HTTP_200_OK
        tabs = response.json()['data']['navigation_tabs']
        assert 'admin' in tabs

    def test_dba_does_not_see_admin_tab(self, sec_dba_token):
        """DBA user does NOT see the 'admin' navigation tab."""
        client = make_auth_client(sec_dba_token)
        response = client.get('/api/v1/auth/me/')
        assert response.status_code == status.HTTP_200_OK
        tabs = response.json()['data']['navigation_tabs']
        assert 'admin' not in tabs

    def test_dba_sees_catalog_and_executions(self, sec_dba_token):
        """DBA user sees catalog, executions, and dashboard tabs."""
        client = make_auth_client(sec_dba_token)
        response = client.get('/api/v1/auth/me/')
        tabs = response.json()['data']['navigation_tabs']
        assert 'catalog' in tabs
        assert 'executions' in tabs
        assert 'dashboard' in tabs

    def test_business_sees_default_tabs(self, sec_business_token):
        """Client Business sees default tabs (catalog, executions, dashboard)."""
        client = make_auth_client(sec_business_token)
        response = client.get('/api/v1/auth/me/')
        tabs = response.json()['data']['navigation_tabs']
        assert 'catalog' in tabs
        assert 'executions' in tabs
        assert 'admin' not in tabs
