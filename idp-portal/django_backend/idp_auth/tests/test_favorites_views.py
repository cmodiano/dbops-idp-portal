"""
Tests for favorites API endpoints.
Story 18.5: GET /users/me/favorites/ should exclude disabled actions.
"""

import pytest
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from idp_auth.models import User
from catalog.models import Action, ActionStatus, UserFavorite


@pytest.mark.django_db
class TestUserFavoritesView(TestCase):
    """Tests for GET /api/v1/users/me/favorites/ endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(username='testuser', profile='DBA')
        self.client.force_authenticate(user=self.user)

    def test_get_favorites_excludes_disabled_actions(self):
        """Story 18.5: GET /users/me/favorites/ should exclude disabled actions."""
        # Create 2 actions: 1 published, 1 disabled
        action_pub = Action.objects.create(
            name='Active Action', engine='Oracle', platform='AAP',
            status=ActionStatus.PUBLISHED
        )
        action_disabled = Action.objects.create(
            name='Disabled Action', engine='Oracle', platform='AAP',
            status=ActionStatus.DISABLED,
            deleted_at=timezone.now(), deletion_reason='Test disabled'
        )

        # Create favorites for both
        UserFavorite.objects.create(user=self.user, action=action_pub)
        UserFavorite.objects.create(user=self.user, action=action_disabled)

        # Call API
        response = self.client.get('/api/v1/users/me/favorites/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 1)
        self.assertEqual(response.data['data'][0]['action_id'], action_pub.id)

    def test_get_favorites_includes_published_and_draft(self):
        """Story 18.5: GET /users/me/favorites/ should include published and draft actions."""
        action_pub = Action.objects.create(
            name='Published Action', engine='Oracle', platform='AAP',
            status=ActionStatus.PUBLISHED
        )
        action_draft = Action.objects.create(
            name='Draft Action', engine='Oracle', platform='AAP',
            status=ActionStatus.DRAFT
        )

        UserFavorite.objects.create(user=self.user, action=action_pub)
        UserFavorite.objects.create(user=self.user, action=action_draft)

        response = self.client.get('/api/v1/users/me/favorites/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 2)
        action_ids = [item['action_id'] for item in response.data['data']]
        self.assertIn(action_pub.id, action_ids)
        self.assertIn(action_draft.id, action_ids)

    def test_get_favorites_empty_when_all_disabled(self):
        """Story 18.5: Returns empty when all favorited actions are disabled."""
        action_disabled = Action.objects.create(
            name='Disabled Action', engine='Oracle', platform='AAP',
            status=ActionStatus.DISABLED,
            deleted_at=timezone.now(), deletion_reason='Test disabled'
        )
        UserFavorite.objects.create(user=self.user, action=action_disabled)

        response = self.client.get('/api/v1/users/me/favorites/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 0)

    def test_get_favorites_empty_when_no_favorites(self):
        """Code Review H3: Returns empty list when user has no favorites at all."""
        # User has NO favorites (new user scenario)
        response = self.client.get('/api/v1/users/me/favorites/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'data': []})
        self.assertEqual(len(response.data['data']), 0)


@pytest.mark.django_db
class TestFavoritesCountConsistency(TestCase):
    """Story 18.5: Integration test — favorites count matches visible actions."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(username='testuser', profile='DBA')
        self.client.force_authenticate(user=self.user)

    def test_favorites_count_matches_active_actions(self):
        """Story 18.5 AC6: Favorites count should match number of visible actions."""
        import time
        # Create 5 actions: 3 published, 2 disabled
        published_actions = []
        for i in range(3):
            action = Action.objects.create(
                name=f'Published Action {i}', engine='Oracle', platform='AAP',
                status=ActionStatus.PUBLISHED
            )
            published_actions.append(action)
            UserFavorite.objects.create(user=self.user, action=action)
            time.sleep(0.01)  # Ensure different timestamps

        for i in range(2):
            action = Action.objects.create(
                name=f'Disabled Action {i}', engine='Oracle', platform='AAP',
                status=ActionStatus.DISABLED,
                deleted_at=timezone.now(), deletion_reason='Test disabled'
            )
            UserFavorite.objects.create(user=self.user, action=action)

        # GET favorites — should return 3 (published only)
        response = self.client.get('/api/v1/users/me/favorites/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        favorites_count = len(response.data['data'])

        # Verify count matches active favorites count
        self.assertEqual(favorites_count, 3)

        # Verify all returned favorites have active actions
        for fav in response.data['data']:
            action = Action.objects.get(id=fav['action_id'])
            self.assertNotEqual(action.status, ActionStatus.DISABLED)

        # Code Review L2: Verify ordering is DESC by created_at
        created_at_list = [fav['created_at'] for fav in response.data['data']]
        # Should be in descending order (newest first)
        self.assertEqual(created_at_list, sorted(created_at_list, reverse=True),
                        "Favorites should be ordered by created_at DESC")
