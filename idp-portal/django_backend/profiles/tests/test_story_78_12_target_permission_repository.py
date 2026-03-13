"""
Story 78.12 — Tests for ProfileTargetPermissionRepository.

Tests: JSON readers, normalized readers, feature flag dispatch, sync_from_json,
       idempotence, edge cases, filter_by_attribute dict reconstruction.
Tables managed by conftest.py session-scoped fixture.
"""
import json

import pytest
from django.test import TestCase, override_settings

from profiles.target_permission_repository import (
    get_target_names,
    get_target_names_from_json,
    get_target_names_from_normalized,
    get_target_patterns,
    get_target_patterns_from_json,
    get_target_patterns_from_normalized,
    get_filter_by_attribute,
    get_filter_by_attribute_from_json,
    get_filter_by_attribute_from_normalized,
    get_exclusion_patterns,
    get_exclusion_patterns_from_json,
    get_exclusion_patterns_from_normalized,
    sync_from_json,
)
from profiles.models import Profile, ProfileTargetPermission
from profiles.models_target_permission_normalized import (
    ProfileTargetAllowlist,
    ProfileTargetAttributeFilter,
    ProfileTargetExclusion,
    ProfileTargetPattern,
)


@pytest.mark.django_db
class JsonReadersTest(TestCase):
    """Test that JSON readers delegate correctly to model helpers."""

    def setUp(self):
        self.profile = Profile.objects.create(
            name='t-json-reader', ad_group='GRP-IDP-TJR'
        )
        self.perm = ProfileTargetPermission.objects.create(
            profile=self.profile,
            permission_type='LIST',
            target_names_json=json.dumps(['server-b', 'server-a', 'server-c']),
            target_patterns_json=json.dumps(['staging-*', 'prod-*']),
            filter_by_attribute_json=json.dumps({'engine_type': ['oracle', 'mysql'], 'zone': ['prod']}),
            exclusion_patterns_json=json.dumps(['DR-*', 'BACKUP-*']),
        )

    def test_get_target_names_from_json_sorted(self):
        result = get_target_names_from_json(self.perm)
        self.assertEqual(result, ['server-a', 'server-b', 'server-c'])

    def test_get_target_patterns_from_json_sorted(self):
        result = get_target_patterns_from_json(self.perm)
        self.assertEqual(result, ['prod-*', 'staging-*'])

    def test_get_filter_by_attribute_from_json_sorted(self):
        result = get_filter_by_attribute_from_json(self.perm)
        self.assertEqual(result, {'engine_type': ['mysql', 'oracle'], 'zone': ['prod']})

    def test_get_exclusion_patterns_from_json_sorted(self):
        result = get_exclusion_patterns_from_json(self.perm)
        self.assertEqual(result, ['BACKUP-*', 'DR-*'])


@pytest.mark.django_db
class NormalizedReadersTest(TestCase):
    """Test reading from normalized tables."""

    def setUp(self):
        self.profile = Profile.objects.create(
            name='t-norm-reader', ad_group='GRP-IDP-TNR'
        )
        self.perm = ProfileTargetPermission.objects.create(
            profile=self.profile, permission_type='LIST'
        )
        # Populate normalized tables directly
        ProfileTargetAllowlist.objects.create(profile=self.perm, target_name='z-server')
        ProfileTargetAllowlist.objects.create(profile=self.perm, target_name='a-server')
        ProfileTargetPattern.objects.create(profile=self.perm, pattern='staging-*')
        ProfileTargetAttributeFilter.objects.create(
            profile=self.perm, attribute_key='zone', attribute_value='prod'
        )
        ProfileTargetAttributeFilter.objects.create(
            profile=self.perm, attribute_key='zone', attribute_value='dev'
        )
        ProfileTargetAttributeFilter.objects.create(
            profile=self.perm, attribute_key='engine_type', attribute_value='oracle'
        )
        ProfileTargetExclusion.objects.create(profile=self.perm, exclusion_pattern='DR-*')

    def test_get_target_names_from_normalized_sorted(self):
        result = get_target_names_from_normalized(self.profile.id)
        self.assertEqual(result, ['a-server', 'z-server'])

    def test_get_target_patterns_from_normalized_sorted(self):
        result = get_target_patterns_from_normalized(self.profile.id)
        self.assertEqual(result, ['staging-*'])

    def test_get_filter_by_attribute_from_normalized_reconstructs_dict(self):
        result = get_filter_by_attribute_from_normalized(self.profile.id)
        self.assertEqual(result, {'engine_type': ['oracle'], 'zone': ['dev', 'prod']})

    def test_get_exclusion_patterns_from_normalized(self):
        result = get_exclusion_patterns_from_normalized(self.profile.id)
        self.assertEqual(result, ['DR-*'])

    def test_empty_normalized_tables(self):
        """Profile with no normalized entries returns empty lists / None."""
        profile2 = Profile.objects.create(name='t-empty-norm', ad_group='GRP-IDP-TEN')
        ProfileTargetPermission.objects.create(profile=profile2, permission_type='ALL')
        self.assertEqual(get_target_names_from_normalized(profile2.id), [])
        self.assertEqual(get_target_patterns_from_normalized(profile2.id), [])
        self.assertIsNone(get_filter_by_attribute_from_normalized(profile2.id))
        self.assertEqual(get_exclusion_patterns_from_normalized(profile2.id), [])


