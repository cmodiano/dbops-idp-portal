"""
Tests for idp_auth services (AuthService).
"""

import pytest
from django.test import TestCase
from idp_auth.models import User
from catalog.models import Action, UserFavorite
from idp_auth.services import AuthService
from core.models import AuditLog


@pytest.mark.django_db
class TestAuthService(TestCase):
    """Tests for AuthService."""
    
    def setUp(self):
        """Set up test data."""
        self.service = AuthService()
        self.action = Action.objects.create(
            name='Test Action',
            engine='Oracle',
            platform='AAP',
            status='published'
        )
    
    def test_create_or_update_user(self):
        """Test create_or_update_user() creates or updates user with audit."""
        user = self.service.create_or_update_user(
            username='testuser',
            display_name='Test User',
            profile='DBA'
        )
        
        self.assertIsNotNone(user.id)
        self.assertEqual(user.username, 'testuser')
        
        # Verify audit
        audit = AuditLog.objects.filter(
            entity_type='user',
            entity_id=user.id,
            action_type='USER_CREATED'
        ).first()
        self.assertIsNotNone(audit)
    
    def test_add_favorite(self):
        """Test add_favorite() adds favorite with audit."""
        user = User.objects.create(username='testuser', profile='DBA')
        
        favorite = self.service.add_favorite(user.id, self.action.id)
        
        self.assertIsNotNone(favorite)
        self.assertEqual(favorite.user.id, user.id)
        self.assertEqual(favorite.action.id, self.action.id)
        
        # Verify audit
        audit = AuditLog.objects.filter(
            entity_type='action',
            entity_id=self.action.id,
            action_type='FAVORITE_ADDED'
        ).first()
        self.assertIsNotNone(audit)
    
    def test_remove_favorite(self):
        """Test remove_favorite() removes favorite with audit."""
        user = User.objects.create(username='testuser', profile='DBA')
        UserFavorite.objects.create(user=user, action=self.action)
        
        result = self.service.remove_favorite(user.id, self.action.id)
        
        self.assertTrue(result)
        self.assertFalse(UserFavorite.objects.filter(user=user, action=self.action).exists())
        
        # Verify audit
        audit = AuditLog.objects.filter(
            entity_type='action',
            entity_id=self.action.id,
            action_type='FAVORITE_REMOVED'
        ).first()
        self.assertIsNotNone(audit)
