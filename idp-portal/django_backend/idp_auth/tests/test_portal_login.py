"""
Tests unitaires pour PortalLoginView — POST /api/v1/auth/portal-login/
Story 68.1 : Endpoint authentification portail via LDAP (utilisateurs interactifs, comptes à haut privilège).

AC4  : test_portal_auth_methods_ldap_is_first
AC5  : tests endpoint credentials valides / invalides / no_profile / ldap_unavailable
AC6  : Audit USER_LOGIN (distinct de SERVICE_LOGIN)
AC7  : PortalLoginThrottle configuré sur la vue
"""

from unittest.mock import MagicMock, patch
from django.conf import settings
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from core.models import AuditActionType

ENDPOINT = '/api/v1/auth/portal-login/'


# ============================================================================
# AC4 — Configuration PORTAL_AUTH_METHODS
# ============================================================================

def test_portal_auth_methods_ldap_is_first():
    """AC4 : LDAP doit être en première position dans PORTAL_AUTH_METHODS."""
    assert settings.PORTAL_AUTH_METHODS[0] == "ldap", (
        f"LDAP doit être prioritaire. Ordre actuel : {settings.PORTAL_AUTH_METHODS}"
    )


def test_portal_auth_methods_default_includes_saml():
    """Vérification supplémentaire : la configuration par défaut inclut 'saml' en fallback."""
    assert "saml" in settings.PORTAL_AUTH_METHODS, (
        f"SAML doit être dans PORTAL_AUTH_METHODS. Valeur actuelle : {settings.PORTAL_AUTH_METHODS}"
    )


def test_portal_auth_methods_is_list():
    """PORTAL_AUTH_METHODS doit être une liste non vide."""
    assert isinstance(settings.PORTAL_AUTH_METHODS, list)
    assert len(settings.PORTAL_AUTH_METHODS) >= 1


def test_portal_auth_methods_env_var_override():
    """AC1 : PORTAL_AUTH_METHODS est contrôlable via variable d'environnement."""
    import importlib
    import os
    from unittest.mock import patch

    with patch.dict(os.environ, {'PORTAL_AUTH_METHODS': 'saml,ldap'}):
        import idp_backend.settings as settings_module
        importlib.reload(settings_module)
        try:
            assert settings_module.PORTAL_AUTH_METHODS == ['saml', 'ldap'], (
                f"Override env var ignoré. Valeur actuelle : {settings_module.PORTAL_AUTH_METHODS}"
            )
        finally:
            # Restaurer le module settings d'origine
            importlib.reload(settings_module)


# ============================================================================
# AC5 + AC6 + AC7 — Endpoint /auth/portal-login/
# ============================================================================

