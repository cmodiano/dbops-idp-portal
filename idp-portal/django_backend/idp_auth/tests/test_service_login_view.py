"""
Tests unitaires pour ServiceLoginView — POST /api/v1/auth/service-login/
Story 49.2 : Backend endpoint authentification compte de service (username+password → JWT).
"""

import pytest
from unittest.mock import MagicMock, patch
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

ENDPOINT = '/api/v1/auth/service-login/'


class TestServiceLoginView(TestCase):
    """Tests for POST /auth/service-login/ endpoint."""

    def setUp(self):
        self.client = APIClient()

    # ---------- AC1, AC5, AC6, AC7 : Succès 200 ----------

    @patch('idp_auth.views.AuditService')
    @patch('idp_auth.views.create_refresh_token', return_value='mock-refresh-token')
    @patch('idp_auth.views.create_access_token', return_value='mock-access-token')
    @patch('idp_auth.views.AuthService')
    @patch('idp_auth.views.Profile')
    @patch('idp_auth.views.LDAPService')
    def test_success_returns_200_with_access_token(
        self, mock_ldap_class, mock_profile, mock_auth_service_class,
        mock_create_access, mock_create_refresh, mock_audit
    ):
        """AC1 + AC5 + AC6 + AC7 : 200, access_token, cookie refresh_token."""
        # Arrange
        mock_ldap = mock_ldap_class.return_value
        mock_ldap.authenticate.return_value = (
            True,
            ['CN=GRP-IDP-DBOPS,OU=Groups,DC=example,DC=com'],
            'Service CI',
        )

        mock_profile_obj = MagicMock()
        mock_profile_obj.name = 'DBOPS'
        mock_profile.objects.find_by_ad_groups.return_value = [mock_profile_obj]

        mock_user = MagicMock()
        mock_user.id = 42
        mock_user.username = 'svc-ci-cd'
        mock_user.profile = 'dbops'
        mock_auth_service_class.return_value.create_or_update_user.return_value = mock_user

        # Act
        response = self.client.post(
            ENDPOINT,
            {'username': 'svc-ci-cd', 'password': 'secret'},
            format='json',
        )

        # Assert status + body
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertEqual(response.data['data']['access_token'], 'mock-access-token')
        self.assertEqual(response.data['data']['token_type'], 'Bearer')
        self.assertIn('expires_in', response.data['data'])

        # Assert refresh cookie présent et propriétés correctes
        self.assertIn('refresh_token', response.cookies)
        cookie = response.cookies['refresh_token']
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'], 'Lax')
        self.assertEqual(cookie['path'], '/api/v1/auth')

        # Assert JIT user creation called with correct args
        mock_auth_service_class.return_value.create_or_update_user.assert_called_once_with(
            username='svc-ci-cd',
            display_name='Service CI',
            profile='dbops',
            saml_subject=None,
        )

        # Assert token built with correct claims
        mock_create_access.assert_called_once_with({
            'sub': '42',
            'username': 'svc-ci-cd',
            'profile': 'dbops',
            'ad_groups': ['CN=GRP-IDP-DBOPS,OU=Groups,DC=example,DC=com'],
        })

        # Assert audit success appelé (AC10)
        mock_audit.create_entry.assert_called_once()
        audit_kwargs = mock_audit.create_entry.call_args.kwargs
        self.assertTrue(audit_kwargs['details']['success'])
        self.assertEqual(audit_kwargs['details']['username'], 'svc-ci-cd')

    # ---------- AC2 : Credentials invalides → 401 ----------

    @patch('idp_auth.views.AuditService')
    @patch('idp_auth.views.LDAPService')
    def test_invalid_credentials_returns_401(self, mock_ldap_class, mock_audit):
        """AC2 : LDAP bind échoue → 401 INVALID_CREDENTIALS."""
        mock_ldap = mock_ldap_class.return_value
        mock_ldap.authenticate.return_value = (False, [], None)

        response = self.client.post(
            ENDPOINT,
            {'username': 'svc', 'password': 'wrong'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data['error']['code'], 'INVALID_CREDENTIALS')

        # Audit appelé pour l'échec
        mock_audit.create_entry.assert_called_once()
        call_kwargs = mock_audit.create_entry.call_args.kwargs
        self.assertFalse(call_kwargs['details']['success'])
        self.assertEqual(call_kwargs['details']['reason'], 'invalid_credentials')

    # ---------- AC3 : Aucun profil AD → 403 ----------

    @patch('idp_auth.views.AuditService')
    @patch('idp_auth.views.Profile')
    @patch('idp_auth.views.LDAPService')
    def test_no_profile_returns_403(self, mock_ldap_class, mock_profile, mock_audit):
        """AC3 : Aucun profil associé aux groupes AD → 403 NO_PROFILE."""
        mock_ldap = mock_ldap_class.return_value
        mock_ldap.authenticate.return_value = (True, ['CN=UNKNOWN-GROUP,DC=example,DC=com'], None)
        mock_profile.objects.find_by_ad_groups.return_value = []

        response = self.client.post(
            ENDPOINT,
            {'username': 'svc', 'password': 'pass'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['error']['code'], 'NO_PROFILE')

    # ---------- AC4 : LDAP indisponible → 503 ----------

    @patch('idp_auth.views.AuditService')
    @patch('idp_auth.views.LDAPService')
    def test_ldap_unavailable_returns_503(self, mock_ldap_class, mock_audit):
        """AC4 : LDAPUnavailableError levée → 503 LDAP_UNAVAILABLE."""
        from idp_auth.ldap_service import LDAPUnavailableError
        mock_ldap = mock_ldap_class.return_value
        mock_ldap.authenticate.side_effect = LDAPUnavailableError('LDAP_URI non configuré')

        response = self.client.post(
            ENDPOINT,
            {'username': 'svc', 'password': 'pass'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data['error']['code'], 'LDAP_UNAVAILABLE')

        # Audit appelé pour l'échec
        mock_audit.create_entry.assert_called_once()
        call_kwargs = mock_audit.create_entry.call_args.kwargs
        self.assertEqual(call_kwargs['details']['reason'], 'ldap_unavailable')

    # ---------- Validation sérializer → 400 ----------

    def test_missing_password_returns_400(self):
        """AC1/AC8 : Body incomplet (password manquant) → 400."""
        response = self.client.post(ENDPOINT, {'username': 'svc'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_empty_body_returns_400(self):
        """AC1 : Body vide → 400."""
        response = self.client.post(ENDPOINT, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_username_returns_400(self):
        """AC1 : Body sans username → 400."""
        response = self.client.post(ENDPOINT, {'password': 'secret'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ---------- AC9 : Rate limiting ----------

    def test_throttle_class_is_configured(self):
        """AC9 : AuthEndpointThrottle actif sur ServiceLoginView."""
        from idp_auth.views import ServiceLoginView
        from core.throttling import AuthEndpointThrottle
        self.assertIn(AuthEndpointThrottle, ServiceLoginView.throttle_classes)

    @patch('idp_auth.views.AuditService')
    @patch('idp_auth.views.LDAPService')
    def test_throttle_applied_on_request(self, mock_ldap_class, mock_audit):
        """AC9 : Le throttle est évalué pour chaque requête (mock throttle → 429)."""
        from core.throttling import ServiceLoginThrottle

        mock_ldap = mock_ldap_class.return_value
        mock_ldap.authenticate.return_value = (False, [], None)

        with patch.object(ServiceLoginThrottle, 'allow_request', return_value=False):
            response = self.client.post(
                ENDPOINT,
                {'username': 'svc', 'password': 'pass'},
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


# ---------- AC8 : Password non loggué — tests pytest standalone ----------
# Note: caplog est incompatible avec unittest.TestCase (learning 49.1).
# On utilise des fonctions pytest standalone avec mock du logger.

@pytest.mark.django_db
@patch('idp_auth.views.AuditService')
@patch('idp_auth.views.LDAPService')
def test_password_not_in_structlog_on_invalid_credentials(mock_ldap_class, mock_audit):
    """AC8 : Le password n'apparaît dans aucun appel structlog lors d'un échec."""
    from rest_framework.test import APIClient

    mock_ldap = mock_ldap_class.return_value
    mock_ldap.authenticate.return_value = (False, [], None)

    log_calls = []

    def capture_log(*args, **kwargs):
        log_calls.append(kwargs)

    with patch('idp_auth.views.logger') as mock_logger:
        bound_logger = MagicMock()
        mock_logger.bind.return_value = bound_logger
        bound_logger.warning.side_effect = capture_log

        client = APIClient()
        client.post(ENDPOINT, {'username': 'svc', 'password': 'secret-password'}, format='json')

    # Aucun appel de log ne doit contenir 'secret-password'
    for call_kwargs in log_calls:
        for value in call_kwargs.values():
            assert 'secret-password' not in str(value), (
                f"Le password a été loggué dans: {call_kwargs}"
            )


@pytest.mark.django_db
@patch('idp_auth.views.AuditService')
@patch('idp_auth.views.LDAPService')
def test_password_not_in_structlog_on_ldap_unavailable(mock_ldap_class, mock_audit):
    """AC8 : Le password n'apparaît pas dans les logs lors d'un LDAPUnavailableError."""
    from idp_auth.ldap_service import LDAPUnavailableError
    from rest_framework.test import APIClient

    mock_ldap = mock_ldap_class.return_value
    mock_ldap.authenticate.side_effect = LDAPUnavailableError('LDAP down')

    error_calls = []

    with patch('idp_auth.views.logger') as mock_logger:
        bound_logger = MagicMock()
        mock_logger.bind.return_value = bound_logger
        bound_logger.error.side_effect = lambda *a, **kw: error_calls.append(kw)

        client = APIClient()
        client.post(ENDPOINT, {'username': 'svc', 'password': 'very-secret'}, format='json')

    for call_kwargs in error_calls:
        for value in call_kwargs.values():
            assert 'very-secret' not in str(value), (
                f"Le password a été loggué dans: {call_kwargs}"
            )
