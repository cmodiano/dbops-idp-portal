"""
Story 78.11 — Tests for normalized profile action permission models.

Tests: ORM creation, unique_together constraints, FK via ProfileActionPermission.
Tables managed by conftest.py session-scoped fixture.
"""
import pytest
from django.db import IntegrityError
from django.test import TestCase

from profiles.models import Profile, ProfileActionPermission
from profiles.models_action_permission_normalized import (
    ProfileActionAllowlist,
    ProfileActionEnv,
    ProfileActionTagPattern,
)


@pytest.mark.django_db
class ProfileActionAllowlistModelTest(TestCase):
    def setUp(self):
        self.profile = Profile.objects.create(
            name='test-allowlist', ad_group='GRP-IDP-TEST-AL'
        )
        self.perm = ProfileActionPermission.objects.create(
            profile=self.profile, permission_type='LIST'
        )

    def test_create_allowlist_entry(self):
        entry = ProfileActionAllowlist.objects.create(
            profile=self.perm, action_id=42
        )
        self.assertEqual(entry.profile_id, self.profile.id)
        self.assertEqual(entry.action_id, 42)

    def test_unique_together_profile_action(self):
        ProfileActionAllowlist.objects.create(profile=self.perm, action_id=1)
        with self.assertRaises(IntegrityError):
            ProfileActionAllowlist.objects.create(profile=self.perm, action_id=1)

    def test_multiple_actions_for_profile(self):
        ProfileActionAllowlist.objects.create(profile=self.perm, action_id=1)
        ProfileActionAllowlist.objects.create(profile=self.perm, action_id=2)
        ProfileActionAllowlist.objects.create(profile=self.perm, action_id=3)
        self.assertEqual(
            ProfileActionAllowlist.objects.filter(profile=self.perm).count(), 3
        )

    def test_str_representation(self):
        entry = ProfileActionAllowlist.objects.create(profile=self.perm, action_id=99)
        self.assertIn('99', str(entry))


@pytest.mark.django_db
class ProfileActionTagPatternModelTest(TestCase):
    def setUp(self):
        self.profile = Profile.objects.create(
            name='test-tagpattern', ad_group='GRP-IDP-TEST-TP'
        )
        self.perm = ProfileActionPermission.objects.create(
            profile=self.profile, permission_type='PATTERN'
        )

    def test_create_tag_pattern_entry(self):
        entry = ProfileActionTagPattern.objects.create(
            profile=self.perm, tag_pattern='oracle'
        )
        self.assertEqual(entry.tag_pattern, 'oracle')

    def test_unique_together_profile_tag(self):
        ProfileActionTagPattern.objects.create(profile=self.perm, tag_pattern='oracle')
        with self.assertRaises(IntegrityError):
            ProfileActionTagPattern.objects.create(profile=self.perm, tag_pattern='oracle')

    def test_str_representation(self):
        entry = ProfileActionTagPattern.objects.create(
            profile=self.perm, tag_pattern='provisioning'
        )
        self.assertIn('provisioning', str(entry))


@pytest.mark.django_db
class ProfileActionEnvModelTest(TestCase):
    def setUp(self):
        self.profile = Profile.objects.create(
            name='test-env', ad_group='GRP-IDP-TEST-ENV'
        )
        self.perm = ProfileActionPermission.objects.create(
            profile=self.profile, permission_type='ALL'
        )

    def test_create_env_entry(self):
        entry = ProfileActionEnv.objects.create(
            profile=self.perm, environment='dev'
        )
        self.assertEqual(entry.environment, 'dev')

    def test_unique_together_profile_env(self):
        ProfileActionEnv.objects.create(profile=self.perm, environment='prod')
        with self.assertRaises(IntegrityError):
            ProfileActionEnv.objects.create(profile=self.perm, environment='prod')

    def test_str_representation(self):
        entry = ProfileActionEnv.objects.create(
            profile=self.perm, environment='staging'
        )
        self.assertIn('staging', str(entry))
