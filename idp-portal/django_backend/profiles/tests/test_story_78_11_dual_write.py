"""
Story 78.15 — Tests for direct normalized write via set_action_permissions().

Story 78.11 dual-write has been removed: JSON CLOB columns no longer exist.
These tests verify that set_action_permissions() writes exclusively to normalized tables.
"""
import pytest
from django.test import TestCase

from profiles.models import Profile
from profiles.models_action_permission_normalized import (
    ProfileActionAllowlist,
    ProfileActionEnv,
    ProfileActionTagPattern,
)
from profiles.services import ProfileService


@pytest.mark.django_db
class DirectNormalizedWriteTest(TestCase):
    def setUp(self):
        self.profile = Profile.objects.create(
            name='normalized-write-test', ad_group='GRP-IDP-DW'
        )
        self.service = ProfileService()

    def test_set_action_permissions_writes_to_normalized_tables(self):
        """set_action_permissions writes action IDs and environments to normalized tables."""
        self.service.set_action_permissions(
            self.profile.id,
            {
                'actions_type': 'list',
                'action_ids': [10, 20, 30],
                'tag_patterns': [],
                'environments': ['dev', 'prod'],
            },
        )

        self.assertEqual(
            sorted(ProfileActionAllowlist.objects.filter(
                profile_id=self.profile.id
            ).values_list('action_id', flat=True)),
            [10, 20, 30],
        )
        self.assertEqual(
            sorted(ProfileActionEnv.objects.filter(
                profile_id=self.profile.id
            ).values_list('environment', flat=True)),
            ['dev', 'prod'],
        )

    def test_update_permissions_replaces_normalized_data(self):
        """Updating permissions deletes and replaces normalized table rows."""
        self.service.set_action_permissions(
            self.profile.id,
            {
                'actions_type': 'list',
                'action_ids': [1, 2],
                'environments': ['dev'],
            },
        )
        self.assertEqual(
            ProfileActionAllowlist.objects.filter(profile_id=self.profile.id).count(), 2
        )

        self.service.set_action_permissions(
            self.profile.id,
            {
                'actions_type': 'list',
                'action_ids': [100],
                'environments': ['prod', 'staging'],
            },
        )
        self.assertEqual(
            list(ProfileActionAllowlist.objects.filter(
                profile_id=self.profile.id
            ).values_list('action_id', flat=True)),
            [100],
        )
        self.assertEqual(
            sorted(ProfileActionEnv.objects.filter(
                profile_id=self.profile.id
            ).values_list('environment', flat=True)),
            ['prod', 'staging'],
        )

    def test_pattern_type_with_tag_patterns(self):
        """Pattern type writes tag patterns to normalized tables."""
        self.service.set_action_permissions(
            self.profile.id,
            {
                'actions_type': 'pattern',
                'tag_patterns': ['oracle', 'provisioning'],
                'environments': ['dev'],
            },
        )

        self.assertEqual(
            sorted(ProfileActionTagPattern.objects.filter(
                profile_id=self.profile.id
            ).values_list('tag_pattern', flat=True)),
            ['oracle', 'provisioning'],
        )

    def test_empty_action_ids_clears_allowlist(self):
        """Setting empty action_ids clears the allowlist."""
        self.service.set_action_permissions(
            self.profile.id,
            {'actions_type': 'list', 'action_ids': [1, 2, 3]},
        )
        self.assertEqual(
            ProfileActionAllowlist.objects.filter(profile_id=self.profile.id).count(), 3
        )

        self.service.set_action_permissions(
            self.profile.id,
            {'actions_type': 'all', 'action_ids': []},
        )
        self.assertEqual(
            ProfileActionAllowlist.objects.filter(profile_id=self.profile.id).count(), 0
        )
