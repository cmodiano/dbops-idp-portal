"""
Story 30.5 — SEC-7 / Story 59.6 — SEC-6: AUTH_DEV_BYPASS production guard tests.
SEC-7: SAML login view logs CRITICAL when dev bypass is active with DEBUG=False.
SEC-6: JWTAuthentication blocks dev bypass in production (returns None → 401).
"""

import pytest
from unittest.mock import patch, MagicMock
from django.test import override_settings
from rest_framework.test import APIClient


@pytest.fixture
def api_client(db):
    return APIClient()


@pytest.mark.django_db
class TestDevBypassGuardSAMLLogin:
    """SEC-7: SAMLLoginView.get() must log CRITICAL when AUTH_DEV_BYPASS + DEBUG=False."""

    @override_settings(AUTH_DEV_BYPASS=True, DEBUG=False)
    def test_dev_bypass_in_production_logs_critical(self, api_client):
        """AUTH_DEV_BYPASS=True + DEBUG=False must emit CRITICAL log."""
        with patch('idp_auth.views.saml.logger') as mock_logger:
            response = api_client.get('/api/v1/auth/saml/login/')
            # Should still work (redirect) but log CRITICAL
            assert response.status_code in (301, 302)
            mock_logger.critical.assert_called_once()
            call_args = mock_logger.critical.call_args[0][0]
            assert 'SECURITY ALERT' in call_args
            assert 'AUTH_DEV_BYPASS' in call_args

    @override_settings(AUTH_DEV_BYPASS=True, DEBUG=True)
    def test_dev_bypass_in_debug_no_critical_log(self, api_client):
        """AUTH_DEV_BYPASS=True + DEBUG=True must NOT emit CRITICAL log."""
        with patch('idp_auth.views.saml.logger') as mock_logger:
            response = api_client.get('/api/v1/auth/saml/login/')
            assert response.status_code in (301, 302)
            mock_logger.critical.assert_not_called()

    @override_settings(AUTH_DEV_BYPASS=False)
    def test_no_bypass_no_critical_log(self, api_client):
        """AUTH_DEV_BYPASS=False must NOT emit CRITICAL log (normal SAML flow)."""
        with patch('idp_auth.views.saml.logger') as mock_logger:
            with patch('idp_auth.views.saml.create_saml_auth') as mock_saml:
                mock_auth = MagicMock()
                mock_auth.login.return_value = 'https://idp.example.com/sso'
                mock_saml.return_value = mock_auth
                response = api_client.get('/api/v1/auth/saml/login/')
                assert response.status_code in (301, 302)
                mock_logger.critical.assert_not_called()


@pytest.mark.django_db
class TestDevBypassGuardJWTAuthentication:
    """SEC-6: JWTAuthentication.authenticate() must block dev bypass in production (DEBUG=False)."""

    @override_settings(AUTH_DEV_BYPASS=True, DEBUG=False)
    def test_jwt_dev_bypass_production_returns_none(self, api_client):
        """Mock token with AUTH_DEV_BYPASS + DEBUG=False must return None (401)."""
        with patch('idp_auth.authentication.logger') as mock_logger:
            # Use dev mock token
            api_client.credentials(HTTP_AUTHORIZATION='Bearer dev-mock-token-for-testing')
            # Access any authenticated endpoint
            response = api_client.get('/api/v1/auth/me/')
            # SEC-6: authenticate() returns None → DRF responds 401
            assert response.status_code == 401
            mock_logger.critical.assert_not_called()

    @override_settings(AUTH_DEV_BYPASS=True, DEBUG=True)
    def test_jwt_dev_bypass_debug_no_critical(self, api_client):
        """Mock token with AUTH_DEV_BYPASS + DEBUG=True must NOT log CRITICAL, must create audit entry."""
        with patch('idp_auth.authentication.logger') as mock_logger:
            with patch('idp_auth.authentication.AuditService') as mock_audit:
                api_client.credentials(HTTP_AUTHORIZATION='Bearer dev-mock-token-for-testing')
                api_client.get('/api/v1/auth/me/')
                mock_logger.critical.assert_not_called()
                # SEC-6: audit entry must be created for dev bypass in dev mode (AC-2)
                mock_audit.create_entry.assert_called_once()
