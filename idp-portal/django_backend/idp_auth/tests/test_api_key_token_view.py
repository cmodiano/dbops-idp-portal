"""
Tests for APIKeyTokenView (Story 44.2).
POST /api/v1/auth/token - Exchange API key for JWT.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, ANY

from jose import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework import status

from idp_auth.models import User, APIKey
from profiles.models import Profile


@pytest.mark.django_db
@override_settings(
    JWT_SECRET_KEY='test-secret-key',
    JWT_ALGORITHM='HS256',
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30,
    JWT_REFRESH_TOKEN_EXPIRE_HOURS=8,
    RATELIMIT_ENABLED=False,
)
class TestAPIKeyTokenView(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(
            username='api_user',
            display_name='API User',
            profile='dba_applicatif',
        )
        # SEC-3: Create matching Profile so ad_groups uses real ad_group value
        self.profile = Profile.objects.create(
            name='dba_applicatif',
            ad_group='GRP-DBA-APPLICATIF',
        )
        self.api_key_instance, self.raw_key = APIKey.objects.create_key(
            user=self.user,
            name='test-ci-cd',
            scope='executions',
        )

    def test_valid_api_key_returns_jwt(self):
        response = self.client.post(
            '/api/v1/auth/token/',
            HTTP_X_API_KEY=self.raw_key,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['data']
        self.assertIn('access_token', data)
        self.assertEqual(data['token_type'], 'Bearer')
        self.assertEqual(data['expires_in'], 1800)

    def test_missing_api_key_header_returns_401(self):
        response = self.client.post('/api/v1/auth/token/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.json()['error']['code'], 'MISSING_API_KEY')

    def test_empty_api_key_header_returns_401(self):
        response = self.client.post('/api/v1/auth/token/', HTTP_X_API_KEY='   ')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.json()['error']['code'], 'MISSING_API_KEY')

    def test_invalid_api_key_returns_401(self):
        response = self.client.post(
            '/api/v1/auth/token/',
            HTTP_X_API_KEY='definitely-not-a-valid-key-abc123',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.json()['error']['code'], 'INVALID_API_KEY')

    def test_inactive_api_key_returns_401(self):
        self.api_key_instance.is_active = False
        self.api_key_instance.save()
        response = self.client.post(
            '/api/v1/auth/token/',
            HTTP_X_API_KEY=self.raw_key,
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.json()['error']['code'], 'INVALID_API_KEY')

    def test_expired_api_key_returns_401(self):
        self.api_key_instance.expires_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
        self.api_key_instance.save()
        response = self.client.post(
            '/api/v1/auth/token/',
            HTTP_X_API_KEY=self.raw_key,
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.json()['error']['code'], 'INVALID_API_KEY')

    def test_jwt_payload_contains_user_data(self):
        response = self.client.post(
            '/api/v1/auth/token/',
            HTTP_X_API_KEY=self.raw_key,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token = response.json()['data']['access_token']
        payload = jwt.decode(token, 'test-secret-key', algorithms=['HS256'])
        self.assertEqual(payload['sub'], str(self.user.id))
        self.assertEqual(payload['username'], self.user.username)
        self.assertEqual(payload['profile'], self.user.profile)
        # SEC-3: ad_groups now contains real ad_group value from Profile DB, not user.profile string
        self.assertIn(self.profile.ad_group, payload['ad_groups'])
        self.assertNotIn(self.user.profile, payload['ad_groups'])

    def test_rate_limit_throttle_applied(self):
        with patch('core.throttling.ApiKeyTokenThrottle.allow_request', return_value=False), \
             patch('core.throttling.ApiKeyTokenThrottle.wait', return_value=60.0):
            response = self.client.post(
                '/api/v1/auth/token/',
                HTTP_X_API_KEY=self.raw_key,
            )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_audit_logged_on_success(self):
        with patch('idp_auth.views.api_keys.AuditService.create_entry') as mock_audit:
            response = self.client.post(
                '/api/v1/auth/token/',
                HTTP_X_API_KEY=self.raw_key,
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_audit.assert_called_once()
        call_kwargs = mock_audit.call_args[1]
        self.assertEqual(call_kwargs['details']['success'], True)
        self.assertEqual(call_kwargs['details']['key_name'], self.api_key_instance.name)

    def test_audit_logged_on_failure(self):
        with patch('idp_auth.views.api_keys.AuditService.create_entry') as mock_audit:
            response = self.client.post(
                '/api/v1/auth/token/',
                HTTP_X_API_KEY='invalid-key-xyz',
            )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        mock_audit.assert_called_once()
        call_kwargs = mock_audit.call_args[1]
        self.assertEqual(call_kwargs['details']['success'], False)

    def test_raw_key_never_logged(self):
        """AC9: raw_key must never appear in structlog output on success or failure."""
        with patch('idp_auth.views.api_keys.logger') as mock_logger:
            self.client.post('/api/v1/auth/token/', HTTP_X_API_KEY=self.raw_key)
            for call in mock_logger.info.call_args_list + mock_logger.warning.call_args_list:
                args, kwargs = call
                all_values = str(args) + str(kwargs)
                self.assertNotIn(self.raw_key, all_values, 'raw_key found in success log')

        with patch('idp_auth.views.api_keys.logger') as mock_logger:
            self.client.post('/api/v1/auth/token/', HTTP_X_API_KEY='bad-key-should-not-log')
            for call in mock_logger.warning.call_args_list:
                args, kwargs = call
                all_values = str(args) + str(kwargs)
                self.assertNotIn('bad-key-should-not-log', all_values, 'raw_key found in failure log')


@pytest.mark.django_db
@override_settings(
    JWT_SECRET_KEY='test-secret-key',
    JWT_ALGORITHM='HS256',
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30,
    JWT_REFRESH_TOKEN_EXPIRE_HOURS=8,
    RATELIMIT_ENABLED=False,
)
class TestAPIKeyTokenViewSEC3(TestCase):
    """Tests SEC-3: API key token includes real ad_groups from Profile DB."""

    def setUp(self):
        self.client = APIClient()

    def _create_user_and_key(self, profile_name='dba_applicatif'):
        user = User.objects.create(username='api_user_sec3', profile=profile_name)
        api_key, raw_key = APIKey.objects.create_key(user=user, name='test-key')
        return user, api_key, raw_key

    def test_59_3_a_profile_found_in_db_uses_real_ad_group(self):
        """59-3-a: Profile found in DB → ad_groups contains p.ad_group, not user.profile."""
        profile, _ = Profile.objects.get_or_create(
            name='dba_applicatif',
            defaults={'ad_group': 'CN=GRP-DBA-APPLICATIF,OU=Groups,DC=example,DC=com'},
        )
        user, _, raw_key = self._create_user_and_key('dba_applicatif')

        response = self.client.post('/api/v1/auth/token/', HTTP_X_API_KEY=raw_key)

        self.assertEqual(response.status_code, 200)
        token = response.json()['data']['access_token']
        payload = jwt.decode(token, 'test-secret-key', algorithms=['HS256'])

        self.assertIn(profile.ad_group, payload['ad_groups'])
        self.assertNotIn('dba_applicatif', payload['ad_groups'])

    def test_59_3_b_no_profile_in_db_fallback_to_user_profile(self):
        """59-3-b: No Profile in DB → fallback to [user.profile], warning logged."""
        user, _, raw_key = self._create_user_and_key('unknown_profile')

        with patch('idp_auth.views.api_keys.logger') as mock_logger:
            response = self.client.post('/api/v1/auth/token/', HTTP_X_API_KEY=raw_key)

        self.assertEqual(response.status_code, 200)
        token = response.json()['data']['access_token']
        payload = jwt.decode(token, 'test-secret-key', algorithms=['HS256'])

        self.assertIn('unknown_profile', payload['ad_groups'])

        mock_logger.warning.assert_any_call(
            'api_key_token_no_profile_found',
            user_profile='unknown_profile',
            user_id=user.id,
            correlation_id=ANY,
        )

    def test_59_3_c_multi_profile_all_ad_groups_included(self):
        """59-3-c: Two profiles resolved → ad_groups contains both ad_group values."""
        profile1 = Profile.objects.create(name='dbops', ad_group='GRP-DBOPS-PRIMARY')
        # Second profile that also matches 'dbops' via ad_group field
        profile2 = Profile.objects.create(name='dbops_extended', ad_group='dbops')

        user, _, raw_key = self._create_user_and_key('dbops')

        response = self.client.post('/api/v1/auth/token/', HTTP_X_API_KEY=raw_key)

        self.assertEqual(response.status_code, 200)
        token = response.json()['data']['access_token']
        payload = jwt.decode(token, 'test-secret-key', algorithms=['HS256'])

        self.assertIn(profile1.ad_group, payload['ad_groups'])
        self.assertIn(profile2.ad_group, payload['ad_groups'])

    def test_59_3_d_other_token_fields_unchanged(self):
        """59-3-d: sub, username, profile fields unchanged by SEC-3 fix."""
        # Profile intentionally not created: ad_groups is populated from user.profile fallback
        # when no Profile exists in DB (tests token structure without Profile resolution).
        user, _, raw_key = self._create_user_and_key('dba_applicatif')

        response = self.client.post('/api/v1/auth/token/', HTTP_X_API_KEY=raw_key)

        self.assertEqual(response.status_code, 200)
        token = response.json()['data']['access_token']
        payload = jwt.decode(token, 'test-secret-key', algorithms=['HS256'])

        self.assertEqual(payload['sub'], str(user.id))
        self.assertEqual(payload['username'], user.username)
        self.assertEqual(payload['profile'], user.profile)
        # ad_groups must be present and non-empty (actual value depends on DB state for 'dba_applicatif')
        self.assertIn('ad_groups', payload)
        self.assertIsInstance(payload['ad_groups'], list)
        self.assertGreater(len(payload['ad_groups']), 0)
