"""
Story 17.12: Feature Flag Service and API tests.

Tests cover:
- FeatureFlagService: is_enabled, rollout, cache, global disable
- API: GET list (admin), GET status (auth), PATCH update (admin), permissions
- Startup validation
- Cache invalidation
"""

from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient

from core import feature_flags
from core.models import AuditLog, FeatureFlag
from core.startup_checks import validate_feature_flags_config
from tests.factories import FeatureFlagFactory, UserFactory


# ============================================================================
# Local Fixtures (core/tests/ has no conftest with shared fixtures)
# ============================================================================

@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def db_user(db):
    return UserFactory.create(profile='DBA')


@pytest.fixture
def admin_user(db):
    return UserFactory.create(profile='DBOPS', username='admin_user')


@pytest.fixture
def api_client_authenticated(api_client, db_user):
    api_client.force_authenticate(user=db_user)
    return api_client


@pytest.fixture
def api_client_admin(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    return api_client


# ============================================================================
# Model Tests
# ============================================================================

@pytest.mark.django_db
class TestFeatureFlagModel:
    def test_create_feature_flag(self):
        flag = FeatureFlagFactory.create(
            flag_key='test_feature',
            enabled=True,
            rollout_percent=50,
        )
        assert flag.flag_key == 'test_feature'
        assert flag.enabled is True
        assert flag.rollout_percent == 50
        assert flag.pk is not None

    def test_str_representation_enabled(self):
        flag = FeatureFlagFactory.create(flag_key='my_flag', enabled=True, rollout_percent=75)
        assert str(flag) == 'my_flag (ON, 75%)'

    def test_str_representation_disabled(self):
        flag = FeatureFlagFactory.create(flag_key='my_flag', enabled=False, rollout_percent=100)
        assert str(flag) == 'my_flag (OFF, 100%)'

    def test_unique_flag_key(self):
        FeatureFlagFactory.create(flag_key='unique_key')
        with pytest.raises(Exception):  # IntegrityError
            FeatureFlagFactory.create(flag_key='unique_key')

    def test_clean_valid_rollout(self):
        flag = FeatureFlagFactory.build(rollout_percent=50)
        flag.clean()  # Should not raise

    def test_clean_invalid_rollout_negative(self):
        flag = FeatureFlagFactory.build(rollout_percent=-1)
        with pytest.raises(ValidationError):
            flag.clean()

    def test_clean_invalid_rollout_over_100(self):
        flag = FeatureFlagFactory.build(rollout_percent=101)
        with pytest.raises(ValidationError):
            flag.clean()

    def test_ordering_by_flag_key(self):
        FeatureFlagFactory.create(flag_key='z_flag')
        FeatureFlagFactory.create(flag_key='a_flag')
        flags = list(FeatureFlag.objects.values_list('flag_key', flat=True))
        assert flags == ['a_flag', 'z_flag']


# ============================================================================
# Feature Flag Service Tests (env source)
# ============================================================================

@pytest.mark.django_db
class TestFeatureFlagServiceEnv:
    def setup_method(self):
        cache.clear()

    @override_settings(
        FEATURE_FLAGS_SOURCE='env',
        FEATURE_FLAGS_ENABLED=True,
        FEATURE_FLAGS='{"new_ui":{"enabled":true,"rollout_percent":100}}',
    )
    def test_is_enabled_returns_true_when_flag_enabled(self):
        assert feature_flags.is_enabled('new_ui') is True

    @override_settings(
        FEATURE_FLAGS_SOURCE='env',
        FEATURE_FLAGS_ENABLED=True,
        FEATURE_FLAGS='{"new_ui":{"enabled":false,"rollout_percent":100}}',
    )
    def test_is_enabled_returns_false_when_flag_disabled(self):
        assert feature_flags.is_enabled('new_ui') is False

    @override_settings(
        FEATURE_FLAGS_SOURCE='env',
        FEATURE_FLAGS_ENABLED=True,
        FEATURE_FLAGS='{}',
    )
    def test_is_enabled_returns_false_for_unknown_flag(self):
        assert feature_flags.is_enabled('nonexistent') is False

    @override_settings(
        FEATURE_FLAGS_SOURCE='env',
        FEATURE_FLAGS_ENABLED=False,
    )
    def test_globally_disabled_returns_false(self):
        assert feature_flags.is_enabled('anything') is False

    @override_settings(
        FEATURE_FLAGS_SOURCE='env',
        FEATURE_FLAGS_ENABLED=True,
        FEATURE_FLAGS='{"gradual":{"enabled":true,"rollout_percent":0}}',
    )
    def test_rollout_0_percent_returns_false(self):
        assert feature_flags.is_enabled('gradual', {'user_id': 'user_1'}) is False

    @override_settings(
        FEATURE_FLAGS_SOURCE='env',
        FEATURE_FLAGS_ENABLED=True,
        FEATURE_FLAGS='{"full":{"enabled":true,"rollout_percent":100}}',
    )
    def test_rollout_100_percent_returns_true(self):
        assert feature_flags.is_enabled('full', {'user_id': 'user_1'}) is True

    @override_settings(
        FEATURE_FLAGS_SOURCE='env',
        FEATURE_FLAGS_ENABLED=True,
        FEATURE_FLAGS='{"gradual":{"enabled":true,"rollout_percent":50}}',
    )
    def test_rollout_50_percent_distribution(self):
        """~50% of users should be enabled (±15% tolerance for 100 samples)."""
        enabled_count = sum(
            feature_flags.is_enabled('gradual', {'user_id': f'user_{i}'})
            for i in range(100)
        )
        assert 35 <= enabled_count <= 65, f"Expected ~50%, got {enabled_count}%"

    @override_settings(
        FEATURE_FLAGS_SOURCE='env',
        FEATURE_FLAGS_ENABLED=True,
        FEATURE_FLAGS='{"test":{"enabled":true,"rollout_percent":50}}',
    )
    def test_rollout_consistent_for_same_user(self):
        """Same user always gets same result (consistent hashing)."""
        results = [feature_flags.is_enabled('test', {'user_id': 'stable_user'}) for _ in range(10)]
        assert len(set(results)) == 1, "Rollout should be consistent for same user"

    @override_settings(
        FEATURE_FLAGS_SOURCE='env',
        FEATURE_FLAGS_ENABLED=True,
        FEATURE_FLAGS='not valid json',
    )
    def test_invalid_json_returns_empty(self):
        assert feature_flags.is_enabled('anything') is False

    @override_settings(
        FEATURE_FLAGS_SOURCE='env',
        FEATURE_FLAGS_ENABLED=True,
        FEATURE_FLAGS='{"test":{"enabled":true,"rollout_percent":100}}',
    )
    def test_cache_is_used(self):
        feature_flags.is_enabled('test')
        cached = cache.get('feature_flags:all:env')
        assert cached is not None
        assert 'test' in cached


# ============================================================================
# Feature Flag Service Tests (database source)
# ============================================================================

@pytest.mark.django_db
class TestFeatureFlagServiceDatabase:
    def setup_method(self):
        cache.clear()

    @override_settings(
        FEATURE_FLAGS_SOURCE='database',
        FEATURE_FLAGS_ENABLED=True,
    )
    def test_is_enabled_from_database(self):
        FeatureFlagFactory.create(flag_key='db_flag', enabled=True, rollout_percent=100)
        assert feature_flags.is_enabled('db_flag') is True

    @override_settings(
        FEATURE_FLAGS_SOURCE='database',
        FEATURE_FLAGS_ENABLED=True,
    )
    def test_is_disabled_from_database(self):
        FeatureFlagFactory.create(flag_key='db_flag', enabled=False, rollout_percent=100)
        assert feature_flags.is_enabled('db_flag') is False

    @override_settings(
        FEATURE_FLAGS_SOURCE='database',
        FEATURE_FLAGS_ENABLED=True,
    )
    def test_get_all_flags_status_from_database(self):
        FeatureFlagFactory.create(flag_key='flag_a', enabled=True, rollout_percent=100)
        FeatureFlagFactory.create(flag_key='flag_b', enabled=False, rollout_percent=100)
        result = feature_flags.get_all_flags_status()
        assert result['flag_a'] is True
        assert result['flag_b'] is False


# ============================================================================
# Cache Invalidation Tests
# ============================================================================

@pytest.mark.django_db
class TestFeatureFlagCacheInvalidation:
    def setup_method(self):
        cache.clear()

    @override_settings(
        FEATURE_FLAGS_SOURCE='env',
        FEATURE_FLAGS_ENABLED=True,
        FEATURE_FLAGS='{"cached_flag":{"enabled":true,"rollout_percent":100}}',
    )
    def test_invalidate_specific_flag(self):
        feature_flags.is_enabled('cached_flag')
        assert cache.get('feature_flag:cached_flag:env') is not None

        feature_flags.invalidate_cache('cached_flag')
        assert cache.get('feature_flag:cached_flag:env') is None
        assert cache.get('feature_flags:all:env') is None

    @override_settings(
        FEATURE_FLAGS_SOURCE='env',
        FEATURE_FLAGS_ENABLED=True,
        FEATURE_FLAGS='{"a":{"enabled":true},"b":{"enabled":true}}',
    )
    def test_invalidate_all(self):
        feature_flags.is_enabled('a')
        feature_flags.is_enabled('b')
        feature_flags.invalidate_cache()
        assert cache.get('feature_flags:all:env') is None


# ============================================================================
# API Tests - Feature Flag List (Admin)
# ============================================================================

@pytest.mark.django_db
class TestFeatureFlagListAPI:

    @override_settings(
        FEATURE_FLAGS_SOURCE='env',
        FEATURE_FLAGS_ENABLED=True,
        FEATURE_FLAGS='{"ui_v2":{"enabled":true,"rollout_percent":80}}',
    )
    def test_list_flags_admin(self, api_client_admin):
        cache.clear()
        response = api_client_admin.get('/api/v1/feature-flags/')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()['data']
        assert len(data) == 1
        assert data[0]['flag_key'] == 'ui_v2'
        assert data[0]['enabled'] is True
        assert data[0]['rollout_percent'] == 80

    @override_settings(
        FEATURE_FLAGS_SOURCE='database',
        FEATURE_FLAGS_ENABLED=True,
    )
    def test_list_flags_database_source(self, api_client_admin):
        cache.clear()
        FeatureFlagFactory.create(flag_key='db_flag_1', enabled=True, rollout_percent=100)
        response = api_client_admin.get('/api/v1/feature-flags/')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()['data']
        assert len(data) == 1
        assert data[0]['flag_key'] == 'db_flag_1'

    def test_list_flags_unauthenticated(self, api_client):
        response = api_client.get('/api/v1/feature-flags/')
        assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    def test_list_flags_non_admin(self, api_client_authenticated):
        response = api_client_authenticated.get('/api/v1/feature-flags/')
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ============================================================================
# API Tests - Feature Flag Status (Authenticated)
# ============================================================================

@pytest.mark.django_db
class TestFeatureFlagStatusAPI:

    @override_settings(
        FEATURE_FLAGS_SOURCE='env',
        FEATURE_FLAGS_ENABLED=True,
        FEATURE_FLAGS='{"feature_a":{"enabled":true,"rollout_percent":100},"feature_b":{"enabled":false}}',
    )
    def test_status_authenticated_user(self, api_client_authenticated):
        cache.clear()
        response = api_client_authenticated.get('/api/v1/feature-flags/status/')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()['data']
        assert data['feature_a'] is True
        assert data['feature_b'] is False

    def test_status_unauthenticated(self, api_client):
        response = api_client.get('/api/v1/feature-flags/status/')
        assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


# ============================================================================
# API Tests - Feature Flag Update (Admin PATCH)
# ============================================================================

@pytest.mark.django_db
class TestFeatureFlagUpdateAPI:

    @override_settings(
        FEATURE_FLAGS_SOURCE='database',
        FEATURE_FLAGS_ENABLED=True,
    )
    def test_patch_toggle_enabled(self, api_client_admin):
        cache.clear()
        FeatureFlagFactory.create(flag_key='toggle_me', enabled=False, rollout_percent=100)
        response = api_client_admin.patch(
            '/api/v1/feature-flags/toggle_me/',
            data={'enabled': True},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK
        result = response.json()['data']
        assert result['enabled'] is True
        assert result['flag_key'] == 'toggle_me'

    @override_settings(
        FEATURE_FLAGS_SOURCE='database',
        FEATURE_FLAGS_ENABLED=True,
    )
    def test_patch_update_rollout(self, api_client_admin):
        cache.clear()
        FeatureFlagFactory.create(flag_key='rollout_flag', enabled=True, rollout_percent=100)
        response = api_client_admin.patch(
            '/api/v1/feature-flags/rollout_flag/',
            data={'rollout_percent': 50},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK
        result = response.json()['data']
        assert result['rollout_percent'] == 50

    @override_settings(
        FEATURE_FLAGS_SOURCE='database',
        FEATURE_FLAGS_ENABLED=True,
    )
    def test_patch_creates_new_flag_in_database(self, api_client_admin):
        cache.clear()
        response = api_client_admin.patch(
            '/api/v1/feature-flags/new_flag/',
            data={'enabled': True, 'rollout_percent': 75},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK
        assert FeatureFlag.objects.filter(flag_key='new_flag').exists()

    @override_settings(
        FEATURE_FLAGS_SOURCE='database',
        FEATURE_FLAGS_ENABLED=True,
    )
    def test_patch_creates_audit_trail(self, api_client_admin):
        cache.clear()
        api_client_admin.patch(
            '/api/v1/feature-flags/audit_test/',
            data={'enabled': True},
            format='json',
        )
        audit = AuditLog.objects.filter(entity_type='feature_flag').first()
        assert audit is not None
        details = audit.get_details()
        assert details['flag_key'] == 'audit_test'

    @override_settings(
        FEATURE_FLAGS_SOURCE='database',
        FEATURE_FLAGS_ENABLED=True,
    )
    def test_patch_invalidates_cache(self, api_client_admin):
        FeatureFlagFactory.create(flag_key='cache_test', enabled=True)
        cache.set('feature_flag:cache_test:database', {'enabled': True}, 300)
        cache.set('feature_flags:all:database', {'cache_test': {'enabled': True}}, 300)

        api_client_admin.patch(
            '/api/v1/feature-flags/cache_test/',
            data={'enabled': False},
            format='json',
        )
        assert cache.get('feature_flag:cache_test:database') is None
        assert cache.get('feature_flags:all:database') is None

    def test_patch_invalid_rollout_over_100(self, api_client_admin):
        response = api_client_admin.patch(
            '/api/v1/feature-flags/test_flag/',
            data={'rollout_percent': 150},
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_patch_invalid_rollout_negative(self, api_client_admin):
        response = api_client_admin.patch(
            '/api/v1/feature-flags/test_flag/',
            data={'rollout_percent': -10},
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_patch_invalid_flag_key(self, api_client_admin):
        response = api_client_admin.patch(
            '/api/v1/feature-flags/INVALID KEY!/',
            data={'enabled': True},
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_patch_no_changes(self, api_client_admin):
        response = api_client_admin.patch(
            '/api/v1/feature-flags/test_flag/',
            data={},
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_patch_unauthenticated(self, api_client):
        response = api_client.patch(
            '/api/v1/feature-flags/test_flag/',
            data={'enabled': True},
            format='json',
        )
        assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    def test_patch_non_admin(self, api_client_authenticated):
        response = api_client_authenticated.patch(
            '/api/v1/feature-flags/test_flag/',
            data={'enabled': True},
            format='json',
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_patch_invalid_enabled_type(self, api_client_admin):
        response = api_client_admin.patch(
            '/api/v1/feature-flags/test_flag/',
            data={'enabled': 'yes'},
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ============================================================================
# API Tests - Feature Flag Update with source=env (PATCH)
# Story 20.7 Task 4: Verify env-source updates only affect cache,
# do NOT write to database, and still create audit trail.
# ============================================================================

@pytest.mark.django_db
class TestFeatureFlagUpdateEnvSourceAPI:

    def setup_method(self):
        cache.clear()

    @override_settings(
        FEATURE_FLAGS_SOURCE='env',
        FEATURE_FLAGS_ENABLED=True,
        FEATURE_FLAGS='{"env_flag":{"enabled":false,"rollout_percent":100}}',
    )
    def test_patch_env_source_updates_cache_only(self, api_client_admin):
        """PATCH with source=env should update cache without database write."""
        response = api_client_admin.patch(
            '/api/v1/feature-flags/env_flag/',
            data={'enabled': True},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK
        result = response.json()['data']
        assert result['flag_key'] == 'env_flag'
        assert result['enabled'] is True
        assert result['updated_at'] is not None

    @override_settings(
        FEATURE_FLAGS_SOURCE='env',
        FEATURE_FLAGS_ENABLED=True,
        FEATURE_FLAGS='{"env_flag":{"enabled":true,"rollout_percent":100}}',
    )
    def test_patch_env_source_no_database_write(self, api_client_admin):
        """Env source PATCH must NOT create FeatureFlag objects in database."""
        initial_count = FeatureFlag.objects.count()
        api_client_admin.patch(
            '/api/v1/feature-flags/env_flag/',
            data={'enabled': False},
            format='json',
        )
        assert FeatureFlag.objects.count() == initial_count

    @override_settings(
        FEATURE_FLAGS_SOURCE='env',
        FEATURE_FLAGS_ENABLED=True,
        FEATURE_FLAGS='{"cache_env_flag":{"enabled":true,"rollout_percent":100}}',
    )
    def test_patch_env_source_invalidates_cache(self, api_client_admin):
        """PATCH should invalidate per-flag and global cache."""
        feature_flags.is_enabled('cache_env_flag')
        assert cache.get('feature_flags:all:env') is not None

        api_client_admin.patch(
            '/api/v1/feature-flags/cache_env_flag/',
            data={'enabled': False},
            format='json',
        )
        assert cache.get('feature_flag:cache_env_flag:env') is None
        assert cache.get('feature_flags:all:env') is None

    @override_settings(
        FEATURE_FLAGS_SOURCE='env',
        FEATURE_FLAGS_ENABLED=True,
        FEATURE_FLAGS='{"audit_env_flag":{"enabled":false,"rollout_percent":50}}',
    )
    def test_patch_env_source_creates_audit_trail(self, api_client_admin):
        """Audit log must be created even when source=env."""
        api_client_admin.patch(
            '/api/v1/feature-flags/audit_env_flag/',
            data={'enabled': True},
            format='json',
        )
        audit = AuditLog.objects.filter(
            entity_type='feature_flag',
        ).order_by('-id').first()
        assert audit is not None
        details = audit.get_details()
        assert details['flag_key'] == 'audit_env_flag'
        assert details['enabled'] is True


# ============================================================================
# Startup Validation Tests
# ============================================================================

class TestFeatureFlagsStartupValidation:

    def test_valid_env_config(self):
        with patch.dict('os.environ', {
            'FEATURE_FLAGS_SOURCE': 'env',
            'FEATURE_FLAGS_ENABLED': 'true',
            'FEATURE_FLAGS_CACHE_TTL': '300',
            'FEATURE_FLAGS': '{"test":{"enabled":true}}',
        }):
            validate_feature_flags_config()  # Should not raise

    def test_valid_database_config(self):
        with patch.dict('os.environ', {
            'FEATURE_FLAGS_SOURCE': 'database',
            'FEATURE_FLAGS_ENABLED': 'true',
            'FEATURE_FLAGS_CACHE_TTL': '300',
        }):
            validate_feature_flags_config()  # Should not raise

    def test_invalid_source(self):
        from django.core.exceptions import ImproperlyConfigured
        with patch.dict('os.environ', {'FEATURE_FLAGS_SOURCE': 'redis'}):
            with pytest.raises(ImproperlyConfigured, match="FEATURE_FLAGS_SOURCE"):
                validate_feature_flags_config()

    def test_invalid_enabled_value(self):
        from django.core.exceptions import ImproperlyConfigured
        with patch.dict('os.environ', {'FEATURE_FLAGS_ENABLED': 'maybe'}):
            with pytest.raises(ImproperlyConfigured, match="FEATURE_FLAGS_ENABLED"):
                validate_feature_flags_config()

    def test_invalid_cache_ttl(self):
        from django.core.exceptions import ImproperlyConfigured
        with patch.dict('os.environ', {'FEATURE_FLAGS_CACHE_TTL': 'abc'}):
            with pytest.raises(ImproperlyConfigured, match="FEATURE_FLAGS_CACHE_TTL"):
                validate_feature_flags_config()

    def test_negative_cache_ttl(self):
        from django.core.exceptions import ImproperlyConfigured
        with patch.dict('os.environ', {'FEATURE_FLAGS_CACHE_TTL': '-1'}):
            with pytest.raises(ImproperlyConfigured, match="FEATURE_FLAGS_CACHE_TTL"):
                validate_feature_flags_config()

    def test_invalid_json_production_raises(self):
        from django.core.exceptions import ImproperlyConfigured
        with patch.dict('os.environ', {
            'APP_ENV': 'production',
            'FEATURE_FLAGS_SOURCE': 'env',
            'FEATURE_FLAGS': 'not json',
        }):
            with pytest.raises(ImproperlyConfigured, match="FEATURE_FLAGS JSON"):
                validate_feature_flags_config()

    def test_invalid_json_dev_warns(self):
        """In dev mode, invalid JSON should warn but not fail."""
        with patch.dict('os.environ', {
            'APP_ENV': 'development',
            'FEATURE_FLAGS_SOURCE': 'env',
            'FEATURE_FLAGS': 'not json',
        }):
            validate_feature_flags_config()  # Should not raise


# ============================================================================
# Rollout Logic Tests
# ============================================================================

class TestRolloutLogic:

    def test_get_rollout_status_0_percent(self):
        result = feature_flags.get_rollout_status('test', 'user_1', rollout_percent=0)
        assert result is False

    def test_get_rollout_status_100_percent(self):
        result = feature_flags.get_rollout_status('test', 'user_1', rollout_percent=100)
        assert result is True

    def test_get_rollout_status_consistent(self):
        """Same flag+user always returns same result."""
        results = [feature_flags.get_rollout_status('flag_x', 'user_42', 50) for _ in range(20)]
        assert len(set(results)) == 1

    def test_get_rollout_status_different_users(self):
        """Different users may get different results at 50%."""
        results = set()
        for i in range(50):
            results.add(feature_flags.get_rollout_status('test_flag', f'user_{i}', 50))
        assert len(results) == 2  # Both True and False should appear

    @pytest.mark.django_db
    def test_get_rollout_status_none_rollout_with_missing_flag(self):
        """Lines 298-300: get_rollout_status() with rollout_percent=None and missing flag returns False."""
        cache.clear()
        with override_settings(
            FEATURE_FLAGS_SOURCE='env',
            FEATURE_FLAGS_ENABLED=True,
            FEATURE_FLAGS='{}',
        ):
            result = feature_flags.get_rollout_status('missing_flag', 'user_1', rollout_percent=None)
            assert result is False

    @pytest.mark.django_db
    def test_get_rollout_status_none_rollout_uses_flag_config(self):
        """Line 301: get_rollout_status() with rollout_percent=None reads rollout_percent from flag config."""
        cache.clear()
        with override_settings(
            FEATURE_FLAGS_SOURCE='env',
            FEATURE_FLAGS_ENABLED=True,
            FEATURE_FLAGS='{"exists_flag":{"enabled":true,"rollout_percent":100}}',
        ):
            result = feature_flags.get_rollout_status('exists_flag', 'user_1', rollout_percent=None)
            assert result is True


# ============================================================================
# Lock Timeout and Validation Tests
# ============================================================================

class TestGetLockTimeout:

    def test_invalid_lock_timeout_negative_returns_default(self):
        """Lines 72-77: negative lock timeout logs warning and returns default."""
        with override_settings(FEATURE_FLAGS_LOCK_TIMEOUT=-5):
            result = feature_flags._get_lock_timeout()
            assert result == feature_flags.DEFAULT_LOCK_TIMEOUT

    def test_invalid_lock_timeout_string_returns_default(self):
        """Lines 72-77: string lock timeout logs warning and returns default."""
        with override_settings(FEATURE_FLAGS_LOCK_TIMEOUT="bad"):
            result = feature_flags._get_lock_timeout()
            assert result == feature_flags.DEFAULT_LOCK_TIMEOUT

    def test_invalid_lock_timeout_zero_returns_default(self):
        """Lines 71-77: zero lock timeout (not > 0) logs warning and returns default."""
        with override_settings(FEATURE_FLAGS_LOCK_TIMEOUT=0):
            result = feature_flags._get_lock_timeout()
            assert result == feature_flags.DEFAULT_LOCK_TIMEOUT

    def test_valid_lock_timeout_returns_value(self):
        """Valid lock timeout returns the configured value."""
        with override_settings(FEATURE_FLAGS_LOCK_TIMEOUT=10):
            result = feature_flags._get_lock_timeout()
            assert result == 10


# ============================================================================
# Load Flags from Env — Edge Cases
# ============================================================================

class TestLoadFlagsFromEnvEdgeCases:

    def test_load_flags_empty_string_returns_empty(self):
        """Line 85: empty FEATURE_FLAGS returns {}."""
        with override_settings(FEATURE_FLAGS=''):
            result = feature_flags._load_flags_from_env()
            assert result == {}

    def test_load_flags_none_returns_empty(self):
        """Line 85: None FEATURE_FLAGS returns {}."""
        with override_settings(FEATURE_FLAGS=None):
            result = feature_flags._load_flags_from_env()
            assert result == {}

    def test_load_flags_non_dict_json_returns_empty(self):
        """Lines 89-90: JSON list returns {} with warning."""
        with override_settings(FEATURE_FLAGS='["a", "b"]'):
            result = feature_flags._load_flags_from_env()
            assert result == {}


# ============================================================================
# Load Flags from Database — Exception Paths
# ============================================================================

@pytest.mark.django_db
class TestLoadFlagsFromDatabaseExceptions:

    def setup_method(self):
        cache.clear()

    def test_load_flags_database_error_returns_empty(self):
        """Lines 107-115: DatabaseError in _load_flags_from_database() returns {}."""
        from django.db import DatabaseError
        from unittest.mock import MagicMock

        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(side_effect=DatabaseError("DB connection failed"))

        with patch('core.feature_flags.FeatureFlag', create=True) as mock_ff_cls:
            mock_ff_cls.objects.all.return_value = mock_qs
            # Patch the local import inside _load_flags_from_database
            with patch.dict('sys.modules', {'core.models': type('m', (), {'FeatureFlag': mock_ff_cls})}):
                pass  # We need a different approach

        # Directly patch what _load_flags_from_database uses via its local import
        import core.models as core_models
        _original_objects = core_models.FeatureFlag.objects

        mock_manager = patch.object(core_models.FeatureFlag, 'objects')
        with mock_manager as mock_objects:
            mock_objects.all.side_effect = DatabaseError("DB connection failed")
            result = feature_flags._load_flags_from_database()
            assert result == {}

    def test_load_flags_unexpected_error_returns_empty(self):
        """Lines 116-127: unexpected exception in _load_flags_from_database() returns {}."""
        import core.models as core_models
        with patch.object(core_models.FeatureFlag, 'objects') as mock_objects:
            mock_objects.all.side_effect = RuntimeError("Unexpected ORM error")
            result = feature_flags._load_flags_from_database()
            assert result == {}


# ============================================================================
# Anti-Thundering Herd — Lock Wait Path
# ============================================================================

@pytest.mark.django_db
class TestGetAllFlagsLockWait:

    def setup_method(self):
        cache.clear()

    @override_settings(
        FEATURE_FLAGS_SOURCE='env',
        FEATURE_FLAGS_ENABLED=True,
        FEATURE_FLAGS='{"herd_flag":{"enabled":true,"rollout_percent":100}}',
        FEATURE_FLAGS_LOCK_TIMEOUT=1,
    )
    def test_lock_wait_succeeds_when_cache_populated(self):
        """Lines 190-204: when lock is held by another, wait loop finds cached value."""
        source = 'env'
        cache_key = f'feature_flags:all:{source}'
        lock_key = f'{cache_key}:lock'

        # Simulate another worker holding the lock
        cache.add(lock_key, 'other-worker-token', 5)

        # Pre-populate cache as if the lock holder just wrote it
        expected_flags = {'herd_flag': {'enabled': True, 'rollout_percent': 100}}
        cache.set(cache_key, expected_flags, 300)

        result = feature_flags._get_all_flags()
        assert result == expected_flags

    @override_settings(
        FEATURE_FLAGS_SOURCE='env',
        FEATURE_FLAGS_ENABLED=True,
        FEATURE_FLAGS='{"herd_flag":{"enabled":true,"rollout_percent":100}}',
        FEATURE_FLAGS_LOCK_TIMEOUT=1,
    )
    def test_lock_wait_cache_hit_in_loop_returns_cached(self):
        """Lines 196-204: cache gets populated while waiting in loop — returns it."""
        source = 'env'
        cache_key = f'feature_flags:all:{source}'
        lock_key = f'{cache_key}:lock'

        # Simulate another worker holding the lock
        cache.add(lock_key, 'other-worker-token', 5)

        # cache.get() will return None first, then the flags on subsequent call
        expected_flags = {'herd_flag': {'enabled': True, 'rollout_percent': 100}}
        call_count = [0]
        original_get = cache.get

        def mock_cache_get(key, *args, **kwargs):
            if key == cache_key:
                call_count[0] += 1
                if call_count[0] >= 2:
                    return expected_flags
                return None
            return original_get(key, *args, **kwargs)

        import unittest.mock as umock
        with umock.patch.object(feature_flags, 'MAX_LOCK_WAIT', 1.0), \
             umock.patch.object(feature_flags, 'LOCK_WAIT_INTERVAL', 0.01), \
             umock.patch('core.feature_flags.cache') as mock_cache:
            mock_cache.get.side_effect = mock_cache_get
            mock_cache.add.return_value = False  # Lock not acquired
            result = feature_flags._get_all_flags()

        # The cache was populated while waiting
        assert result == expected_flags

    @override_settings(
        FEATURE_FLAGS_SOURCE='env',
        FEATURE_FLAGS_ENABLED=True,
        FEATURE_FLAGS='{"timeout_flag":{"enabled":true,"rollout_percent":100}}',
        FEATURE_FLAGS_LOCK_TIMEOUT=1,
    )
    def test_lock_wait_timeout_falls_back_to_load(self):
        """Lines 206-217: lock wait timeout triggers direct load (availability > consistency)."""
        source = 'env'
        cache_key = f'feature_flags:all:{source}'
        lock_key = f'{cache_key}:lock'

        # Simulate another worker holding the lock — never releasing it
        cache.add(lock_key, 'stuck-worker-token', 10)
        # Do NOT populate cache — force timeout path

        import unittest.mock as umock

        # Speed up the test: patch MAX_LOCK_WAIT and LOCK_WAIT_INTERVAL
        with umock.patch.object(feature_flags, 'MAX_LOCK_WAIT', 0.1), \
             umock.patch.object(feature_flags, 'LOCK_WAIT_INTERVAL', 0.05):
            result = feature_flags._get_all_flags()

        # Should fall back to direct load from env
        assert isinstance(result, dict)

    @override_settings(
        FEATURE_FLAGS_SOURCE='database',
        FEATURE_FLAGS_ENABLED=True,
        FEATURE_FLAGS_LOCK_TIMEOUT=1,
    )
    def test_lock_wait_timeout_database_falls_back_to_load(self):
        """Lines 215-216: lock timeout for database source falls back to _load_flags_from_database()."""
        source = 'database'
        cache_key = f'feature_flags:all:{source}'
        lock_key = f'{cache_key}:lock'

        # Simulate another worker holding the lock
        cache.add(lock_key, 'stuck-db-worker-token', 10)

        import unittest.mock as umock

        with umock.patch.object(feature_flags, 'MAX_LOCK_WAIT', 0.1), \
             umock.patch.object(feature_flags, 'LOCK_WAIT_INTERVAL', 0.05), \
             umock.patch('core.feature_flags._load_flags_from_database', return_value={'db_flag': {'enabled': True}}) as mock_load:
            result = feature_flags._get_all_flags()

        mock_load.assert_called_once()
        assert result == {'db_flag': {'enabled': True}}


# ============================================================================
# is_enabled() — Partial Rollout Without User Context
# ============================================================================

@pytest.mark.django_db
class TestIsEnabledPartialRolloutNoUser:

    def setup_method(self):
        cache.clear()

    @override_settings(
        FEATURE_FLAGS_SOURCE='env',
        FEATURE_FLAGS_ENABLED=True,
        FEATURE_FLAGS='{"partial":{"enabled":true,"rollout_percent":50}}',
    )
    def test_partial_rollout_no_context_returns_false(self):
        """Lines 273->276, 279-280: partial rollout with no context returns False."""
        result = feature_flags.is_enabled('partial')
        assert result is False

    @override_settings(
        FEATURE_FLAGS_SOURCE='env',
        FEATURE_FLAGS_ENABLED=True,
        FEATURE_FLAGS='{"partial":{"enabled":true,"rollout_percent":50}}',
    )
    def test_partial_rollout_empty_context_returns_false(self):
        """Lines 273->276, 279-280: partial rollout with empty context dict returns False."""
        result = feature_flags.is_enabled('partial', {})
        assert result is False

    @override_settings(
        FEATURE_FLAGS_SOURCE='env',
        FEATURE_FLAGS_ENABLED=True,
        FEATURE_FLAGS='{"partial":{"enabled":true,"rollout_percent":50}}',
    )
    def test_partial_rollout_context_without_user_id_returns_false(self):
        """Lines 273->276, 279-280: partial rollout with context missing user_id returns False."""
        result = feature_flags.is_enabled('partial', {'profile': 'admin'})
        assert result is False


# ============================================================================
# get_all_flags_status() — Globally Disabled
# ============================================================================

class TestGetAllFlagsStatusDisabled:

    def test_get_all_flags_status_globally_disabled_returns_empty(self):
        """Line 321: get_all_flags_status() returns {} when feature flags globally disabled."""
        with override_settings(FEATURE_FLAGS_ENABLED=False):
            result = feature_flags.get_all_flags_status()
            assert result == {}
