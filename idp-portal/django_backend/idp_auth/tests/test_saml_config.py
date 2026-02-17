"""
Tests for SAML configuration and utilities.
Story M.7 - Task 2.6
"""

from unittest.mock import patch
from django.test import TestCase, RequestFactory, override_settings


class TestReadCertFile(TestCase):
    """Tests for _read_cert_file helper."""

    def test_read_cert_file_empty_path(self):
        """Empty path returns empty string."""
        from idp_auth.saml_config import _read_cert_file
        result = _read_cert_file("")
        self.assertEqual(result, "")

    def test_read_cert_file_none_path(self):
        """None path returns empty string."""
        from idp_auth.saml_config import _read_cert_file
        result = _read_cert_file(None)
        self.assertEqual(result, "")

    @patch('idp_auth.saml_config.Path')
    def test_read_cert_file_valid_path(self, mock_path):
        """Valid path returns file content."""
        from idp_auth.saml_config import _read_cert_file
        mock_path.return_value.read_text.return_value = "  CERT_CONTENT  "
        result = _read_cert_file("/path/to/cert.pem")
        self.assertEqual(result, "CERT_CONTENT")

    @patch('idp_auth.saml_config.Path')
    def test_read_cert_file_not_found(self, mock_path):
        """FileNotFoundError returns empty string (dev mode)."""
        from idp_auth.saml_config import _read_cert_file
        mock_path.return_value.read_text.side_effect = FileNotFoundError()
        result = _read_cert_file("/path/to/missing.pem")
        self.assertEqual(result, "")


@override_settings(
    DEBUG=False,
    SAML_SP_ENTITY_ID='https://sp.example.com/metadata',
    SAML_SP_ACS_URL='https://sp.example.com/acs',
    SAML_SP_CERT_PATH='',
    SAML_SP_KEY_PATH='',
    SAML_IDP_ENTITY_ID='https://idp.example.com/entity',
    SAML_IDP_SSO_URL='https://idp.example.com/sso',
    SAML_IDP_SLO_URL='https://idp.example.com/slo',
    SAML_IDP_CERT_PATH='',
)
class TestGetSamlSettings(TestCase):
    """Tests for get_saml_settings()."""

    def test_get_saml_settings_structure(self):
        """Settings dict has correct structure."""
        from idp_auth.saml_config import get_saml_settings
        settings = get_saml_settings()

        self.assertIn('strict', settings)
        self.assertIn('debug', settings)
        self.assertIn('sp', settings)
        self.assertIn('idp', settings)

    def test_get_saml_settings_sp_config(self):
        """SP config has correct values."""
        from idp_auth.saml_config import get_saml_settings
        settings = get_saml_settings()

        self.assertEqual(settings['sp']['entityId'], 'https://sp.example.com/metadata')
        self.assertEqual(settings['sp']['assertionConsumerService']['url'], 'https://sp.example.com/acs')
        self.assertEqual(
            settings['sp']['assertionConsumerService']['binding'],
            'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST'
        )

    def test_get_saml_settings_idp_config(self):
        """IdP config has correct values."""
        from idp_auth.saml_config import get_saml_settings
        settings = get_saml_settings()

        self.assertEqual(settings['idp']['entityId'], 'https://idp.example.com/entity')
        self.assertEqual(settings['idp']['singleSignOnService']['url'], 'https://idp.example.com/sso')
        self.assertEqual(
            settings['idp']['singleSignOnService']['binding'],
            'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect'
        )

    def test_get_saml_settings_strict_mode(self):
        """Strict mode is enabled."""
        from idp_auth.saml_config import get_saml_settings
        settings = get_saml_settings()
        self.assertTrue(settings['strict'])


class TestPrepareDjangoRequest(TestCase):
    """Tests for prepare_django_request()."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_prepare_django_request_http(self):
        """HTTP request is prepared correctly."""
        from idp_auth.saml_utils import prepare_django_request
        request = self.factory.get('/api/v1/auth/saml/login')
        result = prepare_django_request(request)

        self.assertEqual(result['https'], 'off')
        self.assertEqual(result['script_name'], '/api/v1/auth/saml/login')
        self.assertIsInstance(result['get_data'], dict)
        self.assertEqual(result['post_data'], {})

    def test_prepare_django_request_https(self):
        """HTTPS request is prepared correctly."""
        from idp_auth.saml_utils import prepare_django_request
        request = self.factory.get('/api/v1/auth/saml/login', secure=True)
        result = prepare_django_request(request)

        self.assertEqual(result['https'], 'on')

    def test_prepare_django_request_forwarded_proto(self):
        """X-Forwarded-Proto header is respected."""
        from idp_auth.saml_utils import prepare_django_request
        request = self.factory.get('/api/v1/auth/saml/login', HTTP_X_FORWARDED_PROTO='https')
        result = prepare_django_request(request)

        self.assertEqual(result['https'], 'on')

    def test_prepare_django_request_with_query_params(self):
        """Query params are included in get_data."""
        from idp_auth.saml_utils import prepare_django_request
        request = self.factory.get('/api/v1/auth/saml/login?RelayState=/dashboard')
        result = prepare_django_request(request)

        # dict(QueryDict) returns lists as values
        self.assertEqual(result['get_data'], {'RelayState': ['/dashboard']})

    @override_settings(ALLOWED_HOSTS=['localhost', 'testserver'])
    def test_prepare_django_request_host_with_port(self):
        """Host with port is parsed correctly."""
        from idp_auth.saml_utils import prepare_django_request
        request = self.factory.get('/api/v1/auth/saml/login', HTTP_HOST='localhost:8000')
        result = prepare_django_request(request)

        self.assertEqual(result['http_host'], 'localhost')
        self.assertEqual(result['server_port'], '8000')


class TestCreateSamlAuth(TestCase):
    """Tests for create_saml_auth()."""

    def setUp(self):
        self.factory = RequestFactory()

    @patch('idp_auth.saml_utils.OneLogin_Saml2_Auth')
    @patch('idp_auth.saml_utils.get_saml_settings')
    def test_create_saml_auth_without_post_data(self, mock_settings, mock_auth):
        """Creates auth instance for GET request."""
        from idp_auth.saml_utils import create_saml_auth
        mock_settings.return_value = {'strict': True}
        request = self.factory.get('/api/v1/auth/saml/login')

        create_saml_auth(request)

        mock_auth.assert_called_once()
        call_args = mock_auth.call_args[0]
        self.assertEqual(call_args[0]['post_data'], {})
        self.assertEqual(call_args[1], {'strict': True})

    @patch('idp_auth.saml_utils.OneLogin_Saml2_Auth')
    @patch('idp_auth.saml_utils.get_saml_settings')
    def test_create_saml_auth_with_post_data(self, mock_settings, mock_auth):
        """Creates auth instance with POST data."""
        from idp_auth.saml_utils import create_saml_auth
        mock_settings.return_value = {'strict': True}
        request = self.factory.post('/api/v1/auth/saml/callback')
        post_data = {'SAMLResponse': 'base64data'}

        create_saml_auth(request, post_data=post_data)

        mock_auth.assert_called_once()
        call_args = mock_auth.call_args[0]
        self.assertEqual(call_args[0]['post_data'], post_data)