@pytest.mark.django_db
class FeatureFlagDispatchTest(TestCase):
    """Test that public API dispatches based on feature flag."""

    def setUp(self):
        self.profile = Profile.objects.create(
            name='t-dispatch', ad_group='GRP-IDP-TDI'
        )
        self.perm = ProfileTargetPermission.objects.create(
            profile=self.profile,
            permission_type='LIST',
            target_names_json=json.dumps(['json-server']),
            target_patterns_json=json.dumps(['json-*']),
            filter_by_attribute_json=json.dumps({'key': ['json-val']}),
            exclusion_patterns_json=json.dumps(['json-excl-*']),
        )
        # Different data in normalized tables
        ProfileTargetAllowlist.objects.create(profile=self.perm, target_name='norm-server')
        ProfileTargetPattern.objects.create(profile=self.perm, pattern='norm-*')
        ProfileTargetAttributeFilter.objects.create(
            profile=self.perm, attribute_key='key', attribute_value='norm-val'
        )
        ProfileTargetExclusion.objects.create(profile=self.perm, exclusion_pattern='norm-excl-*')

    def test_dispatch_json_when_flag_false(self):
        """Default (flag=False): reads from JSON."""
        self.assertEqual(get_target_names(self.perm), ['json-server'])
        self.assertEqual(get_target_patterns(self.perm), ['json-*'])
        self.assertEqual(get_filter_by_attribute(self.perm), {'key': ['json-val']})
        self.assertEqual(get_exclusion_patterns(self.perm), ['json-excl-*'])

    @override_settings(PROFILE_TARGET_PERMISSIONS_NORMALIZED_ENABLED=True)
    def test_dispatch_normalized_when_flag_true(self):
        """Flag=True: reads from normalized tables."""
        self.assertEqual(get_target_names(self.perm), ['norm-server'])
        self.assertEqual(get_target_patterns(self.perm), ['norm-*'])
        self.assertEqual(get_filter_by_attribute(self.perm), {'key': ['norm-val']})
        self.assertEqual(get_exclusion_patterns(self.perm), ['norm-excl-*'])


