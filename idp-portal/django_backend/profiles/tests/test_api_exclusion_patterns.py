"""
API tests for ProfileTargetPermission exclusion_patterns field.
Story 25.6 - Task 5.3: Test API endpoints accept and return exclusion_patterns.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from profiles.models import Profile, ProfileTargetPermission
from profiles.services import ProfileService
from profiles.target_permission_repository import get_exclusion_patterns

User = get_user_model()


class TestProfileTargetPermissionsAPIWithExclusion(TestCase):
    """Test GET/PUT /admin/profiles/{id}/targets with exclusion_patterns."""

    def setUp(self):
        """Set up test user, profile, and API client."""
        self.client = APIClient()

        # Create test user
        self.user = User.objects.create_user(
            username='admin_user',
            email='admin@example.com',
            password='testpass123',
            first_name='Admin',
            last_name='User',
            is_staff=True
        )
        # Set DBOPS profile for RBAC permission check
        self.user.profile = 'dbops'
        self.client.force_authenticate(user=self.user)
        
        # Profile DBOPS is created by conftest._ensure_admin_profiles

        # Create admin profile for user
        self.admin_profile = Profile.objects.create(
            name="Admin Profile",
            ad_group="admin-group",
            is_admin=1,
            is_auditor=0
        )
        
        # Create test profile
        self.profile = Profile.objects.create(
            name="Test DBA",
            ad_group="test-dba-group",
            is_admin=0,
            is_auditor=0
        )
    
    def test_get_target_permissions_returns_empty_exclusion_patterns(self):
        """Test GET returns empty array when no exclusion_patterns set."""
        # Create permission without exclusion
        ProfileTargetPermission.objects.create(
            profile=self.profile,
            permission_type='ALL'
        )
        
        response = self.client.get(f'/api/v1/admin/profiles/{self.profile.id}/targets/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()['data']
        self.assertIn('exclusion_patterns', data)
        self.assertEqual(data['exclusion_patterns'], [])
    
    def test_get_target_permissions_returns_exclusion_patterns(self):
        """Test GET returns exclusion_patterns when set."""
        # Create permission with exclusion
        exclusion_patterns = ["PROD-CRITICAL-*", "DR-*"]
        ProfileService().set_target_permissions(
            self.profile.id,
            {'targets_type': 'all', 'exclusion_patterns': exclusion_patterns},
        )

        response = self.client.get(f'/api/v1/admin/profiles/{self.profile.id}/targets/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()['data']
        self.assertEqual(data['exclusion_patterns'], sorted(exclusion_patterns))
    
    def test_put_target_permissions_with_exclusion_patterns(self):
        """Test PUT creates/updates permission with exclusion_patterns."""
        payload = {
            'targets_type': 'all',
            'target_names': [],
            'target_patterns': [],
            'exclusion_patterns': ["PROD-CRITICAL-*", "STAGING-DR-*"]
        }
        
        response = self.client.put(
            f'/api/v1/admin/profiles/{self.profile.id}/targets/',
            data=payload,
            format='json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()['data']
        self.assertEqual(data['exclusion_patterns'], ["PROD-CRITICAL-*", "STAGING-DR-*"])
        
        # Verify in DB
        perm = ProfileTargetPermission.objects.get(profile=self.profile)
        self.assertEqual(sorted(get_exclusion_patterns(perm)), sorted(["PROD-CRITICAL-*", "STAGING-DR-*"]))
    
    def test_put_target_permissions_update_exclusion_patterns(self):
        """Test PUT updates existing exclusion_patterns."""
        # Create permission with initial exclusion
        ProfileService().set_target_permissions(
            self.profile.id,
            {'targets_type': 'all', 'exclusion_patterns': ['OLD-PATTERN-*']},
        )

        # Update with new exclusion
        payload = {
            'targets_type': 'all',
            'target_names': [],
            'target_patterns': [],
            'exclusion_patterns': ["NEW-PATTERN-*"]
        }

        response = self.client.put(
            f'/api/v1/admin/profiles/{self.profile.id}/targets/',
            data=payload,
            format='json'
        )

        self.assertEqual(response.status_code, 200)

        # Verify updated
        perm = ProfileTargetPermission.objects.get(profile=self.profile)
        self.assertEqual(get_exclusion_patterns(perm), ["NEW-PATTERN-*"])
    
    def test_put_target_permissions_clear_exclusion_patterns(self):
        """Test PUT with empty list clears exclusion_patterns."""
        # Create permission with exclusion
        ProfileService().set_target_permissions(
            self.profile.id,
            {'targets_type': 'all', 'exclusion_patterns': ['TEMP-*']},
        )

        # Clear exclusion
        payload = {
            'targets_type': 'all',
            'target_names': [],
            'target_patterns': [],
            'exclusion_patterns': []
        }

        response = self.client.put(
            f'/api/v1/admin/profiles/{self.profile.id}/targets/',
            data=payload,
            format='json'
        )

        self.assertEqual(response.status_code, 200)

        # Verify cleared
        perm = ProfileTargetPermission.objects.get(profile=self.profile)
        self.assertEqual(get_exclusion_patterns(perm), [])
    
    def test_validation_rejects_non_string_patterns(self):
        """Test validation rejects exclusion_patterns with non-string entries."""
        payload = {
            'targets_type': 'all',
            'target_names': [],
            'target_patterns': [],
            'exclusion_patterns': ["VALID-*", 123, None]  # Invalid: number and null
        }
        
        response = self.client.put(
            f'/api/v1/admin/profiles/{self.profile.id}/targets/',
            data=payload,
            format='json'
        )
        
        self.assertEqual(response.status_code, 400)
        errors = response.json()
        self.assertIn('exclusion_patterns', errors)
    
    def test_validation_rejects_empty_string_patterns(self):
        """Test validation rejects exclusion_patterns with empty strings."""
        payload = {
            'targets_type': 'all',
            'target_names': [],
            'target_patterns': [],
            'exclusion_patterns': ["VALID-*", "", "  "]  # Invalid: empty and whitespace
        }
        
        response = self.client.put(
            f'/api/v1/admin/profiles/{self.profile.id}/targets/',
            data=payload,
            format='json'
        )
        
        self.assertEqual(response.status_code, 400)
        errors = response.json()
        self.assertIn('exclusion_patterns', errors)
    
    def test_put_without_exclusion_patterns_field(self):
        """Test PUT without exclusion_patterns field preserves existing value."""
        # Create permission with exclusion
        ProfileService().set_target_permissions(
            self.profile.id,
            {'targets_type': 'pattern', 'target_patterns': ['PROD-*'], 'exclusion_patterns': ['PROD-CRITICAL-*']},
        )

        # Update other fields without touching exclusion_patterns
        payload = {
            'targets_type': 'pattern',
            'target_names': [],
            'target_patterns': ["STAGING-*"]  # Changed
            # exclusion_patterns not included
        }

        response = self.client.put(
            f'/api/v1/admin/profiles/{self.profile.id}/targets/',
            data=payload,
            format='json'
        )

        self.assertEqual(response.status_code, 200)

        # Verify exclusion_patterns preserved
        perm = ProfileTargetPermission.objects.get(profile=self.profile)
        self.assertEqual(get_exclusion_patterns(perm), ["PROD-CRITICAL-*"])
