import pytest
from django.test import TestCase
from profiles.models import Profile, ProfileActionPermission, ProfileTargetPermission


@pytest.mark.django_db
class ProfileModelTest(TestCase):
    """Tests for Profile model."""

    def test_create_profile(self):
        """Test creating a profile."""
        profile = Profile.objects.create(
            name='DBA',
            description='Database Administrator',
            ad_group='GRP-IDP-DBA',
            is_admin=1,
            is_auditor=0
        )
        self.assertEqual(profile.name, 'DBA')
        self.assertEqual(profile.ad_group, 'GRP-IDP-DBA')
        self.assertEqual(profile.is_admin, 1)
        self.assertEqual(profile.is_auditor, 0)
        self.assertIsNotNone(profile.id)
        self.assertIsNotNone(profile.created_at)

    def test_profile_unique_name(self):
        """Test that profile name must be unique."""
        Profile.objects.create(
            name='DBA',
            ad_group='GRP-IDP-DBA'
        )
        with self.assertRaises(Exception):  # IntegrityError
            Profile.objects.create(
                name='DBA',
                ad_group='GRP-IDP-DBA-2'
            )

    def test_profile_str(self):
        """Test Profile __str__ method."""
        profile = Profile.objects.create(
            name='DBA',
            ad_group='GRP-IDP-DBA'
        )
        self.assertEqual(str(profile), 'DBA')


@pytest.mark.django_db
class ProfileActionPermissionModelTest(TestCase):
    """Tests for ProfileActionPermission model."""

    def setUp(self):
        """Set up test data."""
        self.profile = Profile.objects.create(
            name='DBA',
            ad_group='GRP-IDP-DBA'
        )

    def test_create_profile_action_permission(self):
        """Test creating a profile action permission."""
        permission = ProfileActionPermission.objects.create(
            profile=self.profile,
            permission_type='LIST',
            action_ids_json='[1, 2, 3]'
        )
        self.assertEqual(permission.profile, self.profile)
        self.assertEqual(permission.permission_type, 'LIST')
        self.assertEqual(permission.get_action_ids(), [1, 2, 3])

    def test_profile_action_permission_json_helpers(self):
        """Test JSON field helpers."""
        permission = ProfileActionPermission.objects.create(
            profile=self.profile,
            permission_type='PATTERN',
            tag_patterns_json='["oracle", "provisioning"]'
        )
        self.assertEqual(permission.get_tag_patterns(), ['oracle', 'provisioning'])

        permission.set_environments(['DEV', 'STAGING'])
        permission.save()
        self.assertEqual(permission.get_environments(), ['DEV', 'STAGING'])


@pytest.mark.django_db
class ProfileTargetPermissionModelTest(TestCase):
    """Tests for ProfileTargetPermission model."""

    def setUp(self):
        """Set up test data."""
        self.profile = Profile.objects.create(
            name='DBA',
            ad_group='GRP-IDP-DBA'
        )

    def test_create_profile_target_permission(self):
        """Test creating a profile target permission."""
        permission = ProfileTargetPermission.objects.create(
            profile=self.profile,
            permission_type='LIST',
            target_names_json='["db01", "db02"]'
        )
        self.assertEqual(permission.profile, self.profile)
        self.assertEqual(permission.permission_type, 'LIST')
        self.assertEqual(permission.get_target_names(), ['db01', 'db02'])

    def test_profile_target_permission_json_helpers(self):
        """Test JSON field helpers."""
        permission = ProfileTargetPermission.objects.create(
            profile=self.profile,
            permission_type='PATTERN',
            target_patterns_json='["assurance-*", "infra-*"]'
        )
        self.assertEqual(permission.get_target_patterns(), ['assurance-*', 'infra-*'])
