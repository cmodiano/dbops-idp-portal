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

    def test_create_user_with_email(self):
        """Story 50.1: User peut être créé avec un email."""
        user = User.objects.create(
            username='emailuser',
            profile='DBA',
            email='emailuser@example.com'
        )
        self.assertEqual(user.email, 'emailuser@example.com')

    def test_create_user_without_email_defaults_to_none(self):
        """Story 50.1: email est NULL par défaut si non fourni."""
        user = User.objects.create(
            username='noemailuser',
            profile='DBA'
        )
        self.assertIsNone(user.email)

    def test_user_manager_create_or_update_with_email(self):
        """Story 50.1: UserManager.create_or_update stocke l'email."""
        user = User.objects.create_or_update(
            username='mgremailuser',
            profile='DBA',
            email='mgr@example.com'
        )
        self.assertEqual(user.email, 'mgr@example.com')

    def test_user_manager_create_or_update_without_email(self):
        """Story 50.1: UserManager.create_or_update sans email → email=None."""
        user = User.objects.create_or_update(
            username='mgrnoemailuser',
            profile='DBA'
        )
        self.assertIsNone(user.email)
