"""
Story 78.15 — Tests for normalized target permission integrity.

The legacy parity check commands (JSON vs normalized) have been removed.
These tests verify that the normalized target permission tables remain
internally consistent after service operations.
"""

import pytest
from django.test import TestCase

from profiles.target_permission_repository import (
    get_exclusion_patterns_from_normalized,
    get_filter_by_attribute_from_normalized,
    get_target_names_from_normalized,
    get_target_patterns_from_normalized,
)
from profiles.models import Profile
from profiles.models_target_permission_normalized import (
    ProfileTargetAllowlist,
)
from profiles.services import ProfileService


@pytest.mark.django_db
class NormalizedTargetPermissionIntegrityTest(TestCase):
    """Test that target permission normalized tables remain consistent after service ops."""

    def test_set_permissions_replaces_previous_data(self):
        """set_target_permissions overwrites, not appends, existing data."""
        profile = Profile.objects.create(name='t-replace-test', ad_group='GRP-IDP-TRT')
        svc = ProfileService()

        svc.set_target_permissions(
            profile.id,
            {'targets_type': 'list', 'target_names': ['server-1', 'server-2']},
        )
        svc.set_target_permissions(
            profile.id,
            {'targets_type': 'list', 'target_names': ['new-server']},
        )

        names = get_target_names_from_normalized(profile.id)
        self.assertEqual(names, ['new-server'])

    def test_all_type_no_target_names(self):
        """ALL permission type → no target names in normalized table."""
        profile = Profile.objects.create(name='t-all-type', ad_group='GRP-IDP-TAT')
        ProfileService().set_target_permissions(
            profile.id,
            {'targets_type': 'all'},
        )
        self.assertEqual(get_target_names_from_normalized(profile.id), [])
        self.assertEqual(get_target_patterns_from_normalized(profile.id), [])

    def test_pattern_type(self):
        """PATTERN permission type → target_patterns in normalized table."""
        profile = Profile.objects.create(name='t-pattern-type', ad_group='GRP-IDP-TPT')
        ProfileService().set_target_permissions(
            profile.id,
            {'targets_type': 'pattern', 'target_patterns': ['prod-*', 'staging-*']},
        )
        self.assertEqual(
            sorted(get_target_patterns_from_normalized(profile.id)),
            ['prod-*', 'staging-*'],
        )

    def test_filter_by_attribute_persisted(self):
        """filter_by_attribute is correctly stored in normalized table."""
        profile = Profile.objects.create(name='t-filter-test', ad_group='GRP-IDP-TFT')
        ProfileService().set_target_permissions(
            profile.id,
            {
                'targets_type': 'all',
                'filter_by_attribute': {'engine_type': ['oracle', 'mysql'], 'zone': ['prod']},
            },
        )
        result = get_filter_by_attribute_from_normalized(profile.id)
        self.assertEqual(result['engine_type'], ['mysql', 'oracle'])
        self.assertEqual(result['zone'], ['prod'])

    def test_exclusion_patterns_persisted(self):
        """exclusion_patterns are correctly stored in normalized table."""
        profile = Profile.objects.create(name='t-excl-test', ad_group='GRP-IDP-TET')
        ProfileService().set_target_permissions(
            profile.id,
            {'targets_type': 'all', 'exclusion_patterns': ['DR-*', 'BACKUP-*']},
        )
        self.assertEqual(
            sorted(get_exclusion_patterns_from_normalized(profile.id)),
            ['BACKUP-*', 'DR-*'],
        )

    def test_no_duplicate_entries(self):
        """Repeated set_target_permissions never creates duplicate normalized rows."""
        profile = Profile.objects.create(name='t-dup-test', ad_group='GRP-IDP-TDT')
        svc = ProfileService()
        for _ in range(3):
            svc.set_target_permissions(
                profile.id,
                {'targets_type': 'list', 'target_names': ['server-1', 'server-2']},
            )
        self.assertEqual(
            ProfileTargetAllowlist.objects.filter(profile_id=profile.id).count(), 2
        )

    def test_empty_permission_clears_normalized(self):
        """Setting empty permissions removes all normalized entries."""
        profile = Profile.objects.create(name='t-clear-test', ad_group='GRP-IDP-TCT')
        svc = ProfileService()
        svc.set_target_permissions(
            profile.id,
            {'targets_type': 'list', 'target_names': ['srv-1', 'srv-2']},
        )
        svc.set_target_permissions(
            profile.id,
            {'targets_type': 'all', 'target_names': [], 'target_patterns': []},
        )
        self.assertEqual(get_target_names_from_normalized(profile.id), [])
        self.assertEqual(get_target_patterns_from_normalized(profile.id), [])