class TestPortalLoginView(TestCase):
    """Tests for POST /auth/portal-login/ endpoint."""

    def setUp(self):
        cache.clear()  # Reset PortalLoginThrottle state for test isolation
        self.client = APIClient()

    # ---------- AC5 : Succès 200 ----------

    @patch('idp_auth.views.portal_login.AuditService')
    @patch('idp_auth.views.portal_login.create_refresh_token', return_value='mock-refresh-token')
    @patch('idp_auth.views.portal_login.create_access_token', return_value='mock-access-token')
    @patch('idp_auth.views.portal_login.AuthService')
    @patch('idp_auth.views.portal_login.Profile')
    @patch('idp_auth.views.portal_login.LDAPService')
    def test_portal_login_success(
        self, mock_ldap_class, mock_profile, mock_auth_service_class,
        mock_create_access, mock_create_refresh, mock_audit
    ):
        """AC5 : Credentials valides → 200, access_token présent, cookie refresh_token posé."""
        # Arrange
        mock_ldap = mock_ldap_class.return_value
        mock_ldap.authenticate.return_value = (
            True,
            ['CN=GRP-IDP-ADMIN,OU=Groups,DC=example,DC=com'],
            'Jean Dupont',
        )

        mock_profile_obj = MagicMock()
        mock_profile_obj.name = 'ADMIN'
        mock_profile.objects.find_by_ad_groups.return_value = [mock_profile_obj]

        mock_user = MagicMock()
        mock_user.id = 10
        mock_user.username = 'jdupont-admin'
        mock_user.profile = 'admin'
        mock_auth_service_class.return_value.create_or_update_user.return_value = mock_user

        # Act
        response = self.client.post(
            ENDPOINT,
            {'username': 'jdupont-admin', 'password': 'secret'},
            format='json',
        )

        # Assert status + body
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertEqual(response.data['data']['access_token'], 'mock-access-token')
        self.assertEqual(response.data['data']['token_type'], 'Bearer')
        self.assertIn('expires_in', response.data['data'])

        # Assert refresh cookie présent
        self.assertIn('refresh_token', response.cookies)
        cookie = response.cookies['refresh_token']
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'], 'Lax')
        self.assertEqual(cookie['path'], '/api/v1/auth')

        # Assert JIT user creation called
        mock_auth_service_class.return_value.create_or_update_user.assert_called_once_with(
            username='jdupont-admin',
            display_name='Jean Dupont',
            profile='admin',
            saml_subject=None,
        )

        # Assert token built with correct claims
        expected_token_data = {
            'sub': '10',
            'username': 'jdupont-admin',
            'profile': 'admin',
            'ad_groups': ['CN=GRP-IDP-ADMIN,OU=Groups,DC=example,DC=com'],
        }
        mock_create_access.assert_called_once_with(expected_token_data)
        mock_create_refresh.assert_called_once_with(expected_token_data)

    # ---------- AC5 : Credentials invalides → 401 ----------

    @patch('idp_auth.views.portal_login.AuditService')
    @patch('idp_auth.views.portal_login.LDAPService')
    def test_portal_login_invalid_credentials(self, mock_ldap_class, mock_audit):
        """AC5 : LDAP bind échoue → 401 INVALID_CREDENTIALS."""
        mock_ldap = mock_ldap_class.return_value
        mock_ldap.authenticate.return_value = (False, [], None)

        response = self.client.post(
            ENDPOINT,
            {'username': 'jdupont-admin', 'password': 'wrong'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data['error']['code'], 'INVALID_CREDENTIALS')

        # Audit appelé pour l'échec
        mock_audit.create_entry.assert_called_once()
        call_kwargs = mock_audit.create_entry.call_args.kwargs
        self.assertFalse(call_kwargs['details']['success'])
        self.assertEqual(call_kwargs['details']['reason'], 'invalid_credentials')

    # ---------- AC5 : Aucun profil AD → 403 ----------

    @patch('idp_auth.views.portal_login.AuditService')
    @patch('idp_auth.views.portal_login.Profile')
    @patch('idp_auth.views.portal_login.LDAPService')
    def test_portal_login_no_profile(self, mock_ldap_class, mock_profile, mock_audit):
        """AC5 : Aucun profil associé aux groupes AD → 403 NO_PROFILE."""
        mock_ldap = mock_ldap_class.return_value
        mock_ldap.authenticate.return_value = (True, ['CN=UNKNOWN-GROUP,DC=example,DC=com'], 'Jean')
        mock_profile.objects.find_by_ad_groups.return_value = []

        response = self.client.post(
            ENDPOINT,
            {'username': 'jdupont-admin', 'password': 'pass'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['error']['code'], 'NO_PROFILE')

    # ---------- AC5 : LDAP indisponible → 503 ----------

    @patch('idp_auth.views.portal_login.AuditService')
    @patch('idp_auth.views.portal_login.LDAPService')
    def test_portal_login_ldap_unavailable(self, mock_ldap_class, mock_audit):
        """AC5 : LDAPUnavailableError levée → 503 LDAP_UNAVAILABLE."""
        from idp_auth.ldap_service import LDAPUnavailableError
        mock_ldap = mock_ldap_class.return_value
        mock_ldap.authenticate.side_effect = LDAPUnavailableError('LDAP_URI non configuré')

        response = self.client.post(
            ENDPOINT,
            {'username': 'jdupont-admin', 'password': 'pass'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data['error']['code'], 'LDAP_UNAVAILABLE')

        # Audit appelé pour l'échec
        mock_audit.create_entry.assert_called_once()
        call_kwargs = mock_audit.create_entry.call_args.kwargs
        self.assertEqual(call_kwargs['details']['reason'], 'ldap_unavailable')

    # ---------- Validation sérialiseur → 400 ----------

    def test_missing_password_returns_400(self):
        """Body incomplet (password manquant) → 400."""
        response = self.client.post(ENDPOINT, {'username': 'jdupont'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_empty_body_returns_400(self):
        """Body vide → 400."""
        response = self.client.post(ENDPOINT, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_username_returns_400(self):
        """Body sans username → 400."""
        response = self.client.post(ENDPOINT, {'password': 'secret'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ---------- AC7 : PortalLoginThrottle configuré ----------

    def test_portal_throttle_class_configured(self):
        """AC7 : PortalLoginThrottle actif sur PortalLoginView."""
        from idp_auth.views import PortalLoginView
        from core.throttling import PortalLoginThrottle
        self.assertIn(PortalLoginThrottle, PortalLoginView.throttle_classes)

    @patch('idp_auth.views.portal_login.AuditService')
    @patch('idp_auth.views.portal_login.LDAPService')
    def test_throttle_applied_on_request(self, mock_ldap_class, mock_audit):
        """AC7 : Le throttle est évalué pour chaque requête (mock throttle → 429)."""
        from core.throttling import PortalLoginThrottle

        mock_ldap = mock_ldap_class.return_value
        mock_ldap.authenticate.return_value = (False, [], None)

        with patch.object(PortalLoginThrottle, 'allow_request', return_value=False), \
             patch.object(PortalLoginThrottle, 'wait', return_value=60):
            response = self.client.post(
                ENDPOINT,
                {'username': 'jdupont-admin', 'password': 'pass'},
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    # ---------- AC6 : Audit USER_LOGIN (pas SERVICE_LOGIN) ----------

    @patch('idp_auth.views.portal_login.AuditService')
    @patch('idp_auth.views.portal_login.create_refresh_token', return_value='mock-refresh-token')
    @patch('idp_auth.views.portal_login.create_access_token', return_value='mock-access-token')
    @patch('idp_auth.views.portal_login.Profile')
    @patch('idp_auth.views.portal_login.LDAPService')
    @patch('idp_auth.views.portal_login.AuthService')
    def test_portal_login_audit_user_login(
        self, mock_auth_service, mock_ldap_class, mock_profile,
        mock_create_access, mock_create_refresh, mock_audit
    ):
        """AC6 : Audit entrée succès utilise USER_LOGIN (pas SERVICE_LOGIN)."""
        mock_ldap = mock_ldap_class.return_value
        mock_ldap.authenticate.return_value = (True, ['CN=GRP-IDP-ADMIN,DC=example,DC=com'], 'Jean Dupont')
        mock_profile_obj = MagicMock()
        mock_profile_obj.name = 'ADMIN'
        mock_profile.objects.find_by_ad_groups.return_value = [mock_profile_obj]
        mock_user = MagicMock()
        mock_user.id = 10
        mock_user.username = 'jdupont-admin'
        mock_user.profile = 'admin'
        mock_auth_service.return_value.create_or_update_user.return_value = mock_user

        self.client.post(ENDPOINT, {'username': 'jdupont-admin', 'password': 'secret'}, format='json')

        calls = mock_audit.create_entry.call_args_list
        self.assertTrue(len(calls) >= 1)
        audit_call = calls[-1]
        action_type = audit_call.kwargs.get('action_type') or audit_call[1].get('action_type')
        self.assertEqual(action_type, AuditActionType.USER_LOGIN)

    @patch('idp_auth.views.portal_login.AuditService')
    @patch('idp_auth.views.portal_login.LDAPService')
    def test_audit_failure_uses_user_login_action_type(self, mock_ldap_class, mock_audit):
        """AC6 : Audit entrée d'échec utilise USER_LOGIN (pas SERVICE_LOGIN)."""
        mock_ldap = mock_ldap_class.return_value
        mock_ldap.authenticate.return_value = (False, [], None)

        self.client.post(ENDPOINT, {'username': 'jdupont', 'password': 'wrong'}, format='json')

        mock_audit.create_entry.assert_called_once()
        call_kwargs = mock_audit.create_entry.call_args.kwargs
        self.assertEqual(call_kwargs['action_type'], AuditActionType.USER_LOGIN)
