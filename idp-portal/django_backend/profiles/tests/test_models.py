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
        Profile.objects.get_or_create(
            name='UniqueTest',
            defaults={'ad_group': 'GRP-IDP-UT'}
        )
        with self.assertRaises(Exception):  # IntegrityError
            Profile.objects.create(
                name='UniqueTest',
                ad_group='GRP-IDP-UT-2'
            )

    def test_profile_str(self):
        """Test Profile __str__ method."""
        profile, _ = Profile.objects.get_or_create(
            name='DBA',
            defaults={'ad_group': 'GRP-IDP-DBA'}
        )
        self.assertEqual(str(profile), 'DBA')

    def test_profile_is_admin_bool_property(self):
        """
        Story 30.16 AC3: Test is_admin_bool property conversion (Oracle NUMBER(1) → Python bool).
        Validates INCON-4 intentional IntegerField with boolean property wrapper.
        """
        profile, _ = Profile.objects.get_or_create(
            name='DBA',
            defaults={'ad_group': 'GRP-IDP-DBA', 'is_admin': 1, 'is_auditor': 0}
        )
        profile.is_admin = 1
        profile.is_auditor = 0
        profile.save()
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
        profile, _ = Profile.objects.get_or_create(
            name='AUDITOR',
            defaults={'ad_group': 'GRP-IDP-AUDITOR', 'is_admin': 0, 'is_auditor': 1}
        )
        profile.is_auditor = 1
        profile.is_admin = 0
        profile.save()
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
    """Tests for ProfileActionPermission model.

    Story 78.15: Legacy CLOB fields removed. Tests now verify normalized table writes
    via ProfileService.set_action_permissions().
    """

    def setUp(self):
        """Set up test data."""
        from profiles.services import ProfileService
        self.profile, _ = Profile.objects.get_or_create(
            name='DBA',
            defaults={'ad_group': 'GRP-IDP-DBA'}
        )
        self.service = ProfileService()

    def test_create_profile_action_permission(self):
        """Test creating a profile action permission via service."""
        from profiles.models_action_permission_normalized import ProfileActionAllowlist
        self.service.set_action_permissions(
            self.profile.id,
            {'actions_type': 'list', 'action_ids': [1, 2, 3]},
        )
        permission = ProfileActionPermission.objects.get(profile=self.profile)
        self.assertEqual(permission.profile, self.profile)
        self.assertEqual(permission.permission_type, 'LIST')
        self.assertEqual(
            sorted(ProfileActionAllowlist.objects.filter(
                profile_id=self.profile.id
            ).values_list('action_id', flat=True)),
            [1, 2, 3],
        )

    def test_profile_action_permission_normalized_read(self):
        """Test normalized readers via repository."""
        from profiles.action_permission_repository import get_tag_patterns, get_environments
        self.service.set_action_permissions(
            self.profile.id,
            {
                'actions_type': 'pattern',
                'tag_patterns': ['oracle', 'provisioning'],
                'environments': ['DEV', 'STAGING'],
            },
        )
        permission = ProfileActionPermission.objects.get(profile=self.profile)
        self.assertEqual(get_tag_patterns(permission), ['oracle', 'provisioning'])
        self.assertEqual(get_environments(permission), ['DEV', 'STAGING'])


@pytest.mark.django_db
class ProfileTargetPermissionModelTest(TestCase):
    """Tests for ProfileTargetPermission model.

    Story 78.15: Legacy CLOB fields removed. Tests now verify normalized table writes
    via ProfileService.set_target_permissions().
    """

    def setUp(self):
        """Set up test data."""
        from profiles.services import ProfileService
        self.profile, _ = Profile.objects.get_or_create(
            name='DBA',
            defaults={'ad_group': 'GRP-IDP-DBA'}
        )
        self.service = ProfileService()

    def test_create_profile_target_permission(self):
        """Test creating a profile target permission via service."""
        from profiles.models_target_permission_normalized import ProfileTargetAllowlist
        self.service.set_target_permissions(
            self.profile.id,
            {'targets_type': 'list', 'target_names': ['db01', 'db02']},
        )
        permission = ProfileTargetPermission.objects.get(profile=self.profile)
        self.assertEqual(permission.profile, self.profile)
        self.assertEqual(permission.permission_type, 'LIST')
        self.assertEqual(
            sorted(ProfileTargetAllowlist.objects.filter(
                profile_id=self.profile.id
            ).values_list('target_name', flat=True)),
            ['db01', 'db02'],
        )

    def test_profile_target_permission_normalized_read(self):
        """Test normalized readers via repository."""
        from profiles.target_permission_repository import get_target_patterns
        self.service.set_target_permissions(
            self.profile.id,
            {
                'targets_type': 'pattern',
                'target_patterns': ['assurance-*', 'infra-*'],
            },
        )
        permission = ProfileTargetPermission.objects.get(profile=self.profile)
        self.assertEqual(get_target_patterns(permission), ['assurance-*', 'infra-*'])
