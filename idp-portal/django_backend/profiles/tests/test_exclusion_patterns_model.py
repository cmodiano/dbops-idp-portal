"""
Tests for ProfileTargetPermission exclusion patterns via normalized tables.

Story 78.15: Legacy exclusion_patterns_json CLOB field removed.
Exclusion patterns are now stored in PROFILE_TARGET_EXCLUSIONS table
and managed via ProfileService.set_target_permissions().
"""
import pytest
from django.test import TestCase
from profiles.models import Profile, ProfileTargetPermission
from profiles.models_target_permission_normalized import ProfileTargetExclusion
from profiles.services import ProfileService
from profiles.target_permission_repository import get_exclusion_patterns


@pytest.mark.django_db
class TestExclusionPatternsNormalized(TestCase):
    """Test exclusion patterns via normalized table (Story 78.15)."""

    def setUp(self):
        self.profile = Profile.objects.create(
            name="Test Profile Excl",
            ad_group="test-group-excl",
            is_admin=0,
            is_auditor=0,
        )
        self.service = ProfileService()

    def test_get_exclusion_patterns_returns_empty_when_none(self):
        """get_exclusion_patterns returns [] when no exclusion rows exist."""
        self.service.set_target_permissions(
            self.profile.id,
            {'targets_type': 'all'},
        )
        perm = ProfileTargetPermission.objects.get(profile=self.profile)
        self.assertEqual(get_exclusion_patterns(perm), [])

    def test_get_exclusion_patterns_valid_list(self):
        """Exclusion patterns are returned sorted from normalized table."""
        patterns = ["PROD-CRITICAL-*", "DR-*", "SERVER-123"]
        self.service.set_target_permissions(
            self.profile.id,
            {'targets_type': 'all', 'exclusion_patterns': patterns},
        )
        perm = ProfileTargetPermission.objects.get(profile=self.profile)
        result = get_exclusion_patterns(perm)
        self.assertEqual(sorted(result), sorted(patterns))

    def test_set_exclusion_patterns_stores_in_normalized_table(self):
        """set_target_permissions stores exclusion patterns in normalized table."""
        patterns = ["PROD-CRITICAL-*", "DR-*"]
        self.service.set_target_permissions(
            self.profile.id,
            {'targets_type': 'all', 'exclusion_patterns': patterns},
        )
        stored = list(ProfileTargetExclusion.objects.filter(
            profile_id=self.profile.id
        ).values_list('exclusion_pattern', flat=True))
        self.assertEqual(sorted(stored), sorted(patterns))

    def test_update_exclusion_patterns_replaces_previous(self):
        """Updating target permissions replaces exclusion patterns in normalized table."""
        self.service.set_target_permissions(
            self.profile.id,
            {'targets_type': 'all', 'exclusion_patterns': ['OLD-*']},
        )
        self.service.set_target_permissions(
            self.profile.id,
            {'targets_type': 'all', 'exclusion_patterns': ['NEW-A-*', 'NEW-B-*']},
        )
        stored = sorted(ProfileTargetExclusion.objects.filter(
            profile_id=self.profile.id
        ).values_list('exclusion_pattern', flat=True))
        self.assertEqual(stored, ['NEW-A-*', 'NEW-B-*'])

    def test_round_trip_via_service(self):
        """set_target_permissions → get_exclusion_patterns round-trip preserves data."""
        patterns = ["PROD-*", "STAGING-CRITICAL-*", "DR-*"]
        self.service.set_target_permissions(
            self.profile.id,
            {'targets_type': 'all', 'exclusion_patterns': patterns},
        )
        perm = ProfileTargetPermission.objects.get(profile=self.profile)
        result = get_exclusion_patterns(perm)
        self.assertEqual(sorted(result), sorted(patterns))
