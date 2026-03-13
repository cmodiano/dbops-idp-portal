"""
Story 78.11 — Tests for ProfileActionPermissionRepository.

Tests: JSON readers, normalized readers, feature flag dispatch, sync_from_json, idempotence, edge cases.
Tables managed by conftest.py session-scoped fixture.
"""
import json

import pytest
from django.test import TestCase, override_settings

from profiles.action_permission_repository import (
    get_action_ids,
    get_action_ids_from_json,
    get_action_ids_from_normalized,
    get_environments,
    get_environments_from_json,
    get_environments_from_normalized,
    get_tag_patterns,
    get_tag_patterns_from_json,
    get_tag_patterns_from_normalized,
    sync_from_json,
)
from profiles.models import Profile, ProfileActionPermission
from profiles.models_action_permission_normalized import (
    ProfileActionAllowlist,
    ProfileActionEnv,
    ProfileActionTagPattern,
)


@pytest.mark.django_db
class JsonReadersTest(TestCase):
    """Test that JSON readers delegate correctly to model helpers."""

    def setUp(self):
        self.profile = Profile.objects.create(
            name='json-reader-test', ad_group='GRP-IDP-JR'
        )
        self.perm = ProfileActionPermission.objects.create(
            profile=self.profile,
            permission_type='LIST',
            action_ids_json=json.dumps([1, 2, 3]),
            tag_patterns_json=json.dumps(['oracle', 'postgres']),
            environments_json=json.dumps(['dev', 'staging']),
        )

    def test_get_action_ids_from_json(self):
        result = get_action_ids_from_json(self.perm)
        self.assertEqual(result, [1, 2, 3])

    def test_get_tag_patterns_from_json(self):
        result = get_tag_patterns_from_json(self.perm)
        self.assertEqual(result, ['oracle', 'postgres'])

    def test_get_environments_from_json(self):
        result = get_environments_from_json(self.perm)
        self.assertEqual(result, ['dev', 'staging'])


@pytest.mark.django_db
class NormalizedReadersTest(TestCase):
    """Test reading from normalized tables."""

    def setUp(self):
        self.profile = Profile.objects.create(
            name='norm-reader-test', ad_group='GRP-IDP-NR'
        )
        self.perm = ProfileActionPermission.objects.create(
            profile=self.profile, permission_type='LIST'
        )
        # Populate normalized tables directly
        ProfileActionAllowlist.objects.create(profile=self.perm, action_id=5)
        ProfileActionAllowlist.objects.create(profile=self.perm, action_id=3)
        ProfileActionAllowlist.objects.create(profile=self.perm, action_id=10)
        ProfileActionTagPattern.objects.create(profile=self.perm, tag_pattern='oracle')
        ProfileActionTagPattern.objects.create(profile=self.perm, tag_pattern='aws')
        ProfileActionEnv.objects.create(profile=self.perm, environment='prod')

    def test_get_action_ids_from_normalized_sorted(self):
        result = get_action_ids_from_normalized(self.profile.id)
        self.assertEqual(result, [3, 5, 10])

    def test_get_tag_patterns_from_normalized_sorted(self):
        result = get_tag_patterns_from_normalized(self.profile.id)
        self.assertEqual(result, ['aws', 'oracle'])

    def test_get_environments_from_normalized(self):
        result = get_environments_from_normalized(self.profile.id)
        self.assertEqual(result, ['prod'])

    def test_empty_normalized_tables(self):
        """Profile with no normalized entries returns empty lists."""
        profile2 = Profile.objects.create(
            name='empty-norm', ad_group='GRP-IDP-EN'
        )
        ProfileActionPermission.objects.create(
            profile=profile2, permission_type='ALL'
        )
        self.assertEqual(get_action_ids_from_normalized(profile2.id), [])
        self.assertEqual(get_tag_patterns_from_normalized(profile2.id), [])
        self.assertEqual(get_environments_from_normalized(profile2.id), [])


@pytest.mark.django_db
class FeatureFlagDispatchTest(TestCase):
    """Test that public API dispatches based on feature flag."""

    def setUp(self):
        self.profile = Profile.objects.create(
            name='dispatch-test', ad_group='GRP-IDP-DT'
        )
        self.perm = ProfileActionPermission.objects.create(
            profile=self.profile,
            permission_type='LIST',
            action_ids_json=json.dumps([1, 2]),
            tag_patterns_json=json.dumps(['json-pattern']),
            environments_json=json.dumps(['json-env']),
        )
        # Different data in normalized tables
        ProfileActionAllowlist.objects.create(profile=self.perm, action_id=99)
        ProfileActionTagPattern.objects.create(profile=self.perm, tag_pattern='norm-pattern')
        ProfileActionEnv.objects.create(profile=self.perm, environment='norm-env')

    def test_dispatch_json_when_flag_false(self):
        """Default (flag=False): reads from JSON."""
        self.assertEqual(get_action_ids(self.perm), [1, 2])
        self.assertEqual(get_tag_patterns(self.perm), ['json-pattern'])
        self.assertEqual(get_environments(self.perm), ['json-env'])

    @override_settings(PROFILE_ACTION_PERMISSIONS_NORMALIZED_ENABLED=True)
    def test_dispatch_normalized_when_flag_true(self):
        """Flag=True: reads from normalized tables."""
        self.assertEqual(get_action_ids(self.perm), [99])
        self.assertEqual(get_tag_patterns(self.perm), ['norm-pattern'])
        self.assertEqual(get_environments(self.perm), ['norm-env'])


