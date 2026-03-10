"""
Tests de non-régression SAML — Story 68.4
Vérifie que le flux SAML reste fonctionnel après les changements de l'epic 68
(LDAP prioritaire, restriction groupes AD, login explicite).

AC1 : Flux SAML callback fonctionnel (assertion valide → JWT, invalide → 403, no profile → 403)
AC2 : Ordre LDAP > SAML dans PORTAL_AUTH_METHODS
AC3 : Audit auth_method: 'saml' dans SAMLCallbackView
AC6 : Différenciation audit ldap vs saml
"""

from unittest.mock import MagicMock, patch

from django.conf import settings
from django.test import TestCase, RequestFactory, override_settings
from rest_framework.test import APIClient

from core.models import AuditActionType


SAML_TEST_SETTINGS = {
    'AUTH_DEV_BYPASS': False,
    'JWT_SECRET_KEY': 'test-secret-key',
    'JWT_ALGORITHM': 'HS256',
    'JWT_ACCESS_TOKEN_EXPIRE_MINUTES': 30,
    'JWT_REFRESH_TOKEN_EXPIRE_HOURS': 8,
    'APP_ENV': 'development',
    'CORS_ALLOWED_ORIGINS': ['http://localhost:5173'],
    'PORTAL_AUTH_METHODS': ['ldap', 'saml'],
    'SAML_SP_ENTITY_ID': 'https://sp.example.com',
    'SAML_SP_ACS_URL': 'http://localhost:8000/api/v1/auth/saml/callback',
    'SAML_IDP_ENTITY_ID': 'https://idp.example.com',
    'SAML_IDP_SSO_URL': 'https://idp.example.com/sso',
    'SAML_IDP_SLO_URL': 'https://idp.example.com/slo',
    'SAML_IDP_CERT_PATH': '',
    'SAML_SP_CERT_PATH': '',
    'SAML_SP_KEY_PATH': '',
    'DEFAULT_SAML_PROFILE': 'dba_applicatif',
}


def _mock_valid_saml_auth():
    """Crée un mock python3-saml avec une assertion valide."""
    mock_auth = MagicMock()
    mock_auth.process_response.return_value = None
    mock_auth.get_errors.return_value = []
    mock_auth.is_authenticated.return_value = True
    mock_auth.get_attributes.return_value = {
        'username': ['testuser'],
        'displayName': ['Test User'],
        'mail': ['test@example.com'],
        'groups': ['CN=DBOps,OU=Groups,DC=example,DC=com'],
    }
    mock_auth.get_nameid.return_value = 'testuser@example.com'
    return mock_auth


def _mock_user(user_id=123, username='testuser', profile='dbops'):
    """Crée un mock User."""
    mock_user = MagicMock()
    mock_user.id = user_id
    mock_user.username = username
    mock_user.profile = profile
    return mock_user


def _mock_profile(name='dbops'):
    """Crée un mock Profile."""
    mock_profile = MagicMock()
    mock_profile.name = name
    return mock_profile


# ============================================================================
# AC1 — Tests non-régression SAML callback
# ============================================================================

@override_settings(**SAML_TEST_SETTINGS)
class TestSAMLCallbackNonRegression(TestCase):
    """AC1 : Vérifie que le flux SAML callback reste pleinement fonctionnel."""

    def setUp(self):
        self.factory = RequestFactory()

    @patch('idp_auth.views.saml.AuditService')
    @patch('idp_auth.views.saml.AuthService')
    @patch('idp_auth.views.saml.Profile')
    @patch('idp_auth.views.saml.create_saml_auth')
    def test_saml_callback_valid_assertion_returns_jwt(
        self, mock_create_auth, mock_profile_model, mock_auth_service, mock_audit
    ):
        """Assertion SAML valide → redirect avec #access_token, cookie refresh_token."""
        from idp_auth.views import SAMLCallbackView

        mock_create_auth.return_value = _mock_valid_saml_auth()
        mock_profile_model.objects.find_by_ad_groups.return_value = [_mock_profile()]
        mock_auth_service.return_value.create_or_update_user.return_value = _mock_user()

        request = self.factory.post(
            '/api/v1/auth/saml/callback/',
            data={'SAMLResponse': 'base64encodedresponse'}
        )
        response = SAMLCallbackView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        self.assertIn('#access_token=', response.url)
        self.assertIn('refresh_token', response.cookies)
        cookie = response.cookies['refresh_token']
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['path'], '/api/v1/auth')
        # Vérifier que l'utilisateur a été créé/mis à jour (JIT provisioning)
        mock_auth_service.return_value.create_or_update_user.assert_called_once_with(
            username='testuser',
            display_name='Test User',
            profile='dbops',
            saml_subject='testuser@example.com',
            email='test@example.com',
        )

    @patch('idp_auth.views.saml.create_saml_auth')
    def test_saml_callback_invalid_assertion_returns_403(self, mock_create_auth):
        """Assertion SAML invalide → 403 SAML_VALIDATION_FAILED."""
        from idp_auth.views import SAMLCallbackView

        mock_auth = MagicMock()
        mock_auth.get_errors.return_value = ['Signature validation failed']
        mock_auth.get_last_error_reason.return_value = 'Invalid signature'
        mock_create_auth.return_value = mock_auth

        request = self.factory.post(
            '/api/v1/auth/saml/callback/',
            data={'SAMLResponse': 'invalid'}
        )
        response = SAMLCallbackView.as_view()(request)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['error']['code'], 'SAML_VALIDATION_FAILED')

    @patch('idp_auth.views.saml.Profile')
    @patch('idp_auth.views.saml.create_saml_auth')
    def test_saml_callback_no_profile_returns_403(self, mock_create_auth, mock_profile_model):
        """Groupes AD sans profil correspondant → 403 NO_PROFILE."""
        from idp_auth.views import SAMLCallbackView

        mock_auth = _mock_valid_saml_auth()
        mock_auth.get_attributes.return_value = {
            'username': ['unknownuser'],
            'groups': ['CN=UnknownGroup,OU=Groups,DC=example,DC=com'],
        }
        mock_create_auth.return_value = mock_auth
        mock_profile_model.objects.find_by_ad_groups.return_value = []

        request = self.factory.post(
            '/api/v1/auth/saml/callback/',
            data={'SAMLResponse': 'base64data'}
        )
        response = SAMLCallbackView.as_view()(request)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['error']['code'], 'NO_PROFILE')


