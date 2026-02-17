"""
Tests for BUG-BE-6: dead code `if not action` removed from add_favorite().
Story 30.3 — AC5.

Verifies that Action.DoesNotExist propagates naturally when action_id doesn't exist.
"""

import pytest
from django.test import TestCase
from catalog.models import Action
from idp_auth.services import AuthService
from tests.factories import UserFactory


@pytest.mark.django_db
class TestAddFavoriteDoesNotExist(TestCase):
    """Tests that add_favorite raises Action.DoesNotExist for invalid action_id."""

    def setUp(self):
        self.service = AuthService()
        self.user = UserFactory(profile='dba')

    def test_add_favorite_nonexistent_action_raises_does_not_exist(self):
        """add_favorite(action_id=999999) should raise Action.DoesNotExist."""
        with self.assertRaises(Action.DoesNotExist):
            self.service.add_favorite(self.user.id, 999999)

    def test_add_favorite_valid_action_succeeds(self):
        """add_favorite with valid action_id should work normally."""
        action = Action.objects.create(
            name='Test Action',
            category='Test',
            engine='Oracle',
            platform='AAP',
        )
        result = self.service.add_favorite(self.user.id, action.id)
        self.assertIsNotNone(result)
