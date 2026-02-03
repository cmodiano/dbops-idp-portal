import pytest
import json
from django.test import TestCase
from idp_auth.models import User
from integrations.models import Integration
from catalog.models import Action, Tag, ActionTag, UserFavorite


@pytest.mark.django_db
class ActionModelTest(TestCase):
    """Tests for Action model."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create(
            username='testuser',
            profile='DBA'
        )
        self.integration = Integration.objects.create(
            type='aap',
            name='Test AAP',
            base_url='https://aap.example.com'
        )

    def test_create_action(self):
        """Test creating an action."""
        action = Action.objects.create(
            name='Test Action',
            description='Test Description',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status='draft',
            created_by=self.user,
            integration=self.integration
        )
        self.assertEqual(action.name, 'Test Action')
        self.assertEqual(action.category, 'Provisioning')
        self.assertEqual(action.engine, 'Oracle')
        self.assertEqual(action.platform, 'AAP')
        self.assertIsNotNone(action.id)
        self.assertIsNotNone(action.created_at)

    def test_action_json_fields(self):
        """Test JSON field helpers for Action."""
        action = Action.objects.create(
            name='Test Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP'
        )
        # Test parameters_schema
        schema = {'type': 'object', 'properties': {'db_name': {'type': 'string'}}}
        action.set_parameters_schema(schema)
        action.save()
        self.assertEqual(action.get_parameters_schema(), schema)
        
        # Test impact_rules
        impact_rules = {'DEV': {'level': 'low'}, 'PROD': {'level': 'high'}}
        action.set_impact_rules(impact_rules)
        action.save()
        self.assertEqual(action.get_impact_rules(), impact_rules)

    def test_action_str(self):
        """Test Action __str__ method."""
        action = Action.objects.create(
            name='Test Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP'
        )
        self.assertEqual(str(action), 'Test Action')


@pytest.mark.django_db
class TagModelTest(TestCase):
    """Tests for Tag model."""

    def test_create_tag(self):
        """Test creating a tag."""
        tag = Tag.objects.create(name='oracle')
        self.assertEqual(tag.name, 'oracle')
        self.assertIsNotNone(tag.id)
        self.assertIsNotNone(tag.created_at)

    def test_tag_unique_name(self):
        """Test that tag name must be unique."""
        Tag.objects.create(name='oracle')
        with self.assertRaises(Exception):  # IntegrityError
            Tag.objects.create(name='oracle')


@pytest.mark.django_db
class ActionTagModelTest(TestCase):
    """Tests for ActionTag model."""

    def setUp(self):
        """Set up test data."""
        self.action = Action.objects.create(
            name='Test Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP'
        )
        self.tag = Tag.objects.create(name='oracle')

    def test_create_action_tag(self):
        """Test creating an action-tag relationship."""
        action_tag = ActionTag.objects.create(
            action=self.action,
            tag=self.tag
        )
        self.assertEqual(action_tag.action, self.action)
        self.assertEqual(action_tag.tag, self.tag)

    def test_action_tag_unique_together(self):
        """Test that action-tag combination must be unique."""
        ActionTag.objects.create(action=self.action, tag=self.tag)
        with self.assertRaises(Exception):  # IntegrityError
            ActionTag.objects.create(action=self.action, tag=self.tag)


@pytest.mark.django_db
class UserFavoriteModelTest(TestCase):
    """Tests for UserFavorite model."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create(
            username='testuser',
            profile='DBA'
        )
        self.action = Action.objects.create(
            name='Test Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP'
        )

    def test_create_user_favorite(self):
        """Test creating a user favorite."""
        favorite = UserFavorite.objects.create(
            user=self.user,
            action=self.action
        )
        self.assertEqual(favorite.user, self.user)
        self.assertEqual(favorite.action, self.action)
        self.assertIsNotNone(favorite.created_at)
