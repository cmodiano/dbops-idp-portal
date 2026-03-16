"""
Story 78.15 — Tests for direct normalized write via set_target_permissions().

Story 78.12 dual-write has been removed: JSON CLOB columns no longer exist.
These tests verify that set_target_permissions() writes exclusively to normalized tables.
"""
import pytest
from django.test import TestCase

from profiles.models import Profile
from profiles.models_target_permission_normalized import (
    ProfileTargetAllowlist,
    ProfileTargetAttributeFilter,
    ProfileTargetExclusion,
    ProfileTargetPattern,
)
from profiles.services import ProfileService


@pytest.mark.django_db
class DirectNormalizedWriteTargetTest(TestCase):
    def setUp(self):
        self.profile = Profile.objects.create(
            name='t-normalized-write', ad_group='GRP-IDP-TDW'
        )
        self.service = ProfileService()

    def test_set_target_permissions_writes_to_normalized_tables(self):
        """set_target_permissions writes target names, filters, exclusions to normalized tables."""
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

    def test_update_permissions_replaces_normalized_data(self):
        """Updating permissions deletes and replaces normalized table rows."""
        self.service.set_target_permissions(
            self.profile.id,
            {'targets_type': 'list', 'target_names': ['srv-a', 'srv-b']},
        )
        self.assertEqual(
            ProfileTargetAllowlist.objects.filter(profile_id=self.profile.id).count(), 2
        )

        self.service.set_target_permissions(
            self.profile.id,
            {
                'targets_type': 'pattern',
                'target_patterns': ['prod-*'],
                'target_names': [],
            },
        )
        self.assertEqual(
            ProfileTargetAllowlist.objects.filter(profile_id=self.profile.id).count(), 0
        )
        self.assertEqual(
            list(ProfileTargetPattern.objects.filter(
                profile_id=self.profile.id
            ).values_list('pattern', flat=True)),
            ['prod-*'],
        )

    def test_pattern_type_with_patterns_and_exclusions(self):
        """Pattern type writes target patterns and exclusion patterns to normalized tables."""
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
