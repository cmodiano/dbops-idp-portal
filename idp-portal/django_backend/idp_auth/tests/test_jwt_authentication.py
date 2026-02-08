"""
Tests for JWTAuthentication backend.
Story M.7 - Task 9.10
"""

from unittest.mock import patch, MagicMock

from django.test import TestCase, RequestFactory, override_settings
from rest_framework.exceptions import AuthenticationFailed


@override_settings(
    JWT_SECRET_KEY='test-secret-key',
    JWT_ALGORITHM='HS256',
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30,
    JWT_REFRESH_TOKEN_EXPIRE_HOURS=8,
)
class TestJWTAuthentication(TestCase):
    """Tests for JWTAuthentication DRF backend."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_authenticate_valid_token(self):
        """Valid token returns user tuple."""
        from idp_auth.authentication import JWTAuthentication
        from idp_auth.jwt_utils import create_access_token

        # Create mock user
        mock_user = MagicMock()
        mock_user.id = 123

        # Create token
        token_data = {
            'sub': '123',
            'username': 'testuser',
            'profile': 'dbops',
            'ad_groups': ['admin'],
        }
        token = create_access_token(token_data)

        # Create request with token
        request = self.factory.get('/api/v1/test/', HTTP_AUTHORIZATION=f'Bearer {token}')

        with patch('idp_auth.authentication.User') as MockUser:
            MockUser.objects.get.return_value = mock_user

            auth = JWTAuthentication()
            result = auth.authenticate(request)

            self.assertIsNotNone(result)
            user, _ = result
            self.assertEqual(user.id, 123)
            self.assertEqual(user.ad_groups, ['admin'])

    def test_authenticate_no_header(self):
        """No Authorization header returns None (allows anonymous)."""
        from idp_auth.authentication import JWTAuthentication

        request = self.factory.get('/api/v1/test/')

        auth = JWTAuthentication()
        result = auth.authenticate(request)

        self.assertIsNone(result)

    def test_authenticate_non_bearer_header(self):
        """Non-Bearer Authorization header returns None."""
        from idp_auth.authentication import JWTAuthentication

        request = self.factory.get('/api/v1/test/', HTTP_AUTHORIZATION='Basic dXNlcjpwYXNz')

        auth = JWTAuthentication()
        result = auth.authenticate(request)

        self.assertIsNone(result)

    def test_authenticate_invalid_token(self):
        """Invalid token raises AuthenticationFailed."""
        from idp_auth.authentication import JWTAuthentication

        request = self.factory.get('/api/v1/test/', HTTP_AUTHORIZATION='Bearer invalid-token')

        auth = JWTAuthentication()
        with self.assertRaises(AuthenticationFailed) as context:
            auth.authenticate(request)

        self.assertIn('invalide', str(context.exception.detail).lower())

    def test_authenticate_expired_token(self):
        """Expired token raises AuthenticationFailed."""
        from datetime import timedelta
        from idp_auth.authentication import JWTAuthentication
        from idp_auth.jwt_utils import create_access_token

        token_data = {
            'sub': '123',
            'username': 'testuser',
            'profile': 'dbops',
            'ad_groups': [],
        }
        token = create_access_token(token_data, expires_delta=timedelta(seconds=-1))
        request = self.factory.get('/api/v1/test/', HTTP_AUTHORIZATION=f'Bearer {token}')

        auth = JWTAuthentication()
        with self.assertRaises(AuthenticationFailed):
            auth.authenticate(request)

    def test_authenticate_refresh_token_rejected(self):
        """Refresh token is rejected for API auth."""
        from idp_auth.authentication import JWTAuthentication
        from idp_auth.jwt_utils import create_refresh_token

        token_data = {
            'sub': '123',
            'username': 'testuser',
            'profile': 'dbops',
            'ad_groups': [],
        }
        token = create_refresh_token(token_data)
        request = self.factory.get('/api/v1/test/', HTTP_AUTHORIZATION=f'Bearer {token}')

        auth = JWTAuthentication()
        with self.assertRaises(AuthenticationFailed):
            auth.authenticate(request)

    def test_authenticate_user_not_found(self):
        """Token for non-existent user raises AuthenticationFailed."""
        from idp_auth.authentication import JWTAuthentication
        from idp_auth.jwt_utils import create_access_token
        from idp_auth.models import User

        token_data = {
            'sub': '99999',
            'username': 'ghost',
            'profile': 'dbops',
            'ad_groups': [],
        }
        token = create_access_token(token_data)
        request = self.factory.get('/api/v1/test/', HTTP_AUTHORIZATION=f'Bearer {token}')

        with patch('idp_auth.authentication.User.objects.get', side_effect=User.DoesNotExist()):
            auth = JWTAuthentication()
            with self.assertRaises(AuthenticationFailed) as context:
                auth.authenticate(request)

            self.assertIn('non trouve', str(context.exception.detail).lower())

    def test_authenticate_invalid_user_id(self):
        """Token with non-numeric sub raises AuthenticationFailed."""
        from idp_auth.authentication import JWTAuthentication
        from jose import jwt
        from django.conf import settings

        # Create token with non-numeric sub
        token_data = {
            'sub': 'not-a-number',
            'username': 'testuser',
            'profile': 'dbops',
            'ad_groups': [],
            'type': 'access',
        }
        token = jwt.encode(token_data, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        request = self.factory.get('/api/v1/test/', HTTP_AUTHORIZATION=f'Bearer {token}')

        auth = JWTAuthentication()
        with self.assertRaises(AuthenticationFailed):
            auth.authenticate(request)

    def test_authenticate_header_value(self):
        """authenticate_header returns Bearer realm."""
        from idp_auth.authentication import JWTAuthentication

        request = self.factory.get('/api/v1/test/')
        auth = JWTAuthentication()
        header = auth.authenticate_header(request)

        self.assertEqual(header, 'Bearer realm="api"')
