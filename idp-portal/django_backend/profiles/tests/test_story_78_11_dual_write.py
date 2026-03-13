"""
Story 78.11 — Tests for dual-write via set_action_permissions().

Tests: with feature flag True, JSON + normalized tables are both written.
Tables managed by conftest.py session-scoped fixture.
"""
import json

import pytest
from django.test import TestCase, override_settings

from profiles.models import Profile, ProfileActionPermission
from profiles.models_action_permission_normalized import (
    ProfileActionAllowlist,
    ProfileActionEnv,
    ProfileActionTagPattern,
)
from profiles.services import ProfileService


@pytest.mark.django_db
class DualWriteTest(TestCase):
    def setUp(self):
        self.profile = Profile.objects.create(
            name='dual-write-test', ad_group='GRP-IDP-DW'
        )
        self.service = ProfileService()

    @override_settings(PROFILE_ACTION_PERMISSIONS_NORMALIZED_ENABLED=True)
    def test_set_action_permissions_writes_json_and_normalized(self):
        """With flag True, set_action_permissions writes both JSON and normalized tables."""
        self.service.set_action_permissions(
            self.profile.id,
            {
                'actions_type': 'list',
                'action_ids': [10, 20, 30],
                'tag_patterns': [],
                'environments': ['dev', 'prod'],
            },
        )

        # Verify JSON was written
        perm = ProfileActionPermission.objects.get(profile_id=self.profile.id)
        self.assertEqual(json.loads(perm.action_ids_json), [10, 20, 30])
        self.assertEqual(json.loads(perm.environments_json), ['dev', 'prod'])

        # Verify normalized tables were written
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

    @override_settings(PROFILE_ACTION_PERMISSIONS_NORMALIZED_ENABLED=True)
    def test_update_permissions_syncs_normalized(self):
        """Updating permissions re-syncs normalized tables."""
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

        # Update
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

    def test_set_action_permissions_no_normalized_when_flag_false(self):
        """With flag False (default), normalized tables are NOT written."""
        self.service.set_action_permissions(
            self.profile.id,
            {
                'actions_type': 'list',
                'action_ids': [1, 2, 3],
                'environments': ['dev'],
            },
        )

        # JSON was written
        perm = ProfileActionPermission.objects.get(profile_id=self.profile.id)
        self.assertEqual(json.loads(perm.action_ids_json), [1, 2, 3])

        # Normalized tables NOT written
        self.assertEqual(
            ProfileActionAllowlist.objects.filter(profile_id=self.profile.id).count(), 0
        )

    @override_settings(PROFILE_ACTION_PERMISSIONS_NORMALIZED_ENABLED=True)
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
