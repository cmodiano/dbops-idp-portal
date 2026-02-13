"""
Tests for JWT token utilities.
Story M.7 - Task 4.9
"""

from datetime import timedelta

from django.test import TestCase, override_settings
from jose import jwt


@override_settings(
    JWT_SECRET_KEY='test-secret-key',
    JWT_ALGORITHM='HS256',
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30,
    JWT_REFRESH_TOKEN_EXPIRE_HOURS=8,
)
class TestJWTUtils(TestCase):
    """Tests for JWT token creation and verification."""

    def test_create_access_token(self):
        """Create access token with default expiration."""
        from idp_auth.jwt_utils import create_access_token

        data = {
            'sub': '123',
            'username': 'testuser',
            'profile': 'dba_applicatif',
            'ad_groups': ['group1', 'group2'],
        }
        token = create_access_token(data)

        # Decode and verify
        payload = jwt.decode(token, 'test-secret-key', algorithms=['HS256'])
        self.assertEqual(payload['sub'], '123')
        self.assertEqual(payload['username'], 'testuser')
        self.assertEqual(payload['profile'], 'dba_applicatif')
        self.assertEqual(payload['ad_groups'], ['group1', 'group2'])
        self.assertEqual(payload['type'], 'access')
        self.assertIn('exp', payload)

    def test_create_access_token_custom_expiration(self):
        """Create access token with custom expiration."""
        from idp_auth.jwt_utils import create_access_token

        data = {'sub': '123', 'username': 'testuser', 'profile': 'dbops', 'ad_groups': []}
        token = create_access_token(data, expires_delta=timedelta(minutes=5))

        payload = jwt.decode(token, 'test-secret-key', algorithms=['HS256'])
        self.assertEqual(payload['type'], 'access')

    def test_create_refresh_token(self):
        """Create refresh token with 8h expiration."""
        from idp_auth.jwt_utils import create_refresh_token

        data = {
            'sub': '123',
            'username': 'testuser',
            'profile': 'dbops',
            'ad_groups': ['admin'],
        }
        token = create_refresh_token(data)

        payload = jwt.decode(token, 'test-secret-key', algorithms=['HS256'])
        self.assertEqual(payload['sub'], '123')
        self.assertEqual(payload['type'], 'refresh')
        self.assertIn('exp', payload)

    def test_verify_token_valid_access(self):
        """Verify valid access token."""
        from idp_auth.jwt_utils import create_access_token, verify_token

        data = {
            'sub': '123',
            'username': 'testuser',
            'profile': 'dba_applicatif',
            'ad_groups': ['group1'],
        }
        token = create_access_token(data)
        payload = verify_token(token)

        self.assertIsNotNone(payload)
        self.assertEqual(payload.sub, '123')
        self.assertEqual(payload.username, 'testuser')
        self.assertEqual(payload.profile, 'dba_applicatif')
        self.assertEqual(payload.ad_groups, ['group1'])
        self.assertEqual(payload.type, 'access')

    def test_verify_token_valid_refresh(self):
        """Verify valid refresh token."""
        from idp_auth.jwt_utils import create_refresh_token, verify_token

        data = {
            'sub': '456',
            'username': 'testuser',
            'profile': 'dbops',
            'ad_groups': [],
        }
        token = create_refresh_token(data)
        payload = verify_token(token, expected_type='refresh')

        self.assertIsNotNone(payload)
        self.assertEqual(payload.type, 'refresh')

    def test_verify_token_wrong_type(self):
        """Verify token with wrong type returns None."""
        from idp_auth.jwt_utils import create_access_token, verify_token

        data = {'sub': '123', 'username': 'testuser', 'profile': 'dbops', 'ad_groups': []}
        token = create_access_token(data)  # Creates access token
        payload = verify_token(token, expected_type='refresh')  # Expects refresh

        self.assertIsNone(payload)

    def test_verify_token_expired(self):
        """Verify expired token returns None."""
        from idp_auth.jwt_utils import create_access_token, verify_token

        data = {'sub': '123', 'username': 'testuser', 'profile': 'dbops', 'ad_groups': []}
        token = create_access_token(data, expires_delta=timedelta(seconds=-1))
        payload = verify_token(token)

        self.assertIsNone(payload)

    def test_verify_token_invalid_signature(self):
        """Verify token with wrong secret returns None."""
        from idp_auth.jwt_utils import verify_token

        # Create token with different secret
        data = {'sub': '123', 'username': 'testuser', 'profile': 'dbops', 'type': 'access'}
        token = jwt.encode(data, 'wrong-secret', algorithm='HS256')
        payload = verify_token(token)

        self.assertIsNone(payload)

    def test_verify_token_malformed(self):
        """Verify malformed token returns None."""
        from idp_auth.jwt_utils import verify_token

        payload = verify_token('not-a-valid-jwt')
        self.assertIsNone(payload)

    def test_verify_token_empty(self):
        """Verify empty token returns None."""
        from idp_auth.jwt_utils import verify_token

        payload = verify_token('')
        self.assertIsNone(payload)

    def test_decode_token_unsafe(self):
        """Decode token without verification (for debugging)."""
        from idp_auth.jwt_utils import create_access_token, decode_token_unsafe

        data = {'sub': '123', 'username': 'testuser', 'profile': 'dbops', 'ad_groups': []}
        token = create_access_token(data, expires_delta=timedelta(seconds=-1))  # Expired

        # Should still decode (ignores expiration)
        payload = decode_token_unsafe(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload['sub'], '123')


@override_settings(
    JWT_SECRET_KEY='test-secret-key',
    JWT_ALGORITHM='HS256',
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30,
    JWT_REFRESH_TOKEN_EXPIRE_HOURS=8,
)
class TestTokenPayload(TestCase):
    """Tests for TokenPayload class."""

    def test_token_payload_all_fields(self):
        """TokenPayload accepts all fields."""
        from idp_auth.jwt_utils import TokenPayload

        payload = TokenPayload(
            sub='123',
            username='testuser',
            profile='dbops',
            ad_groups=['admin', 'operators'],
            type='access',
        )

        self.assertEqual(payload.sub, '123')
        self.assertEqual(payload.username, 'testuser')
        self.assertEqual(payload.profile, 'dbops')
        self.assertEqual(payload.ad_groups, ['admin', 'operators'])
        self.assertEqual(payload.type, 'access')

    def test_token_payload_default_ad_groups(self):
        """TokenPayload defaults ad_groups to empty list."""
        from idp_auth.jwt_utils import TokenPayload

        payload = TokenPayload(sub='123', username='testuser', profile='dbops')

        self.assertEqual(payload.ad_groups, [])

    def test_token_payload_extra_kwargs(self):
        """TokenPayload accepts extra kwargs from JWT."""
        from idp_auth.jwt_utils import TokenPayload

        # JWT payloads may have extra fields like 'iat', 'iss', etc.
        payload = TokenPayload(
            sub='123',
            username='testuser',
            profile='dbops',
            iat=1234567890,
            iss='idp-portal',
        )

        self.assertEqual(payload.sub, '123')
