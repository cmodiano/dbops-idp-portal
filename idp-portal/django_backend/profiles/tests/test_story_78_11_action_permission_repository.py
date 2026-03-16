"""
Story 78.15 — Tests for ProfileActionPermissionRepository (normalized only).

The legacy CLOB/JSON fields and dual-write mechanisms have been removed.
These tests verify that the repository reads exclusively from normalized tables.
"""

import pytest
from django.test import TestCase

from profiles.action_permission_repository import (
    get_action_ids,
    get_action_ids_from_normalized,
    get_environments,
    get_environments_from_normalized,
    get_tag_patterns,
    get_tag_patterns_from_normalized,
)
from profiles.models import Profile, ProfileActionPermission
from profiles.models_action_permission_normalized import (
    ProfileActionAllowlist,
    ProfileActionEnv,
    ProfileActionTagPattern,
)


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
class PublicApiAlwaysNormalizedTest(TestCase):
    """Test that public API (get_action_ids, etc.) reads from normalized tables."""

    def setUp(self):
        self.profile = Profile.objects.create(
            name='public-api-test', ad_group='GRP-IDP-PA'
        )
        self.perm = ProfileActionPermission.objects.create(
            profile=self.profile, permission_type='LIST'
        )
        ProfileActionAllowlist.objects.create(profile=self.perm, action_id=99)
        ProfileActionTagPattern.objects.create(profile=self.perm, tag_pattern='norm-pattern')
        ProfileActionEnv.objects.create(profile=self.perm, environment='norm-env')

    def test_get_action_ids_reads_normalized(self):
        self.assertEqual(get_action_ids(self.perm), [99])

    def test_get_tag_patterns_reads_normalized(self):
        self.assertEqual(get_tag_patterns(self.perm), ['norm-pattern'])

    def test_get_environments_reads_normalized(self):
        self.assertEqual(get_environments(self.perm), ['norm-env'])


@pytest.mark.django_db
class NormalizedWriteIntegrityTest(TestCase):
    """Test idempotence and integrity of normalized table writes via service."""

    def setUp(self):
        from profiles.services import ProfileService
        self.profile = Profile.objects.create(
            name='write-test', ad_group='GRP-IDP-WT'
        )
        ProfileService().set_action_permissions(
            self.profile.id,
            {
                'actions_type': 'list',
                'action_ids': [10, 20, 30],
                'tag_patterns': ['oracle', 'provisioning'],
                'environments': ['dev', 'staging', 'prod'],
            },
        )

    def test_action_ids_persisted(self):
        self.assertEqual(
            sorted(ProfileActionAllowlist.objects.filter(
                profile_id=self.profile.id
            ).values_list('action_id', flat=True)),
            [10, 20, 30],
        )

    def test_tag_patterns_persisted(self):
        self.assertEqual(
            sorted(ProfileActionTagPattern.objects.filter(
                profile_id=self.profile.id
            ).values_list('tag_pattern', flat=True)),
            ['oracle', 'provisioning'],
        )

    def test_environments_persisted(self):
        self.assertEqual(
            sorted(ProfileActionEnv.objects.filter(
                profile_id=self.profile.id
            ).values_list('environment', flat=True)),
            ['dev', 'prod', 'staging'],
        )

    def test_set_again_is_idempotent(self):
        """Re-setting same permissions does not create duplicates."""
        from profiles.services import ProfileService
        ProfileService().set_action_permissions(
            self.profile.id,
            {
                'actions_type': 'list',
                'action_ids': [10, 20, 30],
                'tag_patterns': ['oracle', 'provisioning'],
                'environments': ['dev', 'staging', 'prod'],
            },
        )
        self.assertEqual(
            ProfileActionAllowlist.objects.filter(profile_id=self.profile.id).count(), 3
        )
        self.assertEqual(
            ProfileActionTagPattern.objects.filter(profile_id=self.profile.id).count(), 2
        )
        self.assertEqual(
            ProfileActionEnv.objects.filter(profile_id=self.profile.id).count(), 3
        )
