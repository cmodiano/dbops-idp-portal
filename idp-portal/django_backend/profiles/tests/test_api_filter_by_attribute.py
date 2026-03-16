"""
Tests for API endpoints with filter_by_attribute.
Story 23.4 - AC3, AC4, AC8: API serializer validation and representation tests.
"""

from django.test import TestCase
from unittest.mock import patch

from profiles.serializers import ProfileTargetPermissionsSerializer
from profiles.models import Profile, ProfileTargetPermission
from profiles.target_permission_repository import get_filter_by_attribute


VALID_CONCEPTS = ['name', 'environment', 'engine_type', 'zone']


class TestProfileTargetPermissionsSerializerValidation(TestCase):
    """Tests for ProfileTargetPermissionsSerializer filter_by_attribute validation."""

    @patch('inventory.mapper.InventoryMapper.get_available_concepts', return_value=VALID_CONCEPTS)
    def test_valid_filter_by_attribute_accepted(self, mock_concepts):
        """Valid filter_by_attribute → serializer valid."""
        data = {
            "targets_type": "all",
            "filter_by_attribute": {"engine_type": ["oracle"]}
        }
        serializer = ProfileTargetPermissionsSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data['filter_by_attribute'],
            {"engine_type": ["oracle"]}
        )

    @patch('inventory.mapper.InventoryMapper.get_available_concepts', return_value=VALID_CONCEPTS)
    def test_invalid_key_rejected(self, mock_concepts):
        """Invalid filter key → ValidationError."""
        data = {
            "targets_type": "all",
            "filter_by_attribute": {"invalid_key": ["value"]}
        }
        serializer = ProfileTargetPermissionsSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('filter_by_attribute', serializer.errors)
        error_msg = str(serializer.errors['filter_by_attribute'])
        self.assertIn('invalid_key', error_msg)
        self.assertIn('Valid attributes', error_msg)

    @patch('inventory.mapper.InventoryMapper.get_available_concepts', return_value=VALID_CONCEPTS)
    def test_empty_values_list_rejected(self, mock_concepts):
        """Empty values list → ValidationError from DictField child."""
        data = {
            "targets_type": "all",
            "filter_by_attribute": {"engine_type": []}
        }
        serializer = ProfileTargetPermissionsSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    @patch('inventory.mapper.InventoryMapper.get_available_concepts', return_value=VALID_CONCEPTS)
    def test_null_filter_accepted(self, mock_concepts):
        """null filter_by_attribute → accepted."""
        data = {
            "targets_type": "all",
            "filter_by_attribute": None,
        }
        serializer = ProfileTargetPermissionsSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    @patch('inventory.mapper.InventoryMapper.get_available_concepts', return_value=VALID_CONCEPTS)
    def test_missing_filter_accepted(self, mock_concepts):
        """Missing filter_by_attribute → accepted (optional field)."""
        data = {
            "targets_type": "all",
        }
        serializer = ProfileTargetPermissionsSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    @patch('inventory.mapper.InventoryMapper.get_available_concepts', return_value=VALID_CONCEPTS)
    def test_multiple_valid_keys_accepted(self, mock_concepts):
        """Multiple valid keys → accepted."""
        data = {
            "targets_type": "all",
            "filter_by_attribute": {
                "engine_type": ["oracle", "sqlserver"],
                "zone": ["prod"]
            }
        }
        serializer = ProfileTargetPermissionsSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    @patch('inventory.mapper.InventoryMapper.get_available_concepts', return_value=VALID_CONCEPTS)
    def test_mixed_valid_and_invalid_keys_rejected(self, mock_concepts):
        """Mix of valid + invalid keys → all invalid keys reported."""
        data = {
            "targets_type": "all",
            "filter_by_attribute": {
                "engine_type": ["oracle"],
                "bad_key": ["value"],
            }
        }
        serializer = ProfileTargetPermissionsSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        error_msg = str(serializer.errors['filter_by_attribute'])
        self.assertIn('bad_key', error_msg)

    @patch('inventory.mapper.InventoryMapper.get_available_concepts', return_value=VALID_CONCEPTS)
    def test_with_list_type_and_filter(self, mock_concepts):
        """LIST type + filter_by_attribute → both accepted."""
        data = {
            "targets_type": "list",
            "target_names": ["srv01", "srv02"],
            "filter_by_attribute": {"engine_type": ["oracle"]},
        }
        serializer = ProfileTargetPermissionsSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)


