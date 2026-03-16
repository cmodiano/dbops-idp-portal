"""
Integration tests for RBAC exclusion patterns.
Story 25.6 / 78.15 - Task 5.2: Test deny explicit RBAC logic.
Exclusion patterns now stored in PROFILE_TARGET_EXCLUSIONS normalized table.
"""

from django.test import TestCase
from profiles.models import Profile
from profiles.services import ProfileService
from inventory.services import InventoryService


class TestRBACExclusionPatterns(TestCase):
    """Integration tests for exclusion_patterns in RBAC resolution."""

    def setUp(self):
        """Set up test profile and mock inventory."""
        self.service = InventoryService()
        self.svc = ProfileService()

        self.profile = Profile.objects.create(
            name="Test DBA",
            ad_group="test-dba-group",
            is_admin=0,
            is_auditor=0
        )

        # Create action permissions (environment access)
        self.svc.set_action_permissions(
            self.profile.id,
            {'actions_type': 'all', 'environments': ['dev', 'staging', 'prod']},
        )

        # Mock inventory targets
        self.mock_targets = [
            {'name': 'PROD-APP-01', 'environment': 'prod', 'target_type': 'server'},
            {'name': 'PROD-APP-02', 'environment': 'prod', 'target_type': 'server'},
            {'name': 'PROD-CRITICAL-DB-01', 'environment': 'prod', 'target_type': 'server'},
            {'name': 'PROD-CRITICAL-DB-02', 'environment': 'prod', 'target_type': 'server'},
            {'name': 'PROD-DR-01', 'environment': 'prod', 'target_type': 'server'},
            {'name': 'STAGING-APP-01', 'environment': 'staging', 'target_type': 'server'},
            {'name': 'DEV-APP-01', 'environment': 'dev', 'target_type': 'server'},
        ]

    def test_exclusion_with_all_access(self):
        """Test 1: Profile with ALL + exclusion ["PROD-CRITICAL-*"]."""
        self.svc.set_target_permissions(
            self.profile.id,
            {'targets_type': 'all', 'exclusion_patterns': ['PROD-CRITICAL-*']},
        )

        def mock_list_targets(*args, **kwargs):
            return self.mock_targets, len(self.mock_targets)

        original_list_targets = self.service.list_targets
        self.service.list_targets = mock_list_targets

        try:
            results, total, truncated = self.service.list_targets_for_user(
                user_id=1,
                ad_groups=['test-dba-group'],
                environment='prod',
                page=1,
                page_size=100
            )

            result_names = [t['name'] for t in results]
            self.assertIn('PROD-APP-01', result_names)
            self.assertIn('PROD-APP-02', result_names)
            self.assertIn('PROD-DR-01', result_names)
            self.assertNotIn('PROD-CRITICAL-DB-01', result_names)
            self.assertNotIn('PROD-CRITICAL-DB-02', result_names)
            self.assertEqual(len(results), 3)

        finally:
            self.service.list_targets = original_list_targets

    def test_exclusion_with_pattern_access(self):
        """Test 2: Profile with PATTERN ["PROD-*"] + exclusion ["PROD-CRITICAL-*"]."""
        self.svc.set_target_permissions(
            self.profile.id,
            {'targets_type': 'pattern', 'target_patterns': ['PROD-*'], 'exclusion_patterns': ['PROD-CRITICAL-*']},
        )

        def mock_list_targets(*args, **kwargs):
            return self.mock_targets, len(self.mock_targets)

        original_list_targets = self.service.list_targets
        self.service.list_targets = mock_list_targets

        try:
            results, total, truncated = self.service.list_targets_for_user(
                user_id=1,
                ad_groups=['test-dba-group'],
                page=1,
                page_size=100
            )

            result_names = [t['name'] for t in results]
            self.assertIn('PROD-APP-01', result_names)
            self.assertIn('PROD-APP-02', result_names)
            self.assertIn('PROD-DR-01', result_names)
            self.assertNotIn('PROD-CRITICAL-DB-01', result_names)
            self.assertNotIn('PROD-CRITICAL-DB-02', result_names)
            self.assertNotIn('STAGING-APP-01', result_names)
            self.assertNotIn('DEV-APP-01', result_names)

        finally:
            self.service.list_targets = original_list_targets

    def test_exclusion_with_list_access(self):
        """Test 3: Profile with LIST + exclusion."""
        self.svc.set_target_permissions(
            self.profile.id,
            {
                'targets_type': 'list',
                'target_names': ['PROD-APP-01', 'PROD-APP-02', 'PROD-CRITICAL-DB-01'],
                'exclusion_patterns': ['PROD-CRITICAL-*'],
            },
        )

        def mock_list_targets(*args, **kwargs):
            return self.mock_targets, len(self.mock_targets)

        original_list_targets = self.service.list_targets
        self.service.list_targets = mock_list_targets

        try:
            results, total, truncated = self.service.list_targets_for_user(
                user_id=1,
                ad_groups=['test-dba-group'],
                page=1,
                page_size=100
            )

            result_names = [t['name'] for t in results]
            self.assertIn('PROD-APP-01', result_names)
            self.assertIn('PROD-APP-02', result_names)
            self.assertNotIn('PROD-CRITICAL-DB-01', result_names)
            self.assertEqual(len(results), 2)

        finally:
            self.service.list_targets = original_list_targets

    def test_multiple_profiles_with_different_exclusions(self):
        """Test 4: Multiple profiles with different exclusions (union = most restrictive)."""
        self.svc.set_target_permissions(
            self.profile.id,
            {'targets_type': 'all', 'exclusion_patterns': ['PROD-CRITICAL-*']},
        )

        profile2 = Profile.objects.create(
            name="Test DBA 2",
            ad_group="test-dba-group",
            is_admin=0,
            is_auditor=0
        )
        self.svc.set_action_permissions(
            profile2.id,
            {'actions_type': 'all', 'environments': ['prod']},
        )
        self.svc.set_target_permissions(
            profile2.id,
            {'targets_type': 'all', 'exclusion_patterns': ['*-DR-*']},
        )

        def mock_list_targets(*args, **kwargs):
            return self.mock_targets, len(self.mock_targets)

        original_list_targets = self.service.list_targets
        self.service.list_targets = mock_list_targets

        try:
            results, total, truncated = self.service.list_targets_for_user(
                user_id=1,
                ad_groups=['test-dba-group'],
                environment='prod',
                page=1,
                page_size=100
            )

            result_names = [t['name'] for t in results]
            self.assertIn('PROD-APP-01', result_names)
            self.assertIn('PROD-APP-02', result_names)
            self.assertNotIn('PROD-CRITICAL-DB-01', result_names)
            self.assertNotIn('PROD-CRITICAL-DB-02', result_names)
            self.assertNotIn('PROD-DR-01', result_names)
            self.assertEqual(len(results), 2)

        finally:
            self.service.list_targets = original_list_targets

    def test_exclusion_without_inclusion(self):
        """Test 5: Exclusion without inclusion → no targets (not an error)."""
        self.svc.set_target_permissions(
            self.profile.id,
            {'targets_type': 'pattern', 'target_patterns': [], 'exclusion_patterns': ['PROD-*']},
        )

        def mock_list_targets(*args, **kwargs):
            return self.mock_targets, len(self.mock_targets)

        original_list_targets = self.service.list_targets
        self.service.list_targets = mock_list_targets

        try:
            results, total, truncated = self.service.list_targets_for_user(
                user_id=1,
                ad_groups=['test-dba-group'],
                page=1,
                page_size=100
            )
            self.assertEqual(len(results), 0)

        finally:
            self.service.list_targets = original_list_targets

    def test_case_insensitive_exclusion(self):
        """Test case-insensitive matching for exclusion patterns."""
        self.svc.set_target_permissions(
            self.profile.id,
            {'targets_type': 'all', 'exclusion_patterns': ['prod-critical-*']},  # lowercase
        )

        def mock_list_targets(*args, **kwargs):
            return self.mock_targets, len(self.mock_targets)

        original_list_targets = self.service.list_targets
        self.service.list_targets = mock_list_targets

        try:
            results, total, truncated = self.service.list_targets_for_user(
                user_id=1,
                ad_groups=['test-dba-group'],
                environment='prod',
                page=1,
                page_size=100
            )

            result_names = [t['name'] for t in results]
            self.assertNotIn('PROD-CRITICAL-DB-01', result_names)
            self.assertNotIn('PROD-CRITICAL-DB-02', result_names)

        finally:
            self.service.list_targets = original_list_targets
