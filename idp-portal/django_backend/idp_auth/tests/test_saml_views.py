"""
Tests for SAML authentication views.
Story M.7 - Task 9.1-9.5

Note: These tests use mocks for python3-saml to avoid dependencies on real SAML infrastructure.
For integration testing with real SAML assertions, consider adding end-to-end tests
with a test IdP (e.g., using samltest.id or a local test IdP).

Code Review Fix (M.7): Added comment about mock strategy and integration test recommendation.
"""

from unittest.mock import patch, MagicMock

from django.test import TestCase, RequestFactory, override_settings
from django.http import HttpResponseRedirect


@override_settings(
    AUTH_DEV_BYPASS=False,
    JWT_SECRET_KEY='test-secret-key',
    JWT_ALGORITHM='HS256',
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30,
    JWT_REFRESH_TOKEN_EXPIRE_HOURS=8,
    APP_ENV='development',
    CORS_ALLOWED_ORIGINS=['http://localhost:5173'],
    SAML_SP_ENTITY_ID='https://sp.example.com',
    SAML_SP_ACS_URL='http://localhost:8000/api/v1/auth/saml/callback',
    SAML_IDP_ENTITY_ID='https://idp.example.com',
    SAML_IDP_SSO_URL='https://idp.example.com/sso',
    SAML_IDP_SLO_URL='https://idp.example.com/slo',
    SAML_IDP_CERT_PATH='',
    SAML_SP_CERT_PATH='',
    SAML_SP_KEY_PATH='',
)
class TestSAMLLoginView(TestCase):
    """Tests for GET /auth/saml/login endpoint."""

    def setUp(self):
        self.factory = RequestFactory()

    @patch('idp_auth.views.create_saml_auth')
    def test_saml_login_redirects_to_idp(self, mock_create_auth):
        """GET /auth/saml/login redirects to IdP SSO URL."""
        from idp_auth.views import SAMLLoginView

        mock_auth = MagicMock()
        mock_auth.login.return_value = 'https://idp.example.com/sso?SAMLRequest=xxx'
        mock_create_auth.return_value = mock_auth

        request = self.factory.get('/api/v1/auth/saml/login')
        view = SAMLLoginView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, 302)
        self.assertIn('idp.example.com', response.url)

    @override_settings(AUTH_DEV_BYPASS=True)
    def test_saml_login_dev_bypass(self):
        """Dev bypass mode skips IdP and emits JWT directly."""
        from idp_auth.views import SAMLLoginView

        request = self.factory.get('/api/v1/auth/saml/login')
        view = SAMLLoginView.as_view()
        response = view(request)

        # Should redirect to SPA with access token
        self.assertEqual(response.status_code, 302)
        self.assertIn('localhost:5173', response.url)
        self.assertIn('access_token=', response.url)

        # Should set refresh_token cookie
        self.assertIn('refresh_token', response.cookies)
        cookie = response.cookies['refresh_token']
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['path'], '/api/v1/auth')