class TestProfileTargetPermissionsSerializerRepresentation(TestCase):
    """Tests for to_representation with filter_by_attribute."""

    def setUp(self):
        self.profile = Profile.objects.create(
            name='test_api_repr', ad_group='GRP-TEST',
        )
        self.target_perm = ProfileTargetPermission.objects.create(
            profile=self.profile, permission_type='ALL',
        )

    def test_representation_includes_filter_when_set(self):
        """to_representation includes filter_by_attribute when set."""
        from profiles.services import ProfileService
        ProfileService().set_target_permissions(
            self.profile.id,
            {'targets_type': 'all', 'filter_by_attribute': {'engine_type': ['oracle']}},
        )
        perm = ProfileTargetPermission.objects.get(profile=self.profile)
        serializer = ProfileTargetPermissionsSerializer(perm)
        data = serializer.data
        self.assertEqual(data['filter_by_attribute'], {"engine_type": ["oracle"]})

    def test_representation_returns_none_when_not_set(self):
        """to_representation returns None when filter not set."""
        serializer = ProfileTargetPermissionsSerializer(self.target_perm)
        data = serializer.data
        self.assertIsNone(data['filter_by_attribute'])

    def test_representation_returns_dict_not_json_string(self):
        """to_representation returns dict (not JSON string)."""
        from profiles.services import ProfileService
        ProfileService().set_target_permissions(
            self.profile.id,
            {'targets_type': 'all', 'filter_by_attribute': {'zone': ['prod']}},
        )
        perm = ProfileTargetPermission.objects.get(profile=self.profile)
        serializer = ProfileTargetPermissionsSerializer(perm)
        data = serializer.data
        self.assertIsInstance(data['filter_by_attribute'], dict)


class TestProfileServiceSetTargetPermissions(TestCase):
    """Tests for ProfileService.set_target_permissions with filter_by_attribute."""

    def setUp(self):
        self.profile = Profile.objects.create(
            name='test_service_filter', ad_group='GRP-TEST',
        )

    def test_set_target_permissions_with_filter(self):
        """set_target_permissions saves filter_by_attribute."""
        from profiles.services import ProfileService

        service = ProfileService()
        perm = service.set_target_permissions(
            self.profile.id,
            {
                'targets_type': 'all',
                'filter_by_attribute': {"engine_type": ["oracle"]},
            }
        )

        self.assertIsNotNone(perm)
        self.assertEqual(
            get_filter_by_attribute(perm),
            {"engine_type": ["oracle"]}
        )

    def test_set_target_permissions_with_null_filter(self):
        """set_target_permissions with null filter → clears it."""
        from profiles.services import ProfileService

        service = ProfileService()
        # First set a filter
        service.set_target_permissions(
            self.profile.id,
            {
                'targets_type': 'all',
                'filter_by_attribute': {"engine_type": ["oracle"]},
            }
        )
        # Then clear it
        perm = service.set_target_permissions(
            self.profile.id,
            {
                'targets_type': 'all',
                'filter_by_attribute': None,
            }
        )

        self.assertIsNone(get_filter_by_attribute(perm))

    def test_set_target_permissions_without_filter_key_preserves(self):
        """set_target_permissions without filter key.

        Story 78.12: Normalized replace semantics — omitted filter_by_attribute
        defaults to None when not in payload.
        """
        from profiles.services import ProfileService

        service = ProfileService()
        # First set a filter
        service.set_target_permissions(
            self.profile.id,
            {
                'targets_type': 'all',
                'filter_by_attribute': {"engine_type": ["oracle"]},
            }
        )
        # Update with filter explicitly preserved
        perm = service.set_target_permissions(
            self.profile.id,
            {
                'targets_type': 'all',
                'filter_by_attribute': {"engine_type": ["oracle"]},
            }
        )

        self.assertEqual(
            get_filter_by_attribute(perm),
            {"engine_type": ["oracle"]}
        )
