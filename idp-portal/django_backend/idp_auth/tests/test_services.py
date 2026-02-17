"""
Tests for idp_auth services (AuthService).
"""

import pytest
from django.test import TestCase
from django.utils import timezone
from idp_auth.models import User
from catalog.models import Action, ActionStatus, UserFavorite
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

    def test_list_favorites_excludes_disabled_actions(self):
        """Story 18.5: list_favorites() should exclude disabled actions."""
        user = User.objects.create(username='testuser', profile='DBA')

        # Create 3 actions: 2 published, 1 disabled
        action_pub1 = Action.objects.create(
            name='Action Published 1', engine='Oracle', platform='AAP',
            status=ActionStatus.PUBLISHED
        )
        action_pub2 = Action.objects.create(
            name='Action Published 2', engine='Oracle', platform='AAP',
            status=ActionStatus.PUBLISHED
        )
        action_disabled = Action.objects.create(
            name='Action Disabled', engine='Oracle', platform='AAP',
            status=ActionStatus.DISABLED,
            deleted_at=timezone.now(), deletion_reason='Test disabled'
        )

        # Create favorites for all 3 actions
        UserFavorite.objects.create(user=user, action=action_pub1)
        UserFavorite.objects.create(user=user, action=action_pub2)
        UserFavorite.objects.create(user=user, action=action_disabled)

        # Call list_favorites
        favorites = self.service.list_favorites(user.id)

        # Assert only 2 favorites returned (disabled excluded)
        self.assertEqual(favorites.count(), 2)
        action_ids = [fav.action_id for fav in favorites]
        self.assertIn(action_pub1.id, action_ids)
        self.assertIn(action_pub2.id, action_ids)
        self.assertNotIn(action_disabled.id, action_ids)

    def test_list_favorites_includes_draft_actions(self):
        """Story 18.5: list_favorites() should include draft actions."""
        user = User.objects.create(username='testuser', profile='DBA')

        action_draft = Action.objects.create(
            name='Action Draft', engine='Oracle', platform='AAP',
            status=ActionStatus.DRAFT
        )
        UserFavorite.objects.create(user=user, action=action_draft)

        favorites = self.service.list_favorites(user.id)

        self.assertEqual(favorites.count(), 1)
        self.assertEqual(favorites.first().action_id, action_draft.id)

    def test_list_favorites_ordering_by_created_at_desc(self):
        """Code Review H2: Verify list_favorites() returns results ordered by created_at DESC."""
        user = User.objects.create(username='testuser', profile='DBA')

        # Create 3 actions with different timestamps
        action1 = Action.objects.create(
            name='Action 1', engine='Oracle', platform='AAP',
            status=ActionStatus.PUBLISHED
        )
        action2 = Action.objects.create(
            name='Action 2', engine='Oracle', platform='AAP',
            status=ActionStatus.PUBLISHED
        )
        action3 = Action.objects.create(
            name='Action 3', engine='Oracle', platform='AAP',
            status=ActionStatus.PUBLISHED
        )

        # Create favorites with different timestamps (oldest first)
        import time
        UserFavorite.objects.create(user=user, action=action1)
        time.sleep(0.01)  # Ensure different timestamps
        UserFavorite.objects.create(user=user, action=action2)
        time.sleep(0.01)
        UserFavorite.objects.create(user=user, action=action3)

        favorites = list(self.service.list_favorites(user.id))

        # Should return in DESC order: fav3, fav2, fav1 (newest first)
        self.assertEqual(len(favorites), 3)
        self.assertEqual(favorites[0].action_id, action3.id)
        self.assertEqual(favorites[1].action_id, action2.id)
        self.assertEqual(favorites[2].action_id, action1.id)

    def test_add_disabled_action_not_listed_in_favorites(self):
        """Code Review M2: Adding disabled action should succeed but not appear in list_favorites()."""
        user = User.objects.create(username='testuser', profile='DBA')

        # Create disabled action
        action_disabled = Action.objects.create(
            name='Disabled Action', engine='Oracle', platform='AAP',
            status=ActionStatus.DISABLED,
            deleted_at=timezone.now(), deletion_reason='Test'
        )

        # Add to favorites (should succeed)
        favorite = self.service.add_favorite(user.id, action_disabled.id)
        self.assertIsNotNone(favorite)

        # Verify exists in DB
        self.assertTrue(UserFavorite.objects.filter(user=user, action=action_disabled).exists())

        # But should NOT appear in list_favorites()
        favorites = self.service.list_favorites(user.id)
        self.assertEqual(favorites.count(), 0)

    def test_is_favorite_returns_false_for_disabled_action(self):
        """Code Review H1: is_favorite() should return False for disabled actions."""
        user = User.objects.create(username='testuser', profile='DBA')

        # Create disabled action and add to favorites
        action_disabled = Action.objects.create(
            name='Disabled Action', engine='Oracle', platform='AAP',
            status=ActionStatus.DISABLED,
            deleted_at=timezone.now(), deletion_reason='Test'
        )
        UserFavorite.objects.create(user=user, action=action_disabled)

        # is_favorite() should return False (UX consistency)
        result = self.service.is_favorite(user.id, action_disabled.id)
        self.assertFalse(result)
