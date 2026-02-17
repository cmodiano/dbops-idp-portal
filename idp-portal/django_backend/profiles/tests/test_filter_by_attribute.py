"""
Tests for ProfileTargetPermission.filter_by_attribute_json field and helpers.
Story 23.4 - AC1, AC8: Model tests for get/set filter_by_attribute.
"""

import json
from django.test import TestCase
from profiles.models import Profile, ProfileTargetPermission


class TestFilterByAttributeModel(TestCase):
    """Tests for ProfileTargetPermission filter_by_attribute helpers."""

    def setUp(self):
        self.profile = Profile.objects.create(
            name='test_filter_profile',
            ad_group='GRP-TEST',
        )
        self.target_perm = ProfileTargetPermission.objects.create(
            profile=self.profile,
            permission_type='ALL',
        )

    def test_get_filter_by_attribute_returns_none_when_null(self):
        """filter_by_attribute_json=None → get returns None."""
        self.target_perm.filter_by_attribute_json = None
        self.assertIsNone(self.target_perm.get_filter_by_attribute())

    def test_get_filter_by_attribute_returns_none_when_empty_string(self):
        """filter_by_attribute_json='' → get returns None."""
        self.target_perm.filter_by_attribute_json = ''
        self.assertIsNone(self.target_perm.get_filter_by_attribute())

    def test_get_filter_by_attribute_returns_dict(self):
        """Valid JSON → get returns dict."""
        value = {"engine_type": ["oracle", "sqlserver"], "zone": ["prod"]}
        self.target_perm.filter_by_attribute_json = json.dumps(value)
        result = self.target_perm.get_filter_by_attribute()
        self.assertEqual(result, value)

    def test_get_filter_by_attribute_empty_dict(self):
        """Empty dict JSON → get returns empty dict."""
        self.target_perm.filter_by_attribute_json = json.dumps({})
        result = self.target_perm.get_filter_by_attribute()
        self.assertEqual(result, {})

    def test_get_filter_by_attribute_malformed_json(self):
        """Malformed JSON → get returns None with warning."""
        self.target_perm.filter_by_attribute_json = '{invalid json'
        result = self.target_perm.get_filter_by_attribute()
        self.assertIsNone(result)

    def test_set_filter_by_attribute_dict(self):
        """set with dict → serializes to JSON."""
        value = {"engine_type": ["oracle"]}
        self.target_perm.set_filter_by_attribute(value)
        self.assertEqual(
            json.loads(self.target_perm.filter_by_attribute_json),
            value
        )

    def test_set_filter_by_attribute_none_clears(self):
        """set with None → clears field."""
        self.target_perm.filter_by_attribute_json = '{"x": ["y"]}'
        self.target_perm.set_filter_by_attribute(None)
        self.assertIsNone(self.target_perm.filter_by_attribute_json)

    def test_set_then_get_roundtrip(self):
        """set → save → get roundtrip preserves data."""
        value = {"engine_type": ["oracle", "sqlserver"], "zone": ["prod"]}
        self.target_perm.set_filter_by_attribute(value)
        self.target_perm.save()

        # Re-read from DB
        perm = ProfileTargetPermission.objects.get(profile=self.profile)
        self.assertEqual(perm.get_filter_by_attribute(), value)

    def test_set_empty_dict(self):
        """set with empty dict → serializes as '{}'."""
        self.target_perm.set_filter_by_attribute({})
        self.assertEqual(self.target_perm.filter_by_attribute_json, '{}')
        self.assertEqual(self.target_perm.get_filter_by_attribute(), {})

    def test_field_is_nullable_by_default(self):
        """New ProfileTargetPermission has filter_by_attribute_json=None."""
        profile2 = Profile.objects.create(
            name='test_filter_profile_2',
            ad_group='GRP-TEST-2',
        )
        perm = ProfileTargetPermission.objects.create(
            profile=profile2,
            permission_type='ALL',
        )
        self.assertIsNone(perm.filter_by_attribute_json)
        self.assertIsNone(perm.get_filter_by_attribute())

    def test_complex_filter_with_multiple_keys(self):
        """Complex filter with multiple keys and values."""
        value = {
            "engine_type": ["oracle", "sqlserver", "mysql"],
            "zone": ["prod", "staging"],
            "region": ["eu-west-1"]
        }
        self.target_perm.set_filter_by_attribute(value)
        self.target_perm.save()

        perm = ProfileTargetPermission.objects.get(profile=self.profile)
        result = perm.get_filter_by_attribute()
        self.assertEqual(result, value)
        self.assertEqual(len(result["engine_type"]), 3)
        self.assertEqual(len(result["zone"]), 2)
