"""
Story 78.15 — Contract tests: legacy CLOB permission fields removed.

Verifies that:
- ProfileActionPermission and ProfileTargetPermission models no longer have *_json fields.
- Django migration 0006 removes them correctly (no field on model).
- set_action_permissions / set_target_permissions write to normalized tables only.
- _permissions_differ() is order-insensitive for tag_patterns comparison.
"""
import pytest
from django.test import TestCase

from profiles.models import Profile, ProfileActionPermission, ProfileTargetPermission
from profiles.services import ProfileService


@pytest.mark.django_db
class TestLegacyCloBFieldsAbsent(TestCase):
    """AC4: Legacy *_json fields must not exist on Django models after migration 0006."""

    def test_profile_action_permission_has_no_action_ids_json(self):
        self.assertFalse(hasattr(ProfileActionPermission(), 'action_ids_json'))

    def test_profile_action_permission_has_no_tag_patterns_json(self):
        self.assertFalse(hasattr(ProfileActionPermission(), 'tag_patterns_json'))

    def test_profile_action_permission_has_no_environments_json(self):
        self.assertFalse(hasattr(ProfileActionPermission(), 'environments_json'))

    def test_profile_target_permission_has_no_target_names_json(self):
        self.assertFalse(hasattr(ProfileTargetPermission(), 'target_names_json'))

    def test_profile_target_permission_has_no_target_patterns_json(self):
        self.assertFalse(hasattr(ProfileTargetPermission(), 'target_patterns_json'))

    def test_profile_target_permission_has_no_filter_by_attribute_json(self):
        self.assertFalse(hasattr(ProfileTargetPermission(), 'filter_by_attribute_json'))

    def test_profile_target_permission_has_no_exclusion_patterns_json(self):
        self.assertFalse(hasattr(ProfileTargetPermission(), 'exclusion_patterns_json'))


@pytest.mark.django_db
class TestNormalizedWriteOnlyPath(TestCase):
    """AC4: set_action_permissions / set_target_permissions write to normalized tables only."""

    def setUp(self):
        self.profile = Profile.objects.create(
            name='contract-test-78-15', ad_group='GRP-IDP-CT'
        )
        self.service = ProfileService()

    def test_set_action_permissions_creates_header_row(self):
        perm = self.service.set_action_permissions(
            self.profile.id,
            {'actions_type': 'list', 'action_ids': [1, 2, 3], 'environments': ['dev']},
        )
        self.assertIsNotNone(perm)
        self.assertEqual(perm.permission_type, 'LIST')
        db_perm = ProfileActionPermission.objects.get(profile_id=self.profile.id)
        self.assertEqual(db_perm.permission_type, 'LIST')

    def test_set_target_permissions_creates_header_row(self):
        perm = self.service.set_target_permissions(
            self.profile.id,
            {'targets_type': 'pattern', 'target_patterns': ['db-*', 'srv-*']},
        )
        self.assertIsNotNone(perm)
        self.assertEqual(perm.permission_type, 'PATTERN')
        db_perm = ProfileTargetPermission.objects.get(profile_id=self.profile.id)
        self.assertEqual(db_perm.permission_type, 'PATTERN')

    def test_action_permission_upsert_is_idempotent(self):
        """Calling set_action_permissions twice does not create duplicate header rows."""
        self.service.set_action_permissions(
            self.profile.id,
            {'actions_type': 'all'},
        )
        self.service.set_action_permissions(
            self.profile.id,
            {'actions_type': 'all'},
        )
        self.assertEqual(
            ProfileActionPermission.objects.filter(profile_id=self.profile.id).count(), 1
        )

    def test_target_permission_upsert_is_idempotent(self):
        """Calling set_target_permissions twice does not create duplicate header rows."""
        self.service.set_target_permissions(
            self.profile.id,
            {'targets_type': 'all'},
        )
        self.service.set_target_permissions(
            self.profile.id,
            {'targets_type': 'all'},
        )
        self.assertEqual(
            ProfileTargetPermission.objects.filter(profile_id=self.profile.id).count(), 1
        )


@pytest.mark.django_db
class TestPermissionsDifferOrderInsensitive(TestCase):
    """H2 fix: _permissions_differ() must be order-insensitive for tag_patterns."""

    def setUp(self):
        from profiles.services_export_import import _permissions_differ
        self._permissions_differ = _permissions_differ
        self.profile = Profile.objects.create(
            name='order-insensitive-test', ad_group='GRP-IDP-OI'
        )
        self.service = ProfileService()
        self.service.set_action_permissions(
            self.profile.id,
            {
                'actions_type': 'pattern',
                'tag_patterns': ['oracle', 'provisioning', 'database'],
            },
        )
        self.service.set_target_permissions(
            self.profile.id,
            {'targets_type': 'all'},
        )

    def test_same_tag_patterns_different_order_returns_false(self):
        """If tag_patterns differ only in order, _permissions_differ must return False."""
        actions_payload = {
            'actions_type': 'pattern',
            'tag_patterns': ['provisioning', 'database', 'oracle'],  # different order
        }
        targets_payload = {'targets_type': 'all'}
        differs = self._permissions_differ(
            self.service, self.profile.id, actions_payload, targets_payload
        )
        self.assertFalse(differs, "Same tag_patterns in different order should not be detected as changed")

    def test_different_tag_patterns_returns_true(self):
        """If tag_patterns actually differ, _permissions_differ must return True."""
        actions_payload = {
            'actions_type': 'pattern',
            'tag_patterns': ['oracle', 'NEW-TAG'],
        }
        targets_payload = {'targets_type': 'all'}
        differs = self._permissions_differ(
            self.service, self.profile.id, actions_payload, targets_payload
        )
        self.assertTrue(differs)