@pytest.mark.django_db
class SyncFromJsonTest(TestCase):
    """Test sync_from_json() — the core dual-write mechanism."""

    def setUp(self):
        self.profile = Profile.objects.create(
            name='t-sync', ad_group='GRP-IDP-TSY'
        )
        self.perm = ProfileTargetPermission.objects.create(
            profile=self.profile,
            permission_type='LIST',
            target_names_json=json.dumps(['server-1', 'server-2']),
            target_patterns_json=json.dumps(['prod-*', 'staging-*']),
            filter_by_attribute_json=json.dumps({'engine_type': ['oracle', 'mysql'], 'zone': ['prod']}),
            exclusion_patterns_json=json.dumps(['DR-*', 'BACKUP-*']),
        )

    def test_sync_creates_normalized_entries(self):
        sync_from_json(self.profile.id)

        self.assertEqual(
            sorted(ProfileTargetAllowlist.objects.filter(
                profile_id=self.profile.id
            ).values_list('target_name', flat=True)),
            ['server-1', 'server-2'],
        )
        self.assertEqual(
            sorted(ProfileTargetPattern.objects.filter(
                profile_id=self.profile.id
            ).values_list('pattern', flat=True)),
            ['prod-*', 'staging-*'],
        )
        af_rows = ProfileTargetAttributeFilter.objects.filter(
            profile_id=self.profile.id
        ).order_by('attribute_key', 'attribute_value')
        self.assertEqual(af_rows.count(), 3)
        self.assertEqual(
            list(af_rows.values_list('attribute_key', 'attribute_value')),
            [('engine_type', 'mysql'), ('engine_type', 'oracle'), ('zone', 'prod')],
        )
        self.assertEqual(
            sorted(ProfileTargetExclusion.objects.filter(
                profile_id=self.profile.id
            ).values_list('exclusion_pattern', flat=True)),
            ['BACKUP-*', 'DR-*'],
        )

    def test_sync_idempotent_no_duplicates(self):
        """Double call to sync_from_json should not create duplicates."""
        sync_from_json(self.profile.id)
        sync_from_json(self.profile.id)

        self.assertEqual(
            ProfileTargetAllowlist.objects.filter(profile_id=self.profile.id).count(), 2
        )
        self.assertEqual(
            ProfileTargetPattern.objects.filter(profile_id=self.profile.id).count(), 2
        )
        self.assertEqual(
            ProfileTargetAttributeFilter.objects.filter(profile_id=self.profile.id).count(), 3
        )
        self.assertEqual(
            ProfileTargetExclusion.objects.filter(profile_id=self.profile.id).count(), 2
        )

    def test_sync_updates_on_json_change(self):
        """Sync after JSON change should reflect new values."""
        sync_from_json(self.profile.id)
        self.assertEqual(
            ProfileTargetAllowlist.objects.filter(profile_id=self.profile.id).count(), 2
        )

        # Update JSON
        self.perm.set_target_names(['new-server'])
        self.perm.save()

        sync_from_json(self.profile.id)
        self.assertEqual(
            list(ProfileTargetAllowlist.objects.filter(
                profile_id=self.profile.id
            ).values_list('target_name', flat=True)),
            ['new-server'],
        )

    def test_sync_null_json_fields(self):
        """NULL JSON fields → no normalized entries (not an error)."""
        perm_null = ProfileTargetPermission.objects.create(
            profile=Profile.objects.create(name='t-null-json', ad_group='GRP-IDP-TNJ'),
            permission_type='ALL',
            target_names_json=None,
            target_patterns_json=None,
            filter_by_attribute_json=None,
            exclusion_patterns_json=None,
        )
        sync_from_json(perm_null.profile_id)
        self.assertEqual(
            ProfileTargetAllowlist.objects.filter(profile_id=perm_null.profile_id).count(), 0
        )
        self.assertEqual(
            ProfileTargetPattern.objects.filter(profile_id=perm_null.profile_id).count(), 0
        )
        self.assertEqual(
            ProfileTargetAttributeFilter.objects.filter(profile_id=perm_null.profile_id).count(), 0
        )
        self.assertEqual(
            ProfileTargetExclusion.objects.filter(profile_id=perm_null.profile_id).count(), 0
        )

    def test_sync_empty_json_arrays(self):
        """Empty JSON arrays '[]' / empty dict '{}' → no normalized entries."""
        perm_empty = ProfileTargetPermission.objects.create(
            profile=Profile.objects.create(name='t-empty-json', ad_group='GRP-IDP-TEJ'),
            permission_type='ALL',
            target_names_json=json.dumps([]),
            target_patterns_json=json.dumps([]),
            filter_by_attribute_json=json.dumps({}),
            exclusion_patterns_json=json.dumps([]),
        )
        sync_from_json(perm_empty.profile_id)
        self.assertEqual(
            ProfileTargetAllowlist.objects.filter(profile_id=perm_empty.profile_id).count(), 0
        )
        self.assertEqual(
            ProfileTargetAttributeFilter.objects.filter(profile_id=perm_empty.profile_id).count(), 0
        )

    def test_sync_json_with_duplicates_deduplicates(self):
        """JSON with duplicate values → deduplicated in normalized tables."""
        perm_dup = ProfileTargetPermission.objects.create(
            profile=Profile.objects.create(name='t-dup-json', ad_group='GRP-IDP-TDJ'),
            permission_type='LIST',
            target_names_json=json.dumps(['srv', 'srv', 'srv2']),
            target_patterns_json=json.dumps(['prod-*', 'prod-*']),
            filter_by_attribute_json=json.dumps({'zone': ['prod', 'prod', 'dev']}),
            exclusion_patterns_json=json.dumps(['DR-*', 'DR-*']),
        )
        sync_from_json(perm_dup.profile_id)
        self.assertEqual(
            ProfileTargetAllowlist.objects.filter(profile_id=perm_dup.profile_id).count(), 2
        )
        self.assertEqual(
            ProfileTargetPattern.objects.filter(profile_id=perm_dup.profile_id).count(), 1
        )
        self.assertEqual(
            ProfileTargetAttributeFilter.objects.filter(profile_id=perm_dup.profile_id).count(), 2
        )
        self.assertEqual(
            ProfileTargetExclusion.objects.filter(profile_id=perm_dup.profile_id).count(), 1
        )

    def test_sync_nonexistent_profile_cleans_up(self):
        """sync_from_json for a profile with no ProfileTargetPermission cleans up stale data."""
        profile_gone = Profile.objects.create(
            name='t-gone-profile', ad_group='GRP-IDP-TGP'
        )
        # Insert some stale data directly
        ProfileTargetAllowlist.objects.create(profile_id=profile_gone.id, target_name='stale')

        sync_from_json(profile_gone.id)
        self.assertEqual(
            ProfileTargetAllowlist.objects.filter(profile_id=profile_gone.id).count(), 0
        )

    def test_sync_filter_by_attribute_multiple_keys(self):
        """filter_by_attribute with multiple keys and values → correct rows."""
        perm_multi = ProfileTargetPermission.objects.create(
            profile=Profile.objects.create(name='t-multi-fa', ad_group='GRP-IDP-TMF'),
            permission_type='ALL',
            filter_by_attribute_json=json.dumps({
                'engine_type': ['oracle', 'mysql', 'postgres'],
                'zone': ['prod', 'staging'],
                'region': ['eu-west-1'],
            }),
        )
        sync_from_json(perm_multi.profile_id)
        self.assertEqual(
            ProfileTargetAttributeFilter.objects.filter(
                profile_id=perm_multi.profile_id
            ).count(),
            6,  # 3 + 2 + 1
        )
