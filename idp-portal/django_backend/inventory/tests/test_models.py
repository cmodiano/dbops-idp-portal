"""
Tests for inventory data structures.
Story 13.1 - Target dataclass tests.
"""

from django.test import TestCase
from inventory.models import Target, TargetEnvironment, TargetType


class TargetDataclassTests(TestCase):
    """Tests for Target dataclass."""

    def test_target_creation(self):
        """Test target is created with correct attributes."""
        target = Target(
            name='srv-web-01',
            environment=TargetEnvironment.DEV,
            target_type=TargetType.SERVER
        )
        self.assertEqual(target.name, 'srv-web-01')
        self.assertEqual(target.environment, 'dev')
        self.assertEqual(target.target_type, 'server')

    def test_target_to_dict(self):
        """Test target conversion to dictionary."""
        target = Target(
            name='db-01',
            environment=TargetEnvironment.PROD,
            target_type=TargetType.DATABASE,
            metadata={'version': '19c'}
        )
        result = target.to_dict()
        self.assertEqual(result['name'], 'db-01')
        self.assertEqual(result['environment'], 'prod')
        self.assertEqual(result['target_type'], 'database')
        self.assertEqual(result['metadata'], {'version': '19c'})

    def test_target_from_dict(self):
        """Test target creation from dictionary."""
        data = {
            'name': 'cluster-01',
            'environment': 'staging',
            'target_type': 'cluster',
            'metadata': {'nodes': 3}
        }
        target = Target.from_dict(data)
        self.assertEqual(target.name, 'cluster-01')
        self.assertEqual(target.environment, 'staging')
        self.assertEqual(target.target_type, 'cluster')
        self.assertEqual(target.metadata, {'nodes': 3})

    def test_target_defaults(self):
        """Test target default values."""
        target = Target(name='test', environment='dev')
        self.assertEqual(target.target_type, TargetType.SERVER)
        self.assertIsNone(target.metadata)


class TargetEnvironmentTests(TestCase):
    """Tests for TargetEnvironment constants."""

    def test_environment_values(self):
        """Test environment constant values."""
        self.assertEqual(TargetEnvironment.DEV, 'dev')
        self.assertEqual(TargetEnvironment.STAGING, 'staging')
        self.assertEqual(TargetEnvironment.PROD, 'prod')

    def test_environment_values_list(self):
        """Test VALUES list contains all environments.
        Story 13.7: Note that VALUES is deprecated - environments come from inventory API.
        This test is kept for backward compatibility but VALUES should not be used in new code.
        """
        # Story 13.7: VALUES is deprecated but kept for backward compatibility
        # In production, environments come from GET /api/v1/inventory/environments
        self.assertIn('dev', TargetEnvironment.VALUES)
        self.assertIn('staging', TargetEnvironment.VALUES)
        self.assertIn('prod', TargetEnvironment.VALUES)


class TargetTypeTests(TestCase):
    """Tests for TargetType constants."""

    def test_type_values(self):
        """Test type constant values."""
        self.assertEqual(TargetType.SERVER, 'server')
        self.assertEqual(TargetType.DATABASE, 'database')
        self.assertEqual(TargetType.GROUP, 'group')
        self.assertEqual(TargetType.CLUSTER, 'cluster')
        self.assertEqual(TargetType.OTHER, 'other')

    def test_type_values_list(self):
        """Test VALUES list contains all types."""
        self.assertIn('server', TargetType.VALUES)
        self.assertIn('database', TargetType.VALUES)
        self.assertIn('cluster', TargetType.VALUES)