@pytest.mark.django_db
class SyncFromJsonTest(TestCase):
    """Test sync_from_json() — the core dual-write mechanism."""

    def setUp(self):
        self.profile = Profile.objects.create(
            name='sync-test', ad_group='GRP-IDP-ST'
        )
        self.perm = ProfileActionPermission.objects.create(
            profile=self.profile,
            permission_type='LIST',
            action_ids_json=json.dumps([10, 20, 30]),
            tag_patterns_json=json.dumps(['oracle', 'provisioning']),
            environments_json=json.dumps(['dev', 'staging', 'prod']),
        )

    def test_sync_creates_normalized_entries(self):
        sync_from_json(self.profile.id)

        self.assertEqual(
            sorted(ProfileActionAllowlist.objects.filter(
                profile_id=self.profile.id
            ).values_list('action_id', flat=True)),
            [10, 20, 30],
        )
        self.assertEqual(
            sorted(ProfileActionTagPattern.objects.filter(
                profile_id=self.profile.id
            ).values_list('tag_pattern', flat=True)),
            ['oracle', 'provisioning'],
        )
        self.assertEqual(
            sorted(ProfileActionEnv.objects.filter(
                profile_id=self.profile.id
            ).values_list('environment', flat=True)),
            ['dev', 'prod', 'staging'],
        )

    def test_sync_idempotent_no_duplicates(self):
        """Double call to sync_from_json should not create duplicates."""
        sync_from_json(self.profile.id)
        sync_from_json(self.profile.id)

        self.assertEqual(
            ProfileActionAllowlist.objects.filter(profile_id=self.profile.id).count(), 3
        )
        self.assertEqual(
            ProfileActionTagPattern.objects.filter(profile_id=self.profile.id).count(), 2
        )
        self.assertEqual(
            ProfileActionEnv.objects.filter(profile_id=self.profile.id).count(), 3
        )

    def test_sync_updates_on_json_change(self):
        """Sync after JSON change should reflect new values."""
        sync_from_json(self.profile.id)
        self.assertEqual(
            ProfileActionAllowlist.objects.filter(profile_id=self.profile.id).count(), 3
        )

        # Update JSON
        self.perm.set_action_ids([100, 200])
        self.perm.save()

        sync_from_json(self.profile.id)
        self.assertEqual(
            sorted(ProfileActionAllowlist.objects.filter(
                profile_id=self.profile.id
            ).values_list('action_id', flat=True)),
            [100, 200],
        )

    def test_sync_null_json_fields(self):
        """NULL JSON fields → no normalized entries (not an error)."""
        perm_null = ProfileActionPermission.objects.create(
            profile=Profile.objects.create(name='null-json', ad_group='GRP-IDP-NJ'),
            permission_type='ALL',
            action_ids_json=None,
            tag_patterns_json=None,
            environments_json=None,
        )
        sync_from_json(perm_null.profile_id)
        self.assertEqual(
            ProfileActionAllowlist.objects.filter(profile_id=perm_null.profile_id).count(), 0
        )
        self.assertEqual(
            ProfileActionTagPattern.objects.filter(profile_id=perm_null.profile_id).count(), 0
        )
        self.assertEqual(
            ProfileActionEnv.objects.filter(profile_id=perm_null.profile_id).count(), 0
        )

    def test_sync_empty_json_arrays(self):
        """Empty JSON arrays '[]' → no normalized entries."""
        perm_empty = ProfileActionPermission.objects.create(
            profile=Profile.objects.create(name='empty-json', ad_group='GRP-IDP-EJ'),
            permission_type='ALL',
            action_ids_json=json.dumps([]),
            tag_patterns_json=json.dumps([]),
            environments_json=json.dumps([]),
        )
        sync_from_json(perm_empty.profile_id)
        self.assertEqual(
            ProfileActionAllowlist.objects.filter(profile_id=perm_empty.profile_id).count(), 0
        )

    def test_sync_json_with_duplicates_deduplicates(self):
        """JSON with duplicate values → deduplicated in normalized tables."""
        perm_dup = ProfileActionPermission.objects.create(
            profile=Profile.objects.create(name='dup-json', ad_group='GRP-IDP-DJ'),
            permission_type='LIST',
            action_ids_json=json.dumps([1, 2, 1, 3, 2]),
            tag_patterns_json=json.dumps(['oracle', 'oracle', 'aws']),
            environments_json=json.dumps(['dev', 'dev']),
        )
        sync_from_json(perm_dup.profile_id)
        self.assertEqual(
            ProfileActionAllowlist.objects.filter(profile_id=perm_dup.profile_id).count(), 3
        )
        self.assertEqual(
            ProfileActionTagPattern.objects.filter(profile_id=perm_dup.profile_id).count(), 2
        )
        self.assertEqual(
            ProfileActionEnv.objects.filter(profile_id=perm_dup.profile_id).count(), 1
        )

    def test_sync_nonexistent_profile_cleans_up(self):
        """sync_from_json for a profile with no ProfileActionPermission cleans up stale data."""
        profile_gone = Profile.objects.create(
            name='gone-profile', ad_group='GRP-IDP-GP'
        )
        # Insert some stale data directly
        ProfileActionAllowlist.objects.create(profile_id=profile_gone.id, action_id=999)

        sync_from_json(profile_gone.id)
        self.assertEqual(
            ProfileActionAllowlist.objects.filter(profile_id=profile_gone.id).count(), 0
        )