# ============================================================================
# AC3 + AC6 — Audit auth_method dans SAML callback
# ============================================================================

@override_settings(**SAML_TEST_SETTINGS)
class TestSAMLAuditAuthMethod(TestCase):
    """AC3 : L'audit SAML inclut auth_method: 'saml'. AC6 : Différenciation ldap/saml."""

    def setUp(self):
        self.factory = RequestFactory()

    @patch('idp_auth.views.saml.AuditService')
    @patch('idp_auth.views.saml.AuthService')
    @patch('idp_auth.views.saml.Profile')
    @patch('idp_auth.views.saml.create_saml_auth')
    def test_saml_callback_audit_includes_auth_method_saml(
        self, mock_create_auth, mock_profile_model, mock_auth_service, mock_audit
    ):
        """L'entrée d'audit du SAMLCallbackView contient auth_method: 'saml'."""
        from idp_auth.views import SAMLCallbackView

        mock_create_auth.return_value = _mock_valid_saml_auth()
        mock_profile_model.objects.find_by_ad_groups.return_value = [_mock_profile()]
        mock_auth_service.return_value.create_or_update_user.return_value = _mock_user()

        request = self.factory.post(
            '/api/v1/auth/saml/callback/',
            data={'SAMLResponse': 'base64data'}
        )
        SAMLCallbackView.as_view()(request)

        mock_audit.create_entry.assert_called_once()
        call_kwargs = mock_audit.create_entry.call_args
        details = call_kwargs.kwargs.get('details') or call_kwargs[1].get('details')
        self.assertEqual(details['auth_method'], 'saml')
        self.assertEqual(details['username'], 'testuser')
        self.assertIn('ad_groups', details)
        self.assertIn('correlation_id', details)

    @patch('idp_auth.views.saml.AuditService')
    @patch('idp_auth.views.saml.AuthService')
    @patch('idp_auth.views.saml.Profile')
    @patch('idp_auth.views.saml.create_saml_auth')
    def test_saml_callback_audit_action_type_is_user_login(
        self, mock_create_auth, mock_profile_model, mock_auth_service, mock_audit
    ):
        """L'audit SAML utilise USER_LOGIN comme action_type."""
        from idp_auth.views import SAMLCallbackView

        mock_create_auth.return_value = _mock_valid_saml_auth()
        mock_profile_model.objects.find_by_ad_groups.return_value = [_mock_profile()]
        mock_auth_service.return_value.create_or_update_user.return_value = _mock_user()

        request = self.factory.post(
            '/api/v1/auth/saml/callback/',
            data={'SAMLResponse': 'base64data'}
        )
        SAMLCallbackView.as_view()(request)

        call_kwargs = mock_audit.create_entry.call_args
        action_type = call_kwargs.kwargs.get('action_type') or call_kwargs[1].get('action_type')
        self.assertEqual(action_type, AuditActionType.USER_LOGIN)


# ============================================================================
# AC2 — Ordre LDAP > SAML
# ============================================================================

class TestLDAPPriorityOverSAML(TestCase):
    """AC2 : LDAP est prioritaire sur SAML dans PORTAL_AUTH_METHODS."""

    def test_ldap_priority_over_saml_in_settings(self):
        """PORTAL_AUTH_METHODS[0] == 'ldap' — LDAP est la méthode principale."""
        self.assertEqual(
            settings.PORTAL_AUTH_METHODS[0], 'ldap',
            f"LDAP doit être prioritaire. Ordre actuel : {settings.PORTAL_AUTH_METHODS}"
        )

    def test_saml_not_first_auth_method(self):
        """SAML ne doit pas être proposé comme méthode principale."""
        if len(settings.PORTAL_AUTH_METHODS) > 1:
            self.assertNotEqual(
                settings.PORTAL_AUTH_METHODS[0], 'saml',
                "SAML ne doit pas être la première méthode d'authentification"
            )


