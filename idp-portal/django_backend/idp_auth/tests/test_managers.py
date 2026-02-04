"""
Tests for idp_auth managers (UserManager).
"""

import pytest
from django.test import TestCase
from idp_auth.models import User, UserManager


@pytest.mark.django_db
class TestUserManager(TestCase):
    """Tests for UserManager."""
    
    def test_create_or_update(self):
        """Test create_or_update() creates or updates user."""
        user, created = User.objects.update_or_create(
            username='testuser',
            defaults={'display_name': 'Test User', 'profile': 'DBA'}
        )
        self.assertTrue(created)
        self.assertEqual(user.username, 'testuser')
        
        # Update existing
        user, created = User.objects.update_or_create(
            username='testuser',
            defaults={'display_name': 'Updated User'}
        )
        self.assertFalse(created)
        self.assertEqual(user.display_name, 'Updated User')
    
    def test_find_by_username(self):
        """Test find_by_username() finds user by username."""
        User.objects.create(
            username='testuser',
            profile='DBA'
        )
        
        user = User.objects.find_by_username('testuser')
        self.assertIsNotNone(user)
        self.assertEqual(user.username, 'testuser')
        
        # Non-existent user
        user = User.objects.find_by_username('nonexistent')
        self.assertIsNone(user)
