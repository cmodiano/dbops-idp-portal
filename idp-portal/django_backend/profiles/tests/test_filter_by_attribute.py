"""
Tests for filter_by_attribute via normalized table (ProfileTargetAttributeFilter).
Story 23.4 / 78.15: Filter by attribute is now stored exclusively in normalized tables.
"""

from django.test import TestCase
from profiles.models import Profile, ProfileTargetPermission
from profiles.models_target_permission_normalized import ProfileTargetAttributeFilter
from profiles.target_permission_repository import get_filter_by_attribute_from_normalized
from profiles.services import ProfileService


class TestFilterByAttributeNormalized(TestCase):
    """Tests for filter_by_attribute via normalized table."""

    def setUp(self):
        self.profile = Profile.objects.create(
            name='test_filter_profile',
            ad_group='GRP-TEST',
        )
        self.svc = ProfileService()

    def test_get_filter_by_attribute_returns_none_when_no_entries(self):
        """No normalized entries → get returns None."""
        ProfileTargetPermission.objects.create(
            profile=self.profile,
            permission_type='ALL',
        )
        self.assertIsNone(get_filter_by_attribute_from_normalized(self.profile.id))

    def test_set_then_get_returns_dict(self):
        """set_target_permissions with filter_by_attribute → normalized entries."""
        value = {"engine_type": ["oracle", "sqlserver"], "zone": ["prod"]}
        self.svc.set_target_permissions(
            self.profile.id,
            {'targets_type': 'all', 'filter_by_attribute': value},
        )
        result = get_filter_by_attribute_from_normalized(self.profile.id)
        self.assertIsNotNone(result)
        self.assertEqual(sorted(result['engine_type']), ['oracle', 'sqlserver'])
        self.assertEqual(result['zone'], ['prod'])

    def test_set_empty_dict_clears(self):
        """set with empty filter_by_attribute → no attribute filter rows."""
        self.svc.set_target_permissions(
            self.profile.id,
            {'targets_type': 'all', 'filter_by_attribute': {'zone': ['prod']}},
        )
        self.svc.set_target_permissions(
            self.profile.id,
            {'targets_type': 'all', 'filter_by_attribute': {}},
        )
        self.assertIsNone(get_filter_by_attribute_from_normalized(self.profile.id))

    def test_complex_filter_with_multiple_keys(self):
        """Complex filter with multiple keys and values stored correctly."""
        value = {
            "engine_type": ["oracle", "sqlserver", "mysql"],
            "zone": ["prod", "staging"],
            "region": ["eu-west-1"]
        }
        self.svc.set_target_permissions(
            self.profile.id,
            {'targets_type': 'all', 'filter_by_attribute': value},
        )
        result = get_filter_by_attribute_from_normalized(self.profile.id)
        self.assertEqual(sorted(result['engine_type']), ['mysql', 'oracle', 'sqlserver'])
        self.assertEqual(sorted(result['zone']), ['prod', 'staging'])
        self.assertEqual(result['region'], ['eu-west-1'])
        self.assertEqual(
            ProfileTargetAttributeFilter.objects.filter(profile_id=self.profile.id).count(),
            6,  # 3 + 2 + 1
        )
