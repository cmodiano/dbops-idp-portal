"""
Tests for ProfileTargetPermission exclusion_patterns field helpers.
Story 25.6 - Task 5.1: Unit tests for get_exclusion_patterns() / set_exclusion_patterns().
"""

import json
from django.test import TestCase
from profiles.models import Profile, ProfileTargetPermission


class TestExclusionPatternsModelHelpers(TestCase):
    """Test get_exclusion_patterns() and set_exclusion_patterns() helpers."""

    def setUp(self):
        """Create test profile and permission."""
        self.profile = Profile.objects.create(
            name="Test Profile",
            ad_group="test-group",
            is_admin=0,
            is_auditor=0
        )
        self.perm = ProfileTargetPermission.objects.create(
            profile=self.profile,
            permission_type='ALL'
        )

    def test_get_exclusion_patterns_returns_empty_when_none(self):
        """Test get_exclusion_patterns() returns [] when field is None."""
        self.perm.exclusion_patterns_json = None
        result = self.perm.get_exclusion_patterns()
        self.assertEqual(result, [])

    def test_get_exclusion_patterns_returns_empty_when_empty_string(self):
        """Test get_exclusion_patterns() returns [] when field is empty string."""
        self.perm.exclusion_patterns_json = ''
        result = self.perm.get_exclusion_patterns()
        self.assertEqual(result, [])

    def test_get_exclusion_patterns_valid_list(self):
        """Test get_exclusion_patterns() deserializes valid JSON array."""
        patterns = ["PROD-CRITICAL-*", "DR-*", "SERVER-123"]
        self.perm.exclusion_patterns_json = json.dumps(patterns)
        result = self.perm.get_exclusion_patterns()
        self.assertEqual(result, patterns)

    def test_get_exclusion_patterns_filters_invalid_entries(self):
        """Test get_exclusion_patterns() filters out non-string and empty entries."""
        # Mix of valid and invalid patterns
        self.perm.exclusion_patterns_json = json.dumps([
            "VALID-*",
            123,  # Invalid: not a string
            "",  # Invalid: empty
            "  ",  # Invalid: whitespace only
            None,  # Invalid: None
            "ANOTHER-VALID",
        ])
        result = self.perm.get_exclusion_patterns()
        # Should only return valid non-empty strings
        self.assertEqual(result, ["VALID-*", "ANOTHER-VALID"])

    def test_get_exclusion_patterns_with_special_characters(self):
        """Test get_exclusion_patterns() handles patterns with special chars."""
        patterns = ["PROD-*", "APP-[123]-*", "SERVER_?_BACKUP"]
        self.perm.exclusion_patterns_json = json.dumps(patterns)
        result = self.perm.get_exclusion_patterns()
        self.assertEqual(result, patterns)

    def test_get_exclusion_patterns_malformed_json_returns_empty(self):
        """Test get_exclusion_patterns() returns [] on malformed JSON."""
        self.perm.exclusion_patterns_json = "{invalid json"
        self.perm.profile_id = self.profile.id  # Set for logging
        result = self.perm.get_exclusion_patterns()
        self.assertEqual(result, [])

    def test_get_exclusion_patterns_not_a_list_returns_empty(self):
        """Test get_exclusion_patterns() returns [] when JSON is not a list."""
        self.perm.exclusion_patterns_json = json.dumps({"key": "value"})
        self.perm.profile_id = self.profile.id
        result = self.perm.get_exclusion_patterns()
        self.assertEqual(result, [])

    def test_set_exclusion_patterns_with_valid_list(self):
        """Test set_exclusion_patterns() serializes list to JSON."""
        patterns = ["PROD-CRITICAL-*", "DR-*"]
        self.perm.set_exclusion_patterns(patterns)
        self.assertEqual(self.perm.exclusion_patterns_json, json.dumps(patterns))

    def test_set_exclusion_patterns_with_none(self):
        """Test set_exclusion_patterns(None) sets field to None."""
        self.perm.set_exclusion_patterns(["TEMP-*"])  # Set something first
        self.perm.set_exclusion_patterns(None)
        self.assertIsNone(self.perm.exclusion_patterns_json)

    def test_set_exclusion_patterns_with_empty_list(self):
        """Test set_exclusion_patterns([]) serializes to empty array."""
        self.perm.set_exclusion_patterns([])
        self.assertEqual(self.perm.exclusion_patterns_json, json.dumps([]))

    def test_round_trip_serialization(self):
        """Test set → get round-trip preserves data."""
        patterns = ["PROD-*", "STAGING-CRITICAL-*", "DR-*"]
        self.perm.set_exclusion_patterns(patterns)
        self.perm.save()
        
        # Reload from DB
        self.perm.refresh_from_db()
        result = self.perm.get_exclusion_patterns()
        self.assertEqual(result, patterns)
