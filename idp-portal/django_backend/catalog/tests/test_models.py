import pytest
from django.test import TestCase
from integrations.models import Integration
from catalog.models import Action, Tag, ActionTag, UserFavorite
from tests.factories import UserFactory


@pytest.mark.django_db
class ActionModelTest(TestCase):
    """Tests for Action model."""

    def setUp(self):
        """Set up test data."""
        self.user = UserFactory(
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

    def test_action_json_fields_simple(self):
        """Test JSON field helpers for Action with simple data."""
        action = Action.objects.create(
            name='Test Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP'
        )
        # Test parameters_schema
        schema = {'type': 'object', 'properties': {'db_name': {'type': 'string'}}}
        action.parameters_schema = schema
        action.save()
        self.assertEqual(action.parameters_schema, schema)

        # Test impact_rules
        impact_rules = {'DEV': {'level': 'low'}, 'PROD': {'level': 'high'}}
        action.impact_rules = impact_rules
        action.save()
        self.assertEqual(action.impact_rules, impact_rules)

    def test_action_json_fields_complex(self):
        """Test JSON field helpers with complex nested objects and arrays (Task 10.4)."""
        action = Action.objects.create(
            name='Test Action Complex',
            category='Provisioning',
            engine='Oracle',
            platform='AAP'
        )

        # Test complex nested object with arrays
        complex_parameters_schema = {
            'type': 'object',
            'properties': {
                'databases': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'name': {'type': 'string'},
                            'environments': {
                                'type': 'array',
                                'items': {'type': 'string'}
                            },
                            'config': {
                                'type': 'object',
                                'properties': {
                                    'host': {'type': 'string'},
                                    'port': {'type': 'number'},
                                    'credentials': {
                                        'type': 'object',
                                        'properties': {
                                            'username': {'type': 'string'},
                                            'password': {'type': 'string'}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        action.parameters_schema = complex_parameters_schema
        action.save()
        retrieved = action.parameters_schema
        self.assertEqual(retrieved['type'], 'object')
        self.assertIn('databases', retrieved['properties'])
        self.assertEqual(retrieved['properties']['databases']['type'], 'array')

        # Test execution_steps with array of complex objects
        complex_execution_steps = [
            {
                'step_order': 1,
                'step_name': 'Pre-flight checks',
                'step_type': 'verification',
                'conditions': {
                    'if': {'environment': 'PROD'},
                    'then': {'require_approval': True},
                    'else': {'require_approval': False}
                },
                'connectors': [
                    {'type': 'vault', 'path': 'secret/db'},
                    {'type': 'servicenow', 'table': 'change_request'}
                ]
            },
            {
                'step_order': 2,
                'step_name': 'Execute SQL',
                'step_type': 'platform',
                'sql_statements': [
                    'CREATE TABLE test1',
                    'CREATE TABLE test2'
                ],
                'rollback': {
                    'enabled': True,
                    'statements': ['DROP TABLE test1', 'DROP TABLE test2']
                }
            }
        ]
        action.execution_steps = complex_execution_steps
        action.save()
        retrieved_steps = action.execution_steps
        self.assertIsInstance(retrieved_steps, list)
        self.assertEqual(len(retrieved_steps), 2)
        self.assertEqual(retrieved_steps[0]['step_name'], 'Pre-flight checks')
        self.assertIn('conditions', retrieved_steps[0])
        self.assertIn('connectors', retrieved_steps[0])
        self.assertIsInstance(retrieved_steps[0]['connectors'], list)
        self.assertEqual(retrieved_steps[1]['step_name'], 'Execute SQL')
        self.assertIn('sql_statements', retrieved_steps[1])
        self.assertIn('rollback', retrieved_steps[1])

        # Test impact_rules with nested structures
        complex_impact_rules = {
            'DEV': {
                'level': 'low',
                'notifications': ['team-dev@example.com'],
                'approval_required': False
            },
            'STAGING': {
                'level': 'medium',
                'notifications': ['team-staging@example.com', 'manager@example.com'],
                'approval_required': True,
                'approvers': ['dba1', 'dba2']
            },
            'PROD': {
                'level': 'high',
                'notifications': ['team-prod@example.com', 'manager@example.com', 'director@example.com'],
                'approval_required': True,
                'approvers': ['dba1', 'dba2', 'dba3'],
                'change_window': {
                    'enabled': True,
                    'start_time': '22:00',
                    'end_time': '06:00',
                    'timezone': 'UTC'
                }
            }
        }
        action.impact_rules = complex_impact_rules
        action.save()
        retrieved_rules = action.impact_rules
        self.assertEqual(retrieved_rules['PROD']['level'], 'high')
        self.assertIn('change_window', retrieved_rules['PROD'])
        self.assertEqual(retrieved_rules['PROD']['change_window']['enabled'], True)
        self.assertIsInstance(retrieved_rules['STAGING']['notifications'], list)
        self.assertEqual(len(retrieved_rules['STAGING']['notifications']), 2)

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
        self.user = UserFactory(
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
