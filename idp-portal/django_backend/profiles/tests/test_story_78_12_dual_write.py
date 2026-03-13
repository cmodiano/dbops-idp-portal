"""
Story 78.12 — Tests for dual-write via set_target_permissions().

Tests: with feature flag True, JSON + normalized tables are both written.
Tables managed by conftest.py session-scoped fixture.
"""
import json

import pytest
from django.test import TestCase, override_settings

from profiles.models import Profile, ProfileTargetPermission
from profiles.models_target_permission_normalized import (
    ProfileTargetAllowlist,
    ProfileTargetAttributeFilter,
    ProfileTargetExclusion,
    ProfileTargetPattern,
)
from profiles.services import ProfileService


@pytest.mark.django_db
class DualWriteTest(TestCase):
    def setUp(self):
        self.profile = Profile.objects.create(
            name='t-dual-write', ad_group='GRP-IDP-TDW'
        )
        self.service = ProfileService()

    @override_settings(PROFILE_TARGET_PERMISSIONS_NORMALIZED_ENABLED=True)
    def test_set_target_permissions_writes_json_and_normalized(self):
        """With flag True, set_target_permissions writes both JSON and normalized tables."""
        self.service.set_target_permissions(
            self.profile.id,
            {
                'targets_type': 'list',
                'target_names': ['server-1', 'server-2'],
                'target_patterns': [],
                'filter_by_attribute': {'engine_type': ['oracle']},
                'exclusion_patterns': ['DR-*'],
            },
        )

        # Verify JSON was written
        perm = ProfileTargetPermission.objects.get(profile_id=self.profile.id)
        self.assertEqual(json.loads(perm.target_names_json), ['server-1', 'server-2'])

        # Verify normalized tables were written
        self.assertEqual(
            sorted(ProfileTargetAllowlist.objects.filter(
                profile_id=self.profile.id
            ).values_list('target_name', flat=True)),
            ['server-1', 'server-2'],
        )
        self.assertEqual(
            list(ProfileTargetAttributeFilter.objects.filter(
                profile_id=self.profile.id
            ).values_list('attribute_key', 'attribute_value')),
            [('engine_type', 'oracle')],
        )
        self.assertEqual(
            list(ProfileTargetExclusion.objects.filter(
                profile_id=self.profile.id
            ).values_list('exclusion_pattern', flat=True)),
            ['DR-*'],
        )

    @override_settings(PROFILE_TARGET_PERMISSIONS_NORMALIZED_ENABLED=True)
    def test_update_permissions_syncs_normalized(self):
        """Updating permissions re-syncs normalized tables."""
        self.service.set_target_permissions(
            self.profile.id,
            {
                'targets_type': 'list',
                'target_names': ['srv-a', 'srv-b'],
            },
        )
        self.assertEqual(
            ProfileTargetAllowlist.objects.filter(profile_id=self.profile.id).count(), 2
        )

        # Update
        self.service.set_target_permissions(
            self.profile.id,
            {
                'targets_type': 'pattern',
                'target_patterns': ['prod-*'],
                'target_names': [],
            },
        )
        # Old allowlist entries should be deleted
        self.assertEqual(
            ProfileTargetAllowlist.objects.filter(profile_id=self.profile.id).count(), 0
        )
        self.assertEqual(
            list(ProfileTargetPattern.objects.filter(
                profile_id=self.profile.id
            ).values_list('pattern', flat=True)),
            ['prod-*'],
        )

    def test_set_target_permissions_no_normalized_when_flag_false(self):
        """With flag False (default), normalized tables are NOT written."""
        self.service.set_target_permissions(
            self.profile.id,
            {
                'targets_type': 'list',
                'target_names': ['server-1'],
            },
        )

        # JSON was written
        perm = ProfileTargetPermission.objects.get(profile_id=self.profile.id)
        self.assertEqual(json.loads(perm.target_names_json), ['server-1'])

        # Normalized tables NOT written
        self.assertEqual(
            ProfileTargetAllowlist.objects.filter(profile_id=self.profile.id).count(), 0
        )

    @override_settings(PROFILE_TARGET_PERMISSIONS_NORMALIZED_ENABLED=True)
    def test_pattern_type_with_patterns(self):
        """Pattern type writes target patterns to normalized tables."""
        self.service.set_target_permissions(
            self.profile.id,
            {
                'targets_type': 'pattern',
                'target_patterns': ['prod-*', 'staging-*'],
                'exclusion_patterns': ['CRITICAL-*'],
            },
        )

        self.assertEqual(
            sorted(ProfileTargetPattern.objects.filter(
                profile_id=self.profile.id
            ).values_list('pattern', flat=True)),
            ['prod-*', 'staging-*'],
        )
        self.assertEqual(
            list(ProfileTargetExclusion.objects.filter(
                profile_id=self.profile.id
            ).values_list('exclusion_pattern', flat=True)),
            ['CRITICAL-*'],
        )

    @override_settings(PROFILE_TARGET_PERMISSIONS_NORMALIZED_ENABLED=True)
    def test_filter_by_attribute_with_multiple_keys(self):
        """filter_by_attribute with complex dict → correct rows in normalized table."""
        self.service.set_target_permissions(
            self.profile.id,
            {
                'targets_type': 'all',
                'filter_by_attribute': {
                    'engine_type': ['oracle', 'mysql'],
                    'zone': ['prod'],
                },
            },
        )

        af_rows = ProfileTargetAttributeFilter.objects.filter(
            profile_id=self.profile.id
        ).order_by('attribute_key', 'attribute_value')
        self.assertEqual(af_rows.count(), 3)
        self.assertEqual(
            list(af_rows.values_list('attribute_key', 'attribute_value')),
            [('engine_type', 'mysql'), ('engine_type', 'oracle'), ('zone', 'prod')],
        )
