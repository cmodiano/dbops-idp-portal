import pytest
from django.test import TestCase
from profiles.models import Profile, ProfileActionPermission, ProfileTargetPermission


@pytest.mark.django_db
class ProfileModelTest(TestCase):
    """Tests for Profile model."""

    def test_create_profile(self):
        """Test creating a profile."""
        profile, _ = Profile.objects.get_or_create(
            name='DBA',
            defaults={
                'description': 'Database Administrator',
                'ad_group': 'GRP-IDP-DBA',
                'is_admin': 1,
                'is_auditor': 0,
            }
        )
        profile.description = 'Database Administrator'
        profile.ad_group = 'GRP-IDP-DBA'
        profile.is_admin = 1
        profile.is_auditor = 0
        profile.save()
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

    def test_profile_is_admin_bool_property(self):
        """
        Story 30.16 AC3: Test is_admin_bool property conversion (Oracle NUMBER(1) → Python bool).
        Validates INCON-4 intentional IntegerField with boolean property wrapper.
        """
        profile = Profile.objects.create(
            name='DBA',
            ad_group='GRP-IDP-DBA',
            is_admin=1,
            is_auditor=0
        )
        # Test property conversion
        self.assertIsInstance(profile.is_admin_bool, bool)
        self.assertTrue(profile.is_admin_bool)
        self.assertFalse(profile.is_auditor_bool)

        # Test property after update
        profile.is_admin = 0
        profile.is_auditor = 1
        self.assertFalse(profile.is_admin_bool)
        self.assertTrue(profile.is_auditor_bool)

    def test_profile_is_auditor_bool_property(self):
        """
        Story 30.16 AC3: Test is_auditor_bool property edge cases.
        """
        profile = Profile.objects.create(
            name='AUDITOR',
            ad_group='GRP-IDP-AUDITOR',
            is_admin=0,
            is_auditor=1
        )
        self.assertTrue(profile.is_auditor_bool)
        self.assertFalse(profile.is_admin_bool)

    def test_profile_is_approver_bool_property_zero_is_false(self):
        """
        Story 57.14 AC1: Test is_approver_bool property — 0 → False.
        Validates INCON-4 pattern for is_approver (Oracle NUMBER(1)).
        """
        profile = Profile.objects.create(
            name='REGULAR',
            ad_group='GRP-IDP-REGULAR',
            is_approver=0
        )
        self.assertIsInstance(profile.is_approver_bool, bool)
        self.assertFalse(profile.is_approver_bool)

    def test_profile_is_approver_bool_property_one_is_true(self):
        """
        Story 57.14 AC1: Test is_approver_bool property — 1 → True.
        Validates INCON-4 pattern for is_approver (Oracle NUMBER(1)).
        """
        profile = Profile.objects.create(
            name='APPROVER',
            ad_group='GRP-IDP-APPROVER',
            is_approver=1
        )
        self.assertIsInstance(profile.is_approver_bool, bool)
        self.assertTrue(profile.is_approver_bool)

    def test_profile_is_approver_default_is_zero(self):
        """
        Story 57.14 AC1: Test is_approver defaults to 0 when not specified.
        """
        profile = Profile.objects.create(
            name='DEFAULT_APPROVER',
            ad_group='GRP-IDP-DEFAULT'
        )
        self.assertEqual(profile.is_approver, 0)
        self.assertFalse(profile.is_approver_bool)

    def test_profile_is_approver_bool_property_nonone_is_false(self):
        """
        Story 57.14 AC1: Test is_approver_bool uses strict equality (== 1).
        Any value other than exactly 1 (e.g. 2) returns False.
        Validates INCON-4 — property is is_approver == 1, not bool(is_approver).
        """
        profile = Profile(
            name='EDGE_CASE',
            ad_group='GRP-IDP-EDGE',
            is_approver=2  # Hors plage Oracle CHECK (0,1) — non insérable en DB
        )
        self.assertIsInstance(profile.is_approver_bool, bool)
        self.assertFalse(profile.is_approver_bool)


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
