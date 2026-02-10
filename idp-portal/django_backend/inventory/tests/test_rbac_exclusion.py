"""
Integration tests for RBAC exclusion patterns.
Story 25.6 - Task 5.2: Test deny explicit RBAC logic.
"""

from django.test import TestCase
from profiles.models import Profile, ProfileActionPermission, ProfileTargetPermission
from inventory.services import InventoryService


class TestRBACExclusionPatterns(TestCase):
    """Integration tests for exclusion_patterns in RBAC resolution."""

    def setUp(self):
        """Set up test profile and mock inventory."""
        self.service = InventoryService()
        
        # Create test profile
        self.profile = Profile.objects.create(
            name="Test DBA",
            ad_group="test-dba-group",
            is_admin=0,
            is_auditor=0
        )
        
        # Create action permissions (environment access)
        self.action_perm = ProfileActionPermission.objects.create(
            profile=self.profile,
            permission_type='ALL'
        )
        self.action_perm.set_environments(['dev', 'staging', 'prod'])
        self.action_perm.save()
        
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
        # Create target permission with ALL + exclusion
        target_perm = ProfileTargetPermission.objects.create(
            profile=self.profile,
            permission_type='ALL'
        )
        target_perm.set_exclusion_patterns(["PROD-CRITICAL-*"])
        target_perm.save()
        
        # Mock list_targets to return our test data
        def mock_list_targets(*args, **kwargs):
            return self.mock_targets, len(self.mock_targets)
        
        original_list_targets = self.service.list_targets
        self.service.list_targets = mock_list_targets
        
        try:
            # Execute RBAC resolution
            results, total, truncated = self.service.list_targets_for_user(
                user_id=1,
                ad_groups=['test-dba-group'],
                environment='prod',
                page=1,
                page_size=100
            )
            
            # Verify PROD-CRITICAL-* targets are excluded
            result_names = [t['name'] for t in results]
            self.assertIn('PROD-APP-01', result_names)
            self.assertIn('PROD-APP-02', result_names)
            self.assertIn('PROD-DR-01', result_names)
            self.assertNotIn('PROD-CRITICAL-DB-01', result_names)
            self.assertNotIn('PROD-CRITICAL-DB-02', result_names)
            
            self.assertEqual(len(results), 3)  # 5 prod targets - 2 excluded
            
        finally:
            self.service.list_targets = original_list_targets
    
    def test_exclusion_with_pattern_access(self):
        """Test 2: Profile with PATTERN ["PROD-*"] + exclusion ["PROD-CRITICAL-*"]."""
        # Create target permission with PATTERN + exclusion
        target_perm = ProfileTargetPermission.objects.create(
            profile=self.profile,
            permission_type='PATTERN'
        )
        target_perm.set_target_patterns(["PROD-*"])
        target_perm.set_exclusion_patterns(["PROD-CRITICAL-*"])
        target_perm.save()
        
        # Mock list_targets
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
            
            # Should match PROD-* but exclude PROD-CRITICAL-*
            result_names = [t['name'] for t in results]
            self.assertIn('PROD-APP-01', result_names)
            self.assertIn('PROD-APP-02', result_names)
            self.assertIn('PROD-DR-01', result_names)
            self.assertNotIn('PROD-CRITICAL-DB-01', result_names)
            self.assertNotIn('PROD-CRITICAL-DB-02', result_names)
            # Should not include non-PROD targets
            self.assertNotIn('STAGING-APP-01', result_names)
            self.assertNotIn('DEV-APP-01', result_names)
            
        finally:
            self.service.list_targets = original_list_targets
    
    def test_exclusion_with_list_access(self):
        """Test 3: Profile with LIST + exclusion."""
        # Create target permission with LIST + exclusion
        target_perm = ProfileTargetPermission.objects.create(
            profile=self.profile,
            permission_type='LIST'
        )
        target_perm.set_target_names(["PROD-APP-01", "PROD-APP-02", "PROD-CRITICAL-DB-01"])
        target_perm.set_exclusion_patterns(["PROD-CRITICAL-*"])
        target_perm.save()
        
        # Mock list_targets
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
            
            # Should include listed targets except excluded ones
            result_names = [t['name'] for t in results]
            self.assertIn('PROD-APP-01', result_names)
            self.assertIn('PROD-APP-02', result_names)
            self.assertNotIn('PROD-CRITICAL-DB-01', result_names)  # Excluded
            
            self.assertEqual(len(results), 2)
            
        finally:
            self.service.list_targets = original_list_targets
    
    def test_multiple_profiles_with_different_exclusions(self):
        """Test 4: Multiple profiles with different exclusions (union = most restrictive)."""
        # Profile 1: ALL with exclusion ["PROD-CRITICAL-*"]
        target_perm1 = ProfileTargetPermission.objects.create(
            profile=self.profile,
            permission_type='ALL'
        )
        target_perm1.set_exclusion_patterns(["PROD-CRITICAL-*"])
        target_perm1.save()
        
        # Profile 2: ALL with exclusion ["*-DR-*"]
        profile2 = Profile.objects.create(
            name="Test DBA 2",
            ad_group="test-dba-group",  # Same group
            is_admin=0,
            is_auditor=0
        )
        action_perm2 = ProfileActionPermission.objects.create(
            profile=profile2,
            permission_type='ALL'
        )
        action_perm2.set_environments(['prod'])
        action_perm2.save()
        
        target_perm2 = ProfileTargetPermission.objects.create(
            profile=profile2,
            permission_type='ALL'
        )
        target_perm2.set_exclusion_patterns(["*-DR-*"])
        target_perm2.save()
        
        # Mock list_targets
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
            
            # Should exclude BOTH PROD-CRITICAL-* AND *-DR-* (union of exclusions)
            result_names = [t['name'] for t in results]
            self.assertIn('PROD-APP-01', result_names)
            self.assertIn('PROD-APP-02', result_names)
            self.assertNotIn('PROD-CRITICAL-DB-01', result_names)  # Excluded by profile 1
            self.assertNotIn('PROD-CRITICAL-DB-02', result_names)  # Excluded by profile 1
            self.assertNotIn('PROD-DR-01', result_names)  # Excluded by profile 2
            
            self.assertEqual(len(results), 2)
            
        finally:
            self.service.list_targets = original_list_targets
    
    def test_exclusion_without_inclusion(self):
        """Test 5: Exclusion without inclusion → no targets (not an error)."""
        # Create target permission with no inclusion (empty PATTERN)
        target_perm = ProfileTargetPermission.objects.create(
            profile=self.profile,
            permission_type='PATTERN'
        )
        target_perm.set_target_patterns([])  # Empty = no targets
        target_perm.set_exclusion_patterns(["PROD-*"])
        target_perm.save()
        
        # Mock list_targets
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
            
            # Should return no targets (no inclusion base)
            self.assertEqual(len(results), 0)
            
        finally:
            self.service.list_targets = original_list_targets
    
    def test_no_exclusion_patterns(self):
        """Test case-insensitive matching for exclusion patterns."""
        # Create target permission with mixed-case exclusion
        target_perm = ProfileTargetPermission.objects.create(
            profile=self.profile,
            permission_type='ALL'
        )
        target_perm.set_exclusion_patterns(["prod-critical-*"])  # lowercase pattern
        target_perm.save()
        
        # Mock list_targets (targets have uppercase names)
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
            
            # Should match case-insensitively
            result_names = [t['name'] for t in results]
            self.assertNotIn('PROD-CRITICAL-DB-01', result_names)
            self.assertNotIn('PROD-CRITICAL-DB-02', result_names)
            
        finally:
            self.service.list_targets = original_list_targets