@override_settings(
    AUTH_DEV_BYPASS=False,
    JWT_SECRET_KEY='test-secret-key',
    JWT_ALGORITHM='HS256',
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30,
    JWT_REFRESH_TOKEN_EXPIRE_HOURS=8,
    APP_ENV='development',
    CORS_ALLOWED_ORIGINS=['http://localhost:5173'],
    SAML_SP_ENTITY_ID='https://sp.example.com',
    SAML_SP_ACS_URL='http://localhost:8000/api/v1/auth/saml/callback',
    SAML_IDP_ENTITY_ID='https://idp.example.com',
    SAML_IDP_SSO_URL='https://idp.example.com/sso',
    SAML_IDP_SLO_URL='https://idp.example.com/slo',
    SAML_IDP_CERT_PATH='',
    SAML_SP_CERT_PATH='',
    SAML_SP_KEY_PATH='',
)
class TestSAMLCallbackView(TestCase):
    """Tests for POST /auth/saml/callback endpoint."""

    def setUp(self):
        self.factory = RequestFactory()

    @patch('idp_auth.views.AuditService')
    @patch('idp_auth.views.AuthService')
    @patch('idp_auth.views.Profile')
    @patch('idp_auth.views.create_saml_auth')
    def test_saml_callback_valid_assertion_creates_user(
        self, mock_create_auth, mock_profile_model, mock_auth_service, mock_audit
    ):
        """Valid SAML assertion creates/updates user and emits JWT."""
        from idp_auth.views import SAMLCallbackView

        # Mock SAML auth
        mock_auth = MagicMock()
        mock_auth.get_errors.return_value = []
        mock_auth.is_authenticated.return_value = True
        mock_auth.get_attributes.return_value = {
            'username': ['testuser'],
            'displayName': ['Test User'],
            'profile': ['dbops'],
            'groups': ['CN=DBOps,OU=Groups,DC=example,DC=com'],
        }
        mock_auth.get_nameid.return_value = 'testuser@example.com'
        mock_create_auth.return_value = mock_auth

        # Mock profile lookup
        mock_profile = MagicMock()
        mock_profile.name = 'dbops'
        mock_profile_model.objects.find_by_ad_groups.return_value = [mock_profile]

        # Mock user creation
        mock_user = MagicMock()
        mock_user.id = 123
        mock_user.username = 'testuser'
        mock_user.profile = 'dbops'
        mock_auth_service.return_value.create_or_update_user.return_value = mock_user

        request = self.factory.post(
            '/api/v1/auth/saml/callback',
            data={'SAMLResponse': 'base64encodedresponse'}
        )
        view = SAMLCallbackView.as_view()
        response = view(request)

        # Should redirect to SPA with access token
        self.assertEqual(response.status_code, 302)
        self.assertIn('localhost:5173', response.url)
        self.assertIn('access_token=', response.url)

        # User should be created/updated
        mock_auth_service.return_value.create_or_update_user.assert_called_once()

    @patch('idp_auth.views.create_saml_auth')
    def test_saml_callback_invalid_assertion_returns_403(self, mock_create_auth):
        """Invalid SAML assertion returns 403 SAML_VALIDATION_FAILED."""
        from idp_auth.views import SAMLCallbackView

        mock_auth = MagicMock()
        mock_auth.get_errors.return_value = ['Signature validation failed']
        mock_auth.get_last_error_reason.return_value = 'Invalid signature'
        mock_create_auth.return_value = mock_auth

        request = self.factory.post(
            '/api/v1/auth/saml/callback',
            data={'SAMLResponse': 'invalid'}
        )
        view = SAMLCallbackView.as_view()

        from core.exceptions import ForbiddenError
        with self.assertRaises(ForbiddenError) as context:
            view(request)

        self.assertEqual(context.exception.code, 'SAML_VALIDATION_FAILED')

    @patch('idp_auth.views.create_saml_auth')
    def test_saml_callback_not_authenticated_returns_403(self, mock_create_auth):
        """Not authenticated returns 403 SAML_NOT_AUTHENTICATED."""
        from idp_auth.views import SAMLCallbackView

        mock_auth = MagicMock()
        mock_auth.get_errors.return_value = []
        mock_auth.is_authenticated.return_value = False
        mock_create_auth.return_value = mock_auth

        request = self.factory.post(
            '/api/v1/auth/saml/callback',
            data={'SAMLResponse': 'base64data'}
        )
        view = SAMLCallbackView.as_view()

        from core.exceptions import ForbiddenError
        with self.assertRaises(ForbiddenError) as context:
            view(request)

        self.assertEqual(context.exception.code, 'SAML_NOT_AUTHENTICATED')

    @patch('idp_auth.views.Profile')
    @patch('idp_auth.views.create_saml_auth')
    def test_saml_callback_no_profile_returns_403(self, mock_create_auth, mock_profile_model):
        """User with no matching profile returns 403 NO_PROFILE."""
        from idp_auth.views import SAMLCallbackView

        mock_auth = MagicMock()
        mock_auth.get_errors.return_value = []
        mock_auth.is_authenticated.return_value = True
        mock_auth.get_attributes.return_value = {
            'username': ['unknownuser'],
            'groups': ['CN=UnknownGroup,OU=Groups,DC=example,DC=com'],
        }
        mock_auth.get_nameid.return_value = 'unknownuser@example.com'
        mock_create_auth.return_value = mock_auth

        # No matching profiles
        mock_profile_model.objects.find_by_ad_groups.return_value = []

        request = self.factory.post(
            '/api/v1/auth/saml/callback',
            data={'SAMLResponse': 'base64data'}
        )
        view = SAMLCallbackView.as_view()

        from core.exceptions import ForbiddenError
        with self.assertRaises(ForbiddenError) as context:
            view(request)

        self.assertEqual(context.exception.code, 'NO_PROFILE')


class TestExtractAdGroups(TestCase):
    """Tests for _extract_ad_groups helper."""

    def test_extract_ad_groups_from_groups(self):
        """Extract AD groups from 'groups' attribute."""
        from idp_auth.views import _extract_ad_groups

        attributes = {'groups': ['group1', 'group2']}
        result = _extract_ad_groups(attributes, None)

        self.assertEqual(result, ['group1', 'group2'])

    def test_extract_ad_groups_from_memberOf(self):
        """Extract AD groups from 'memberOf' attribute."""
        from idp_auth.views import _extract_ad_groups

        attributes = {'memberOf': ['CN=Group1,DC=test', 'CN=Group2,DC=test']}
        result = _extract_ad_groups(attributes, None)

        self.assertEqual(result, ['CN=Group1,DC=test', 'CN=Group2,DC=test'])

    def test_extract_ad_groups_from_ad_groups(self):
        """Extract AD groups from 'ad_groups' attribute."""
        from idp_auth.views import _extract_ad_groups

        attributes = {'ad_groups': ['admin', 'users']}
        result = _extract_ad_groups(attributes, None)

        self.assertEqual(result, ['admin', 'users'])

    def test_extract_ad_groups_string_value(self):
        """Handle single string value for groups."""
        from idp_auth.views import _extract_ad_groups

        attributes = {'groups': 'single_group'}
        result = _extract_ad_groups(attributes, None)

        self.assertEqual(result, ['single_group'])

    def test_extract_ad_groups_fallback_to_profile(self):
        """Fall back to raw_profile if no groups found."""
        from idp_auth.views import _extract_ad_groups

        attributes = {}
        result = _extract_ad_groups(attributes, 'dbops')

        self.assertEqual(result, ['dbops'])

    def test_extract_ad_groups_strips_whitespace(self):
        """Whitespace is stripped from group names."""
        from idp_auth.views import _extract_ad_groups

        attributes = {'groups': ['  group1  ', '  group2  ']}
        result = _extract_ad_groups(attributes, None)

        self.assertEqual(result, ['group1', 'group2'])

    def test_extract_ad_groups_filters_empty(self):
        """Empty and whitespace-only groups are filtered."""
        from idp_auth.views import _extract_ad_groups

        attributes = {'groups': ['group1', '', '  ', 'group2']}
        result = _extract_ad_groups(attributes, None)

        self.assertEqual(result, ['group1', 'group2'])
