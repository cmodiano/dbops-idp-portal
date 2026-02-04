"""
Tests for authentication endpoints (DRF).
Tests: GET /auth/me, POST /auth/refresh, POST /auth/logout
Story M.7 - Task 9.6-9.8
"""

import pytest
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework import status
from idp_auth.models import User
from profiles.models import Profile


@pytest.mark.django_db
@override_settings(
    JWT_SECRET_KEY='test-secret-key',
    JWT_ALGORITHM='HS256',
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30,
    JWT_REFRESH_TOKEN_EXPIRE_HOURS=8,
)
class TestCurrentUserProfileView(TestCase):
    """Tests for GET /auth/me endpoint."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create test user
        self.user = User.objects.create(
            username='test_user',
            display_name='Test User',
            profile='dbops'
        )

        # Create profile matching user's profile
        self.profile = Profile.objects.create(
            name='dbops',
            description='DBOPS Profile',
            ad_group='dbops',
            is_admin=1,
            is_auditor=0
        )

    def test_get_current_user_profile_authenticated(self):
        """Test GET /auth/me with authenticated user returns 200."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/v1/auth/me')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        data = response.data['data']
        self.assertEqual(data['id'], self.user.id)
        self.assertEqual(data['username'], 'test_user')
        self.assertEqual(data['display_name'], 'Test User')
        self.assertEqual(data['profile'], 'dbops')
        self.assertIn('navigation_tabs', data)
        self.assertIn('is_business_profile', data)

    def test_get_current_user_profile_unauthenticated(self):
        """Test GET /auth/me without authentication returns 401."""
        response = self.client.get('/api/v1/auth/me')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_current_user_profile_includes_navigation_tabs(self):
        """Test GET /auth/me includes navigation_tabs."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/v1/auth/me')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data['data']
        self.assertIn('navigation_tabs', data)
        # DBOPS profile should have admin tab
        self.assertIn('admin', data['navigation_tabs'])

    def test_get_current_user_profile_includes_is_business_profile(self):
        """Test GET /auth/me includes is_business_profile flag."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/v1/auth/me')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data['data']
        self.assertIn('is_business_profile', data)
        # dbops profile should not be business profile
        self.assertFalse(data['is_business_profile'])

    def test_get_current_user_profile_with_jwt_token(self):
        """Test GET /auth/me with JWT token authentication."""
        from idp_auth.jwt_utils import create_access_token

        token_data = {
            'sub': str(self.user.id),
            'username': self.user.username,
            'profile': self.user.profile,
            'ad_groups': ['dbops'],
        }
        token = create_access_token(token_data)

        response = self.client.get(
            '/api/v1/auth/me',
            HTTP_AUTHORIZATION=f'Bearer {token}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertEqual(response.data['data']['id'], self.user.id)

    def test_get_current_user_profile_expired_jwt_token(self):
        """Test GET /auth/me with expired JWT token returns 401."""
        from idp_auth.jwt_utils import create_access_token

        token_data = {
            'sub': str(self.user.id),
            'username': self.user.username,
            'profile': self.user.profile,
            'ad_groups': [],
        }
        token = create_access_token(token_data, expires_delta=timedelta(seconds=-1))

        response = self.client.get(
            '/api/v1/auth/me',
            HTTP_AUTHORIZATION=f'Bearer {token}'
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@pytest.mark.django_db
@override_settings(
    JWT_SECRET_KEY='test-secret-key',
    JWT_ALGORITHM='HS256',
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30,
    JWT_REFRESH_TOKEN_EXPIRE_HOURS=8,
)
class TestRefreshTokenView(TestCase):
    """Tests for POST /auth/refresh endpoint."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create test user
        self.user = User.objects.create(
            username='test_user',
            display_name='Test User',
            profile='dbops'
        )

    @patch('idp_auth.views.AuditService')
    def test_refresh_token_success(self, mock_audit):
        """Test POST /auth/refresh with valid cookie returns new access token."""
        from idp_auth.jwt_utils import create_refresh_token

        token_data = {
            'sub': str(self.user.id),
            'username': self.user.username,
            'profile': self.user.profile,
            'ad_groups': ['dbops'],
        }
        refresh_token = create_refresh_token(token_data)

        # Set cookie in request
        self.client.cookies['refresh_token'] = refresh_token
        response = self.client.post('/api/v1/auth/refresh')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertIn('access_token', response.data['data'])
        self.assertEqual(response.data['data']['token_type'], 'bearer')

    def test_refresh_token_missing_cookie(self):
        """Test POST /auth/refresh without cookie returns 401."""
        response = self.client.post('/api/v1/auth/refresh')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error']['code'], 'NO_REFRESH_TOKEN')

    def test_refresh_token_invalid_cookie(self):
        """Test POST /auth/refresh with invalid token returns 401."""
        self.client.cookies['refresh_token'] = 'invalid-token'
        response = self.client.post('/api/v1/auth/refresh')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error']['code'], 'INVALID_TOKEN')

    def test_refresh_token_expired_cookie(self):
        """Test POST /auth/refresh with expired token returns 401."""
        from jose import jwt
        from django.conf import settings
        from datetime import datetime, timezone

        token_data = {
            'sub': str(self.user.id),
            'username': self.user.username,
            'profile': self.user.profile,
            'ad_groups': [],
            'type': 'refresh',
        }
        expired_token = jwt.encode(
            {**token_data, 'exp': datetime.now(timezone.utc) - timedelta(hours=1)},
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )

        self.client.cookies['refresh_token'] = expired_token
        response = self.client.post('/api/v1/auth/refresh')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_token_wrong_type(self):
        """Test POST /auth/refresh with access token (wrong type) returns 401."""
        from idp_auth.jwt_utils import create_access_token

        # Create access token instead of refresh
        token_data = {
            'sub': str(self.user.id),
            'username': self.user.username,
            'profile': self.user.profile,
            'ad_groups': [],
        }
        access_token = create_access_token(token_data)

        self.client.cookies['refresh_token'] = access_token
        response = self.client.post('/api/v1/auth/refresh')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@pytest.mark.django_db
@override_settings(
    JWT_SECRET_KEY='test-secret-key',
    JWT_ALGORITHM='HS256',
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30,
    JWT_REFRESH_TOKEN_EXPIRE_HOURS=8,
)
class TestLogoutView(TestCase):
    """Tests for POST /auth/logout endpoint."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

    @patch('idp_auth.views.AuditService')
    def test_logout_success(self, mock_audit):
        """Test POST /auth/logout returns success and clears cookie."""
        response = self.client.post('/api/v1/auth/logout')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertIn('message', response.data['data'])
        self.assertEqual(response.data['data']['message'], 'Deconnexion reussie')

    @patch('idp_auth.views.AuditService')
    def test_logout_clears_cookie(self, mock_audit):
        """Test POST /auth/logout clears refresh_token cookie."""
        from idp_auth.jwt_utils import create_refresh_token

        token_data = {
            'sub': '123',
            'username': 'testuser',
            'profile': 'dbops',
            'ad_groups': [],
        }
        refresh_token = create_refresh_token(token_data)
        self.client.cookies['refresh_token'] = refresh_token

        response = self.client.post('/api/v1/auth/logout')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that delete_cookie was called (cookie should be expired)
        self.assertIn('refresh_token', str(response.cookies))
