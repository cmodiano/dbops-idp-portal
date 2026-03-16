"""
Story 78.15 — Tests for normalized action permission integrity.

The legacy parity check commands (JSON vs normalized) have been removed.
These tests verify that the normalized action permission tables remain
internally consistent after service operations.
"""

import pytest
from django.test import TestCase

from profiles.action_permission_repository import (
    get_action_ids_from_normalized,
    get_environments_from_normalized,
    get_tag_patterns_from_normalized,
)
from profiles.models import Profile
from profiles.models_action_permission_normalized import (
    ProfileActionAllowlist,
)
from profiles.services import ProfileService


@pytest.mark.django_db
class NormalizedActionPermissionIntegrityTest(TestCase):
    """Test that action permission normalized tables remain consistent after service ops."""

    def test_set_permissions_replaces_previous_data(self):
        """set_action_permissions overwrites, not appends, existing data."""
        profile = Profile.objects.create(name='replace-test', ad_group='GRP-IDP-RT')
        svc = ProfileService()

        svc.set_action_permissions(
            profile.id,
            {'actions_type': 'list', 'action_ids': [1, 2, 3], 'environments': ['dev']},
        )
        svc.set_action_permissions(
            profile.id,
            {'actions_type': 'list', 'action_ids': [10, 20], 'environments': ['prod']},
        )

        action_ids = get_action_ids_from_normalized(profile.id)
        self.assertEqual(sorted(action_ids), [10, 20])

        envs = get_environments_from_normalized(profile.id)
        self.assertEqual(envs, ['prod'])

    def test_all_type_no_action_ids(self):
        """ALL permission type → no action_ids in normalized table."""
        profile = Profile.objects.create(name='all-type-test', ad_group='GRP-IDP-AT')
        ProfileService().set_action_permissions(
            profile.id,
            {'actions_type': 'all', 'environments': ['dev', 'staging', 'prod']},
        )
        self.assertEqual(get_action_ids_from_normalized(profile.id), [])
        self.assertEqual(
            sorted(get_environments_from_normalized(profile.id)),
            ['dev', 'prod', 'staging'],
        )

    def test_pattern_type(self):
        """PATTERN permission type → tag_patterns in normalized table."""
        profile = Profile.objects.create(name='pattern-type-test', ad_group='GRP-IDP-PTT')
        ProfileService().set_action_permissions(
            profile.id,
            {'actions_type': 'pattern', 'tag_patterns': ['oracle', 'provisioning'], 'environments': ['prod']},
        )
        self.assertEqual(
            sorted(get_tag_patterns_from_normalized(profile.id)),
            ['oracle', 'provisioning'],
        )
        self.assertEqual(get_environments_from_normalized(profile.id), ['prod'])

    def test_no_duplicate_entries(self):
        """Repeated set_action_permissions never creates duplicate normalized rows."""
        profile = Profile.objects.create(name='dup-test', ad_group='GRP-IDP-DT')
        svc = ProfileService()
        for _ in range(3):
            svc.set_action_permissions(
                profile.id,
                {'actions_type': 'list', 'action_ids': [1, 2, 3]},
            )
        self.assertEqual(
            ProfileActionAllowlist.objects.filter(profile_id=profile.id).count(), 3
        )

    def test_empty_permission_clears_normalized(self):
        """Setting empty permissions removes all normalized entries."""
        profile = Profile.objects.create(name='clear-test', ad_group='GRP-IDP-CT')
        svc = ProfileService()
        svc.set_action_permissions(
            profile.id,
            {'actions_type': 'list', 'action_ids': [1, 2], 'environments': ['dev']},
        )
        svc.set_action_permissions(
            profile.id,
            {'actions_type': 'all', 'action_ids': [], 'environments': []},
        )
        self.assertEqual(get_action_ids_from_normalized(profile.id), [])
        self.assertEqual(get_environments_from_normalized(profile.id), [])
