"""
Tests for Story 25.1: ExecutionTarget model, API serialization, creation flow, and cascade delete.
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from django.db import IntegrityError
from django.test import TestCase
from rest_framework.test import APIClient

from idp_auth.models import User
from catalog.models import Action
from executions.models import (
    Execution, ExecutionTarget, TargetType, ExecutionStatus,
)
from executions.serializers import ExecutionTargetSerializer, ExecutionSerializer


# =============================================================================
# 5.1: Model tests — creation, unique constraint, JSON helpers
# =============================================================================

@pytest.mark.django_db
class ExecutionTargetModelTest(TestCase):
    """Tests for the ExecutionTarget model (Task 1, Subtask 5.1)."""

    def setUp(self):
        self.user = User.objects.create(username='target_test_user', profile='DBA')
        self.action = Action.objects.create(
            name='Target Action', category='Provisioning', engine='Oracle', platform='AAP',
        )
        self.execution = Execution.objects.create(
            action=self.action, user=self.user, environment='dev', status=ExecutionStatus.SUBMITTED,
        )

    def test_create_execution_target(self):
        """Can create an ExecutionTarget and read it back."""
        target = ExecutionTarget.objects.create(
            execution=self.execution,
            target_type=TargetType.SERVER,
            target_id='srv-dev-01',
            target_name='srv-dev-01',
        )
        self.assertIsNotNone(target.id)
        self.assertEqual(target.execution, self.execution)
        self.assertEqual(target.target_type, 'SERVER')
        self.assertEqual(target.target_id, 'srv-dev-01')
        self.assertEqual(target.target_name, 'srv-dev-01')
        self.assertIsNotNone(target.created_at)

    def test_target_type_choices(self):
        """TargetType enum includes all expected values."""
        expected = {'SERVER', 'DATABASE', 'INSTANCE', 'SCHEMA', 'CLUSTER', 'OTHER'}
        actual = {c[0] for c in TargetType.choices}
        self.assertEqual(actual, expected)

    def test_unique_constraint_execution_target_type_target_id(self):
        """Duplicate (execution, target_type, target_id) raises IntegrityError."""
        ExecutionTarget.objects.create(
            execution=self.execution,
            target_type=TargetType.SERVER,
            target_id='srv-dev-01',
            target_name='srv-dev-01',
        )
        with self.assertRaises(IntegrityError):
            ExecutionTarget.objects.create(
                execution=self.execution,
                target_type=TargetType.SERVER,
                target_id='srv-dev-01',
                target_name='srv-dev-01 duplicate',
            )

    def test_same_target_id_different_types_allowed(self):
        """Same target_id with different target_type is allowed."""
        ExecutionTarget.objects.create(
            execution=self.execution,
            target_type=TargetType.SERVER,
            target_id='entity-01',
            target_name='entity-01',
        )
        t2 = ExecutionTarget.objects.create(
            execution=self.execution,
            target_type=TargetType.DATABASE,
            target_id='entity-01',
            target_name='entity-01',
        )
        self.assertIsNotNone(t2.id)

    def test_get_set_target_metadata(self):
        """JSON helper methods serialize/deserialize metadata correctly."""
        target = ExecutionTarget.objects.create(
            execution=self.execution,
            target_type=TargetType.SERVER,
            target_id='srv-dev-01',
            target_name='srv-dev-01',
        )
        metadata = {'environment': 'dev', 'engine_type': 'oracle', 'zone': 'prod'}
        target.set_target_metadata(metadata)
        target.save()

        target.refresh_from_db()
        loaded = target.get_target_metadata()
        self.assertEqual(loaded, metadata)

    def test_get_target_metadata_null(self):
        """get_target_metadata returns None when field is null."""
        target = ExecutionTarget.objects.create(
            execution=self.execution,
            target_type=TargetType.SERVER,
            target_id='srv-dev-01',
            target_name='srv-dev-01',
        )
        self.assertIsNone(target.get_target_metadata())

    def test_set_target_metadata_none_clears(self):
        """set_target_metadata(None) sets field to None."""
        target = ExecutionTarget.objects.create(
            execution=self.execution,
            target_type=TargetType.SERVER,
            target_id='srv-dev-01',
            target_name='srv-dev-01',
        )
        target.set_target_metadata({'key': 'value'})
        target.save()
        target.set_target_metadata(None)
        target.save()
        target.refresh_from_db()
        self.assertIsNone(target.get_target_metadata())

    def test_unicode_in_metadata(self):
        """ensure_ascii=False preserves Unicode characters in metadata."""
        target = ExecutionTarget.objects.create(
            execution=self.execution,
            target_type=TargetType.DATABASE,
            target_id='db-01',
            target_name='db-01',
        )
        metadata = {'description': 'Base de données café'}
        target.set_target_metadata(metadata)
        target.save()
        target.refresh_from_db()
        self.assertEqual(target.get_target_metadata()['description'], 'Base de données café')

    def test_related_name_targets(self):
        """Execution.targets.all() returns associated ExecutionTarget objects."""
        ExecutionTarget.objects.create(
            execution=self.execution,
            target_type=TargetType.SERVER,
            target_id='srv-01',
            target_name='srv-01',
        )
        ExecutionTarget.objects.create(
            execution=self.execution,
            target_type=TargetType.DATABASE,
            target_id='db-01',
            target_name='db-01',
        )
        self.assertEqual(self.execution.targets.count(), 2)

    def test_str_representation(self):
        """__str__ returns readable representation."""
        target = ExecutionTarget.objects.create(
            execution=self.execution,
            target_type=TargetType.SERVER,
            target_id='srv-dev-01',
            target_name='srv-dev-01',
        )
        self.assertIn('SERVER', str(target))
        self.assertIn('srv-dev-01', str(target))


# =============================================================================
# 5.5: Cascade delete test
# =============================================================================

@pytest.mark.django_db
class ExecutionTargetCascadeDeleteTest(TestCase):
    """Test that deleting Execution cascades to ExecutionTarget (Subtask 5.5)."""

    def setUp(self):
        self.user = User.objects.create(username='cascade_user', profile='DBA')
        self.action = Action.objects.create(
            name='Cascade Action', category='Provisioning', engine='Oracle', platform='AAP',
        )

    def test_cascade_delete(self):
        """Deleting Execution deletes all associated ExecutionTarget records."""
        execution = Execution.objects.create(
            action=self.action, user=self.user, environment='dev', status=ExecutionStatus.SUBMITTED,
        )
        ExecutionTarget.objects.create(
            execution=execution, target_type=TargetType.SERVER,
            target_id='srv-01', target_name='srv-01',
        )
        ExecutionTarget.objects.create(
            execution=execution, target_type=TargetType.DATABASE,
            target_id='db-01', target_name='db-01',
        )
        self.assertEqual(ExecutionTarget.objects.filter(execution=execution).count(), 2)

        execution.delete()
        self.assertEqual(ExecutionTarget.objects.count(), 0)


# =============================================================================
# 5.2: API POST — creation with targets creates ExecutionTarget records
# =============================================================================

@pytest.mark.django_db
class ExecutionTargetCreationFlowTest(TestCase):
    """Test that POST /executions with target_names creates ExecutionTarget records (Subtask 5.2)."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(username='flow_user', profile='DBA')
        self.client.force_authenticate(user=self.user)
        self.action = Action.objects.create(
            name='Flow Action', category='Provisioning', engine='Oracle', platform='AAP',
            status='published', requires_target=True,
        )

    def test_post_execution_creates_execution_targets(self):
        """POST /executions with target_names creates ExecutionTarget for each target."""
        allowed_targets = [
            {'name': 'srv-dev-01', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
            {'name': 'srv-dev-02', 'environment': 'dev', 'target_type': 'server', 'metadata': None, 'engine_type': 'oracle'},
        ]
        with patch('executions.views.InventoryService') as MockInventory:
            mock_inst = MagicMock()
            mock_inst.list_targets_for_user.return_value = (allowed_targets, 2, False)
            MockInventory.return_value = mock_inst

            response = self.client.post('/api/v1/executions/', {
                'action_id': self.action.id,
                'target_names': ['srv-dev-01', 'srv-dev-02'],
                'parameters': {},
            }, format='json')

        self.assertEqual(response.status_code, 201)
        execution_id = response.data['data']['execution_id']
        targets = ExecutionTarget.objects.filter(execution_id=execution_id).order_by('target_id')
        self.assertEqual(targets.count(), 2)

        t1 = targets[0]
        self.assertEqual(t1.target_type, 'SERVER')
        self.assertEqual(t1.target_id, 'srv-dev-01')
        self.assertEqual(t1.target_name, 'srv-dev-01')

        t2 = targets[1]
        self.assertEqual(t2.target_type, 'SERVER')
        self.assertEqual(t2.target_id, 'srv-dev-02')
        # Verify metadata snapshot includes engine_type from inventory
        meta = t2.get_target_metadata()
        self.assertIsNotNone(meta)
        self.assertEqual(meta.get('engine_type'), 'oracle')
        self.assertEqual(meta.get('environment'), 'dev')

    def test_post_execution_without_targets_no_execution_targets(self):
        """POST /executions without target_names creates no ExecutionTarget records."""
        action_no_target = Action.objects.create(
            name='No Target Action', category='Provisioning', engine='Oracle', platform='AAP',
            status='published', requires_target=False,
        )
        with patch('executions.views._validate_environment_against_inventory'):
            response = self.client.post('/api/v1/executions/', {
                'action_id': action_no_target.id,
                'environment': 'dev',
            }, format='json')
        self.assertEqual(response.status_code, 201)
        execution_id = response.data['data']['execution_id']
        self.assertEqual(ExecutionTarget.objects.filter(execution_id=execution_id).count(), 0)

    def test_backward_compatibility_targets_in_parameters(self):
        """POST still stores target_names in parameters._targets (backward compat)."""
        allowed_targets = [
            {'name': 'srv-01', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
        ]
        with patch('executions.views.InventoryService') as MockInventory:
            mock_inst = MagicMock()
            mock_inst.list_targets_for_user.return_value = (allowed_targets, 1, False)
            MockInventory.return_value = mock_inst

            response = self.client.post('/api/v1/executions/', {
                'action_id': self.action.id,
                'target_names': ['srv-01'],
            }, format='json')

        self.assertEqual(response.status_code, 201)
        execution = Execution.objects.get(id=response.data['data']['execution_id'])
        params = execution.get_parameters()
        self.assertEqual(params.get('_targets'), ['srv-01'])


# =============================================================================
# 5.3: API GET — verify targets[] returned in response
# =============================================================================

@pytest.mark.django_db
class ExecutionTargetSerializationTest(TestCase):
    """Test that GET /executions/{id}/ includes targets array (Subtask 5.3)."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(username='serial_user', profile='DBA')
        self.client.force_authenticate(user=self.user)
        self.action = Action.objects.create(
            name='Serial Action', category='Provisioning', engine='Oracle', platform='AAP',
        )
        self.execution = Execution.objects.create(
            action=self.action, user=self.user, environment='dev', status=ExecutionStatus.SUBMITTED,
        )

    def test_get_execution_detail_includes_targets(self):
        """GET /api/v1/executions/{id}/ returns targets array with metadata."""
        t1 = ExecutionTarget.objects.create(
            execution=self.execution, target_type=TargetType.SERVER,
            target_id='srv-01', target_name='srv-01',
        )
        t1.set_target_metadata({'environment': 'dev', 'engine_type': 'oracle'})
        t1.save()
        ExecutionTarget.objects.create(
            execution=self.execution, target_type=TargetType.DATABASE,
            target_id='db-01', target_name='db-01',
        )

        response = self.client.get(f'/api/v1/executions/{self.execution.id}/')
        self.assertEqual(response.status_code, 200)
        data = response.data['data']
        self.assertIn('targets', data)
        targets = data['targets']
        self.assertEqual(len(targets), 2)

        # Verify target fields
        server_target = next(t for t in targets if t['target_type'] == 'SERVER')
        self.assertEqual(server_target['target_id'], 'srv-01')
        self.assertEqual(server_target['target_name'], 'srv-01')
        self.assertEqual(server_target['target_metadata']['engine_type'], 'oracle')

    def test_get_execution_detail_empty_targets(self):
        """GET /api/v1/executions/{id}/ returns empty targets array when none exist."""
        response = self.client.get(f'/api/v1/executions/{self.execution.id}/')
        self.assertEqual(response.status_code, 200)
        data = response.data['data']
        self.assertEqual(data['targets'], [])


# =============================================================================
# 5.4: RBAC — only authorized targets create ExecutionTarget
# =============================================================================

@pytest.mark.django_db
class ExecutionTargetRBACTest(TestCase):
    """Test that RBAC prevents creation of ExecutionTarget for unauthorized targets (Subtask 5.4)."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(username='rbac_target_user', profile='DEV')
        self.client.force_authenticate(user=self.user)
        self.action = Action.objects.create(
            name='RBAC Target Action', category='Provisioning', engine='Oracle', platform='AAP',
            status='published', requires_target=True,
        )

    def test_forbidden_target_creates_no_execution_target(self):
        """403 on unauthorized target means no ExecutionTarget is created."""
        allowed_targets = [
            {'name': 'srv-dev-01', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
        ]
        with patch('executions.views.InventoryService') as MockInventory:
            mock_inst = MagicMock()
            mock_inst.list_targets_for_user.return_value = (allowed_targets, 1, False)
            MockInventory.return_value = mock_inst

            response = self.client.post('/api/v1/executions/', {
                'action_id': self.action.id,
                'target_names': ['srv-prod-01'],
            }, format='json')

        self.assertEqual(response.status_code, 403)
        self.assertEqual(ExecutionTarget.objects.count(), 0)
        self.assertEqual(Execution.objects.count(), 0)


# =============================================================================
# Serializer unit tests
# =============================================================================

@pytest.mark.django_db
class ExecutionTargetSerializerUnitTest(TestCase):
    """Unit tests for ExecutionTargetSerializer."""

    def setUp(self):
        self.user = User.objects.create(username='ser_unit_user', profile='DBA')
        self.action = Action.objects.create(
            name='Ser Unit Action', category='Provisioning', engine='Oracle', platform='AAP',
        )
        self.execution = Execution.objects.create(
            action=self.action, user=self.user, environment='dev', status=ExecutionStatus.SUBMITTED,
        )

    def test_serializer_output(self):
        """ExecutionTargetSerializer produces expected dict structure."""
        target = ExecutionTarget.objects.create(
            execution=self.execution, target_type=TargetType.SERVER,
            target_id='srv-01', target_name='srv-01',
        )
        target.set_target_metadata({'env': 'dev'})
        target.save()

        data = ExecutionTargetSerializer(target).data
        self.assertEqual(data['target_type'], 'SERVER')
        self.assertEqual(data['target_id'], 'srv-01')
        self.assertEqual(data['target_name'], 'srv-01')
        self.assertEqual(data['target_metadata'], {'env': 'dev'})

    def test_serializer_null_metadata(self):
        """ExecutionTargetSerializer handles null metadata."""
        target = ExecutionTarget.objects.create(
            execution=self.execution, target_type=TargetType.DATABASE,
            target_id='db-01', target_name='db-01',
        )
        data = ExecutionTargetSerializer(target).data
        self.assertIsNone(data['target_metadata'])
