"""
Story 78.15 — Tests for ProfileTargetPermissionRepository (normalized only).

The legacy CLOB/JSON fields and dual-write mechanisms have been removed.
These tests verify that the repository reads exclusively from normalized tables.
"""

import pytest
from django.test import TestCase

from profiles.target_permission_repository import (
    get_target_names,
    get_target_names_from_normalized,
    get_target_patterns,
    get_target_patterns_from_normalized,
    get_filter_by_attribute,
    get_filter_by_attribute_from_normalized,
    get_exclusion_patterns,
    get_exclusion_patterns_from_normalized,
)
from profiles.models import Profile, ProfileTargetPermission
from profiles.models_target_permission_normalized import (
    ProfileTargetAllowlist,
    ProfileTargetAttributeFilter,
    ProfileTargetExclusion,
    ProfileTargetPattern,
)


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
class PublicApiAlwaysNormalizedTest(TestCase):
    """Test that public API reads from normalized tables (no flag dispatch)."""

    def setUp(self):
        self.profile = Profile.objects.create(
            name='t-public-api', ad_group='GRP-IDP-TPA'
        )
        self.perm = ProfileTargetPermission.objects.create(
            profile=self.profile, permission_type='LIST'
        )
        ProfileTargetAllowlist.objects.create(profile=self.perm, target_name='norm-server')
        ProfileTargetPattern.objects.create(profile=self.perm, pattern='norm-*')
        ProfileTargetAttributeFilter.objects.create(
            profile=self.perm, attribute_key='key', attribute_value='norm-val'
        )
        ProfileTargetExclusion.objects.create(profile=self.perm, exclusion_pattern='norm-excl-*')

    def test_get_target_names_reads_normalized(self):
        self.assertEqual(get_target_names(self.perm), ['norm-server'])

    def test_get_target_patterns_reads_normalized(self):
        self.assertEqual(get_target_patterns(self.perm), ['norm-*'])

    def test_get_filter_by_attribute_reads_normalized(self):
        self.assertEqual(get_filter_by_attribute(self.perm), {'key': ['norm-val']})

    def test_get_exclusion_patterns_reads_normalized(self):
        self.assertEqual(get_exclusion_patterns(self.perm), ['norm-excl-*'])


@pytest.mark.django_db
class NormalizedWriteIntegrityTest(TestCase):
    """Test idempotence and integrity of normalized table writes via service."""

    def setUp(self):
        from profiles.services import ProfileService
        self.profile = Profile.objects.create(
            name='t-write-test', ad_group='GRP-IDP-TWT'
        )
        ProfileService().set_target_permissions(
            self.profile.id,
            {
                'targets_type': 'list',
                'target_names': ['server-1', 'server-2'],
                'target_patterns': ['prod-*', 'staging-*'],
                'filter_by_attribute': {'engine_type': ['oracle', 'mysql'], 'zone': ['prod']},
                'exclusion_patterns': ['DR-*', 'BACKUP-*'],
            },
        )

    def test_target_names_persisted(self):
        self.assertEqual(
            sorted(ProfileTargetAllowlist.objects.filter(
                profile_id=self.profile.id
            ).values_list('target_name', flat=True)),
            ['server-1', 'server-2'],
        )

    def test_target_patterns_persisted(self):
        self.assertEqual(
            sorted(ProfileTargetPattern.objects.filter(
                profile_id=self.profile.id
            ).values_list('pattern', flat=True)),
            ['prod-*', 'staging-*'],
        )

    def test_filter_by_attribute_persisted(self):
        af_rows = ProfileTargetAttributeFilter.objects.filter(
            profile_id=self.profile.id
        ).order_by('attribute_key', 'attribute_value')
        self.assertEqual(af_rows.count(), 3)
        self.assertEqual(
            list(af_rows.values_list('attribute_key', 'attribute_value')),
            [('engine_type', 'mysql'), ('engine_type', 'oracle'), ('zone', 'prod')],
        )

    def test_exclusion_patterns_persisted(self):
        self.assertEqual(
            sorted(ProfileTargetExclusion.objects.filter(
                profile_id=self.profile.id
            ).values_list('exclusion_pattern', flat=True)),
            ['BACKUP-*', 'DR-*'],
        )

    def test_set_again_is_idempotent(self):
        """Re-setting same permissions does not create duplicates."""
        from profiles.services import ProfileService
        ProfileService().set_target_permissions(
            self.profile.id,
            {
                'targets_type': 'list',
                'target_names': ['server-1', 'server-2'],
                'target_patterns': ['prod-*', 'staging-*'],
                'filter_by_attribute': {'engine_type': ['oracle', 'mysql'], 'zone': ['prod']},
                'exclusion_patterns': ['DR-*', 'BACKUP-*'],
            },
        )
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
