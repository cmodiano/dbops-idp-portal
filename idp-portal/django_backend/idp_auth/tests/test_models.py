import pytest
from django.test import TestCase
from idp_auth.models import User


@pytest.mark.django_db
class UserModelTest(TestCase):
    """Tests for User model."""

    def test_create_user(self):
        """Test creating a user."""
        user = User.objects.create(
            username='testuser',
            display_name='Test User',
            profile='DBA'
        )
        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.display_name, 'Test User')
        self.assertEqual(user.profile, 'DBA')
        self.assertIsNotNone(user.id)
        self.assertIsNotNone(user.created_at)
        self.assertIsNotNone(user.updated_at)

    def test_user_str(self):
        """Test User __str__ method."""
        user = User.objects.create(
            username='testuser',
            profile='DBA'
        )
        self.assertEqual(str(user), 'testuser')

    def test_user_unique_username(self):
        """Test that username must be unique."""
        User.objects.create(username='testuser', profile='DBA')
        with self.assertRaises(Exception):  # IntegrityError
            User.objects.create(username='testuser', profile='DBA')