# ============================================================================
# AC6 — Test croisé audit portal-login auth_method: 'ldap'
# ============================================================================

@override_settings(
    PORTAL_AUTH_METHODS=['ldap', 'saml'],
    PORTAL_REQUIRED_GROUPS=['CN=DBOps,OU=Groups,DC=example,DC=com'],
    JWT_SECRET_KEY='test-secret-key',
    JWT_ALGORITHM='HS256',
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30,
    JWT_REFRESH_TOKEN_EXPIRE_HOURS=8,
    APP_ENV='development',
    CORS_ALLOWED_ORIGINS=['http://localhost:5173'],
    DEFAULT_SAML_PROFILE='dba_applicatif',
)
class TestPortalLoginAuditAuthMethodLDAP(TestCase):
    """AC6 : Vérification croisée que PortalLoginView enregistre auth_method: 'ldap'."""

    @patch('idp_auth.views.portal_login.AuditService')
    @patch('idp_auth.views.portal_login.AuthService')
    @patch('idp_auth.views.portal_login.Profile')
    @patch('idp_auth.views.portal_login.LDAPService')
    def test_portal_login_audit_includes_auth_method_ldap(
        self, mock_ldap_service_cls, mock_profile_model, mock_auth_service, mock_audit
    ):
        """PortalLoginView enregistre auth_method: 'ldap' dans les détails d'audit."""
        # Mock LDAPService.authenticate → return (success, ad_groups, display_name)
        mock_ldap_service = MagicMock()
        mock_ldap_service.authenticate.return_value = (
            True,
            ['CN=DBOps,OU=Groups,DC=example,DC=com'],
            'LDAP User',
        )
        mock_ldap_service_cls.return_value = mock_ldap_service

        # Mock profile lookup
        mock_profile = _mock_profile()
        mock_profile_model.objects.find_by_ad_groups.return_value = [mock_profile]

        # Mock user creation
        mock_user = _mock_user(username='ldapuser', profile='dbops')
        mock_auth_service.return_value.create_or_update_user.return_value = mock_user

        client = APIClient()
        response = client.post(
            '/api/v1/auth/portal-login/',
            data={'username': 'ldapuser', 'password': 'testpass'},
            format='json'
        )

        # Vérifier que la requête a réussi (200 = login OK)
        self.assertEqual(response.status_code, 200, f"Portal login failed: {response.data}")

        # Vérifier que l'audit a bien été appelé avec auth_method: 'ldap'
        mock_audit.create_entry.assert_called_once()
        call_kwargs = mock_audit.create_entry.call_args
        details = call_kwargs.kwargs.get('details') or call_kwargs[1].get('details')
        self.assertEqual(details['auth_method'], 'ldap')


# ============================================================================
# Coexistence SAML + LDAP
# ============================================================================

@override_settings(**SAML_TEST_SETTINGS)
class TestSAMLAndLDAPCoexistence(TestCase):
    """Vérifie que SAML et LDAP coexistent sans conflit."""

    def setUp(self):
        self.factory = RequestFactory()

    @patch('idp_auth.views.saml.create_saml_auth')
    def test_saml_login_redirects_to_idp(self, mock_create_auth):
        """GET /auth/saml/login/ → redirect vers IdP SSO URL."""
        from idp_auth.views import SAMLLoginView

        mock_auth = MagicMock()
        mock_auth.login.return_value = 'https://idp.example.com/sso?SAMLRequest=xxx'
        mock_create_auth.return_value = mock_auth

        request = self.factory.get('/api/v1/auth/saml/login/')
        response = SAMLLoginView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        self.assertIn('idp.example.com', response.url)

    @patch('idp_auth.views.saml.AuditService')
    @patch('idp_auth.views.saml.AuthService')
    @patch('idp_auth.views.saml.Profile')
    @patch('idp_auth.views.saml.create_saml_auth')
    def test_saml_and_ldap_coexist_without_conflict(
        self, mock_create_auth, mock_profile_model, mock_auth_service, mock_audit
    ):
        """Les deux méthodes sont activées et le callback SAML fonctionne."""
        from idp_auth.views import SAMLCallbackView

        self.assertIn('saml', settings.PORTAL_AUTH_METHODS)
        self.assertIn('ldap', settings.PORTAL_AUTH_METHODS)

        # Le callback SAML fonctionne quand les deux méthodes sont activées
        mock_create_auth.return_value = _mock_valid_saml_auth()
        mock_profile_model.objects.find_by_ad_groups.return_value = [_mock_profile()]
        mock_auth_service.return_value.create_or_update_user.return_value = _mock_user()

        request = self.factory.post(
            '/api/v1/auth/saml/callback/',
            data={'SAMLResponse': 'base64data'}
        )
        response = SAMLCallbackView.as_view()(request)
        self.assertEqual(response.status_code, 302)
