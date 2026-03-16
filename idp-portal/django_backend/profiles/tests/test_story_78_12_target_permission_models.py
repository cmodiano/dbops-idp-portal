"""
Story 78.12 — Tests for normalized profile target permission models.

Tests: ORM creation, unique_together constraints, FK via ProfileTargetPermission.
Tables managed by conftest.py session-scoped fixture.
"""
import pytest
from django.db import IntegrityError
from django.test import TestCase

from profiles.models import Profile, ProfileTargetPermission
from profiles.models_target_permission_normalized import (
    ProfileTargetAllowlist,
    ProfileTargetAttributeFilter,
    ProfileTargetExclusion,
    ProfileTargetPattern,
)


@pytest.mark.django_db
class ProfileTargetAllowlistModelTest(TestCase):
    def setUp(self):
        self.profile = Profile.objects.create(
            name='test-t-allowlist', ad_group='GRP-IDP-T-AL'
        )
        self.perm = ProfileTargetPermission.objects.create(
            profile=self.profile, permission_type='LIST'
        )

    def test_create_allowlist_entry(self):
        entry = ProfileTargetAllowlist.objects.create(
            profile=self.perm, target_name='server-01'
        )
        self.assertEqual(entry.profile_id, self.profile.id)
        self.assertEqual(entry.target_name, 'server-01')

    def test_unique_together_profile_target(self):
        ProfileTargetAllowlist.objects.create(profile=self.perm, target_name='server-01')
        with self.assertRaises(IntegrityError):
            ProfileTargetAllowlist.objects.create(profile=self.perm, target_name='server-01')

    def test_multiple_targets_for_profile(self):
        ProfileTargetAllowlist.objects.create(profile=self.perm, target_name='srv-1')
        ProfileTargetAllowlist.objects.create(profile=self.perm, target_name='srv-2')
        ProfileTargetAllowlist.objects.create(profile=self.perm, target_name='srv-3')
        self.assertEqual(
            ProfileTargetAllowlist.objects.filter(profile=self.perm).count(), 3
        )

    def test_str_representation(self):
        entry = ProfileTargetAllowlist.objects.create(profile=self.perm, target_name='srv-99')
        self.assertIn('srv-99', str(entry))


@pytest.mark.django_db
class ProfileTargetPatternModelTest(TestCase):
    def setUp(self):
        self.profile = Profile.objects.create(
            name='test-t-pattern', ad_group='GRP-IDP-T-PT'
        )
        self.perm = ProfileTargetPermission.objects.create(
            profile=self.profile, permission_type='PATTERN'
        )

    def test_create_pattern_entry(self):
        entry = ProfileTargetPattern.objects.create(
            profile=self.perm, pattern='prod-*'
        )
        self.assertEqual(entry.pattern, 'prod-*')

    def test_unique_together_profile_pattern(self):
        ProfileTargetPattern.objects.create(profile=self.perm, pattern='prod-*')
        with self.assertRaises(IntegrityError):
            ProfileTargetPattern.objects.create(profile=self.perm, pattern='prod-*')

    def test_str_representation(self):
        entry = ProfileTargetPattern.objects.create(
            profile=self.perm, pattern='staging-*'
        )
        self.assertIn('staging-*', str(entry))


@pytest.mark.django_db
class ProfileTargetAttributeFilterModelTest(TestCase):
    def setUp(self):
        self.profile = Profile.objects.create(
            name='test-t-attrfilter', ad_group='GRP-IDP-T-AF'
        )
        self.perm = ProfileTargetPermission.objects.create(
            profile=self.profile, permission_type='ALL'
        )

    def test_create_attribute_filter_entry(self):
        entry = ProfileTargetAttributeFilter.objects.create(
            profile=self.perm, attribute_key='engine_type', attribute_value='oracle'
        )
        self.assertEqual(entry.attribute_key, 'engine_type')
        self.assertEqual(entry.attribute_value, 'oracle')

    def test_unique_together_profile_key_value(self):
        ProfileTargetAttributeFilter.objects.create(
            profile=self.perm, attribute_key='engine_type', attribute_value='oracle'
        )
        with self.assertRaises(IntegrityError):
            ProfileTargetAttributeFilter.objects.create(
                profile=self.perm, attribute_key='engine_type', attribute_value='oracle'
            )

    def test_same_key_different_values(self):
        """Same attribute_key with different values → allowed."""
        ProfileTargetAttributeFilter.objects.create(
            profile=self.perm, attribute_key='zone', attribute_value='prod'
        )
        ProfileTargetAttributeFilter.objects.create(
            profile=self.perm, attribute_key='zone', attribute_value='staging'
        )
        self.assertEqual(
            ProfileTargetAttributeFilter.objects.filter(profile=self.perm).count(), 2
        )

    def test_str_representation(self):
        entry = ProfileTargetAttributeFilter.objects.create(
            profile=self.perm, attribute_key='zone', attribute_value='prod'
        )
        self.assertIn('zone', str(entry))
        self.assertIn('prod', str(entry))


@pytest.mark.django_db
class ProfileTargetExclusionModelTest(TestCase):
    def setUp(self):
        self.profile = Profile.objects.create(
            name='test-t-exclusion', ad_group='GRP-IDP-T-EX'
        )
        self.perm = ProfileTargetPermission.objects.create(
            profile=self.profile, permission_type='ALL'
        )

    def test_create_exclusion_entry(self):
        entry = ProfileTargetExclusion.objects.create(
            profile=self.perm, exclusion_pattern='PROD-CRITICAL-*'
        )
        self.assertEqual(entry.exclusion_pattern, 'PROD-CRITICAL-*')

    def test_unique_together_profile_exclusion(self):
        ProfileTargetExclusion.objects.create(
            profile=self.perm, exclusion_pattern='DR-*'
        )
        with self.assertRaises(IntegrityError):
            ProfileTargetExclusion.objects.create(
                profile=self.perm, exclusion_pattern='DR-*'
            )

    def test_str_representation(self):
        entry = ProfileTargetExclusion.objects.create(
            profile=self.perm, exclusion_pattern='BACKUP-*'
        )
        self.assertIn('BACKUP-*', str(entry))
