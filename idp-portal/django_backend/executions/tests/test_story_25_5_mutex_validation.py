"""
Story 25.5: Mutex inter-actions - Validation tests.

Tests for:
- Mutex validation at execution submission
- same_target=True: blocks only with target intersection
- same_target=False: blocks globally
- Active statuses: RUNNING, PENDING_APPROVAL, SUBMITTED
- Symmetric enforcement (A→B and B→A)
"""
import pytest
from unittest.mock import patch, MagicMock
from django.test import TestCase
from rest_framework.test import APIClient

from catalog.models import Action, ActionStatus, ActionMutex
from executions.models import Execution, ExecutionStatus, ExecutionTarget
from idp_auth.models import User


@pytest.mark.django_db
class TestStory255MutexValidation(TestCase):
    """Task 5: Mutex validation at execution submission."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(username='mutex_user', profile='DBA')
        self.client.force_authenticate(user=self.user)
        
        # Create test actions
        self.action_patching = Action.objects.create(
            name='Patching Oracle',
            category='Patching',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            requires_target=True,
        )
        
        self.action_backup = Action.objects.create(
            name='Backup Database',
            category='Administration',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            requires_target=True,
        )
        
        self.action_monitoring = Action.objects.create(
            name='Health Check',
            category='Monitoring',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            requires_target=True,
        )

    def test_mutex_same_target_blocks_execution_same_target(self):
        """
        Task 5.1: Mutex with same_target=True blocks execution on same target.
        AC1: RUNNING execution for action B on target X blocks action A on target X.
        """
        # Create mutex rule: patching ⊗ backup (same_target=True)
        ActionMutex.objects.create(
            action=self.action_patching,
            incompatible_with=self.action_backup,
            same_target=True,
            description='Patching et backup incompatibles sur même cible'
        )
        
        # Create active execution for backup on srv-prod-01
        backup_exec = Execution.objects.create(
            user=self.user,
            action=self.action_backup,
            environment='prod',
            status=ExecutionStatus.RUNNING,
        )
        ExecutionTarget.objects.create(
            execution=backup_exec,
            target_type='server',
            target_id='srv-prod-01',
            target_name='srv-prod-01',
        )
        
        # Mock inventory
        allowed_targets = [
            {'name': 'srv-prod-01', 'environment': 'prod', 'target_type': 'server', 'metadata': None},
        ]
        with patch('executions.validators.target_validator.InventoryService') as MockInventory:
            mock_inst = MagicMock()
            mock_inst.list_targets_for_user.return_value = (allowed_targets, 1, False)
            MockInventory.return_value = mock_inst
            
            # Attempt to submit patching on same target
            response = self.client.post('/api/v1/executions/', {
                'action_id': self.action_patching.id,
                'target_names': ['srv-prod-01'],
                'parameters': {},
            }, format='json')
        
        # Should be rejected with 409 MUTEX_VIOLATION
        self.assertEqual(response.status_code, 409)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error']['code'], 'MUTEX_VIOLATION')
        self.assertIn('backup', response.data['error']['message'].lower())
        
        # Verify execution was NOT created
        patching_execs = Execution.objects.filter(action=self.action_patching)
        self.assertEqual(patching_execs.count(), 0)

    def test_mutex_same_target_allows_execution_different_target(self):
        """
        Task 5.1: Mutex with same_target=True allows execution on different target.
        AC1: RUNNING execution for action B on target X does NOT block action A on target Y.
        """
        # Create mutex rule: patching ⊗ backup (same_target=True)
        ActionMutex.objects.create(
            action=self.action_patching,
            incompatible_with=self.action_backup,
            same_target=True,
        )
        
        # Create active execution for backup on srv-prod-01
        backup_exec = Execution.objects.create(
            user=self.user,
            action=self.action_backup,
            environment='prod',
            status=ExecutionStatus.RUNNING,
        )
        ExecutionTarget.objects.create(
            execution=backup_exec,
            target_type='server',
            target_id='srv-prod-01',
            target_name='srv-prod-01',
        )
        
        # Mock inventory with different target
        allowed_targets = [
            {'name': 'srv-prod-02', 'environment': 'prod', 'target_type': 'server', 'metadata': None},
        ]
        with patch('executions.validators.target_validator.InventoryService') as MockInventory:
            mock_inst = MagicMock()
            mock_inst.list_targets_for_user.return_value = (allowed_targets, 1, False)
            MockInventory.return_value = mock_inst
            
            # Submit patching on different target
            response = self.client.post('/api/v1/executions/', {
                'action_id': self.action_patching.id,
                'target_names': ['srv-prod-02'],
                'parameters': {},
            }, format='json')
        
        # Should succeed
        self.assertEqual(response.status_code, 201)
        self.assertIn('data', response.data)
        
        # Verify execution WAS created
        patching_execs = Execution.objects.filter(action=self.action_patching)
        self.assertEqual(patching_execs.count(), 1)

    def test_mutex_global_blocks_execution_any_target(self):
        """
        Task 5.2: Mutex with same_target=False blocks execution globally.
        AC2: RUNNING execution for action B blocks action A regardless of target.
        """
        # Create mutex rule: patching ⊗ monitoring (same_target=False, global)
        ActionMutex.objects.create(
            action=self.action_patching,
            incompatible_with=self.action_monitoring,
            same_target=False,
            description='Patching et monitoring incompatibles globalement'
        )
        
        # Create active execution for monitoring on srv-prod-01
        monitoring_exec = Execution.objects.create(
            user=self.user,
            action=self.action_monitoring,
            environment='prod',
            status=ExecutionStatus.RUNNING,
        )
        ExecutionTarget.objects.create(
            execution=monitoring_exec,
            target_type='server',
            target_id='srv-prod-01',
            target_name='srv-prod-01',
        )
        
        # Mock inventory with different target
        allowed_targets = [
            {'name': 'srv-prod-99', 'environment': 'prod', 'target_type': 'server', 'metadata': None},
        ]
        with patch('executions.validators.target_validator.InventoryService') as MockInventory:
            mock_inst = MagicMock()
            mock_inst.list_targets_for_user.return_value = (allowed_targets, 1, False)
            MockInventory.return_value = mock_inst
            
            # Attempt patching on completely different target
            response = self.client.post('/api/v1/executions/', {
                'action_id': self.action_patching.id,
                'target_names': ['srv-prod-99'],
                'parameters': {},
            }, format='json')
        
        # Should be rejected with 409 MUTEX_VIOLATION
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['error']['code'], 'MUTEX_VIOLATION')
        self.assertIn('health check', response.data['error']['message'].lower())
        
        # Verify execution was NOT created
        patching_execs = Execution.objects.filter(action=self.action_patching)
        self.assertEqual(patching_execs.count(), 0)

    def test_mutex_ignores_completed_executions(self):
        """
        Task 5.2: Mutex only blocks active statuses (RUNNING, PENDING_APPROVAL, SUBMITTED).
        AC1: COMPLETED, FAILED, CANCELLED executions do NOT block.
        """
        # Create mutex rule
        ActionMutex.objects.create(
            action=self.action_patching,
            incompatible_with=self.action_backup,
            same_target=True,
        )
        
        # Create COMPLETED execution for backup
        backup_exec = Execution.objects.create(
            user=self.user,
            action=self.action_backup,
            environment='prod',
            status=ExecutionStatus.COMPLETED,  # Terminal status
        )
        ExecutionTarget.objects.create(
            execution=backup_exec,
            target_type='server',
            target_id='srv-prod-01',
            target_name='srv-prod-01',
        )
        
        # Mock inventory
        allowed_targets = [
            {'name': 'srv-prod-01', 'environment': 'prod', 'target_type': 'server', 'metadata': None},
        ]
        with patch('executions.validators.target_validator.InventoryService') as MockInventory:
            mock_inst = MagicMock()
            mock_inst.list_targets_for_user.return_value = (allowed_targets, 1, False)
            MockInventory.return_value = mock_inst
            
            # Submit patching on same target - should succeed
            response = self.client.post('/api/v1/executions/', {
                'action_id': self.action_patching.id,
                'target_names': ['srv-prod-01'],
                'parameters': {},
            }, format='json')
        
        # Should succeed because backup is COMPLETED
        self.assertEqual(response.status_code, 201)
        patching_execs = Execution.objects.filter(action=self.action_patching)
        self.assertEqual(patching_execs.count(), 1)

    def test_mutex_blocks_submitted_status(self):
        """Task 5.2: SUBMITTED status blocks new executions."""
        ActionMutex.objects.create(
            action=self.action_patching,
            incompatible_with=self.action_backup,
            same_target=True,
        )
        
        # Create SUBMITTED execution for backup
        backup_exec = Execution.objects.create(
            user=self.user,
            action=self.action_backup,
            environment='prod',
            status=ExecutionStatus.SUBMITTED,  # Active status
        )
        ExecutionTarget.objects.create(
            execution=backup_exec,
            target_type='server',
            target_id='srv-prod-01',
            target_name='srv-prod-01',
        )
        
        allowed_targets = [
            {'name': 'srv-prod-01', 'environment': 'prod', 'target_type': 'server', 'metadata': None},
        ]
        with patch('executions.validators.target_validator.InventoryService') as MockInventory:
            mock_inst = MagicMock()
            mock_inst.list_targets_for_user.return_value = (allowed_targets, 1, False)
            MockInventory.return_value = mock_inst
            
            response = self.client.post('/api/v1/executions/', {
                'action_id': self.action_patching.id,
                'target_names': ['srv-prod-01'],
                'parameters': {},
            }, format='json')
        
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['error']['code'], 'MUTEX_VIOLATION')

    def test_mutex_blocks_pending_approval_status(self):
        """Task 5.2: PENDING_APPROVAL status blocks new executions."""
        ActionMutex.objects.create(
            action=self.action_patching,
            incompatible_with=self.action_backup,
            same_target=True,
        )
        
        # Create PENDING_APPROVAL execution for backup
        backup_exec = Execution.objects.create(
            user=self.user,
            action=self.action_backup,
            environment='prod',
            status=ExecutionStatus.PENDING_APPROVAL,  # Active status
        )
        ExecutionTarget.objects.create(
            execution=backup_exec,
            target_type='server',
            target_id='srv-prod-01',
            target_name='srv-prod-01',
        )
        
        allowed_targets = [
            {'name': 'srv-prod-01', 'environment': 'prod', 'target_type': 'server', 'metadata': None},
        ]
        with patch('executions.validators.target_validator.InventoryService') as MockInventory:
            mock_inst = MagicMock()
            mock_inst.list_targets_for_user.return_value = (allowed_targets, 1, False)
            MockInventory.return_value = mock_inst
            
            response = self.client.post('/api/v1/executions/', {
                'action_id': self.action_patching.id,
                'target_names': ['srv-prod-01'],
                'parameters': {},
            }, format='json')
        
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['error']['code'], 'MUTEX_VIOLATION')

    def test_mutex_symmetric_enforcement(self):
        """
        Task 2.3: Symmetric enforcement - B→A also blocks when A→B exists.
        Option B validation: check both directions in validate_action_mutex.
        """
        # Create ONE-WAY rule: patching → backup (no symmetric rule in DB)
        ActionMutex.objects.create(
            action=self.action_patching,
            incompatible_with=self.action_backup,
            same_target=True,
        )
        
        # Create active execution for patching
        patching_exec = Execution.objects.create(
            user=self.user,
            action=self.action_patching,
            environment='prod',
            status=ExecutionStatus.RUNNING,
        )
        ExecutionTarget.objects.create(
            execution=patching_exec,
            target_type='server',
            target_id='srv-prod-01',
            target_name='srv-prod-01',
        )
        
        allowed_targets = [
            {'name': 'srv-prod-01', 'environment': 'prod', 'target_type': 'server', 'metadata': None},
        ]
        with patch('executions.validators.target_validator.InventoryService') as MockInventory:
            mock_inst = MagicMock()
            mock_inst.list_targets_for_user.return_value = (allowed_targets, 1, False)
            MockInventory.return_value = mock_inst
            
            # Attempt to submit backup - should be blocked even though rule is patching→backup
            response = self.client.post('/api/v1/executions/', {
                'action_id': self.action_backup.id,
                'target_names': ['srv-prod-01'],
                'parameters': {},
            }, format='json')
        
        # Should be blocked by symmetric enforcement
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['error']['code'], 'MUTEX_VIOLATION')

    def test_mutex_target_intersection_partial(self):
        """
        Task 5.1: Mutex blocks if ANY target overlaps (partial intersection).
        Execution A targets [srv-01, srv-02], execution B targets [srv-02, srv-03] → blocked.
        """
        ActionMutex.objects.create(
            action=self.action_patching,
            incompatible_with=self.action_backup,
            same_target=True,
        )
        
        # Create active execution for backup on [srv-prod-01, srv-prod-02]
        backup_exec = Execution.objects.create(
            user=self.user,
            action=self.action_backup,
            environment='prod',
            status=ExecutionStatus.RUNNING,
        )
        ExecutionTarget.objects.create(
            execution=backup_exec,
            target_type='server',
            target_id='srv-prod-01',
            target_name='srv-prod-01',
        )
        ExecutionTarget.objects.create(
            execution=backup_exec,
            target_type='server',
            target_id='srv-prod-02',
            target_name='srv-prod-02',
        )
        
        # Attempt patching on [srv-prod-02, srv-prod-03] - overlaps on srv-prod-02
        allowed_targets = [
            {'name': 'srv-prod-02', 'environment': 'prod', 'target_type': 'server', 'metadata': None},
            {'name': 'srv-prod-03', 'environment': 'prod', 'target_type': 'server', 'metadata': None},
        ]
        with patch('executions.validators.target_validator.InventoryService') as MockInventory:
            mock_inst = MagicMock()
            mock_inst.list_targets_for_user.return_value = (allowed_targets, 2, False)
            MockInventory.return_value = mock_inst
            
            response = self.client.post('/api/v1/executions/', {
                'action_id': self.action_patching.id,
                'target_names': ['srv-prod-02', 'srv-prod-03'],
                'parameters': {},
            }, format='json')
        
        # Should be blocked due to overlap on srv-prod-02
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['error']['code'], 'MUTEX_VIOLATION')

    def test_no_mutex_rule_allows_execution(self):
        """Task 5.3: No mutex rule → execution allowed."""
        # No mutex rule created
        
        # Create active execution for backup
        backup_exec = Execution.objects.create(
            user=self.user,
            action=self.action_backup,
            environment='prod',
            status=ExecutionStatus.RUNNING,
        )
        ExecutionTarget.objects.create(
            execution=backup_exec,
            target_type='server',
            target_id='srv-prod-01',
            target_name='srv-prod-01',
        )
        
        allowed_targets = [
            {'name': 'srv-prod-01', 'environment': 'prod', 'target_type': 'server', 'metadata': None},
        ]
        with patch('executions.validators.target_validator.InventoryService') as MockInventory:
            mock_inst = MagicMock()
            mock_inst.list_targets_for_user.return_value = (allowed_targets, 1, False)
            MockInventory.return_value = mock_inst
            
            response = self.client.post('/api/v1/executions/', {
                'action_id': self.action_patching.id,
                'target_names': ['srv-prod-01'],
                'parameters': {},
            }, format='json')
        
        # Should succeed - no mutex rule
        self.assertEqual(response.status_code, 201)

    def test_execution_and_execution_targets_not_created_on_mutex_violation(self):
        """
        Task 5.3: Verify no Execution or ExecutionTarget created when mutex blocks.
        """
        ActionMutex.objects.create(
            action=self.action_patching,
            incompatible_with=self.action_backup,
            same_target=True,
        )
        
        backup_exec = Execution.objects.create(
            user=self.user,
            action=self.action_backup,
            environment='prod',
            status=ExecutionStatus.RUNNING,
        )
        ExecutionTarget.objects.create(
            execution=backup_exec,
            target_type='server',
            target_id='srv-prod-01',
            target_name='srv-prod-01',
        )
        
        initial_exec_count = Execution.objects.count()
        initial_target_count = ExecutionTarget.objects.count()
        
        allowed_targets = [
            {'name': 'srv-prod-01', 'environment': 'prod', 'target_type': 'server', 'metadata': None},
        ]
        with patch('executions.validators.target_validator.InventoryService') as MockInventory:
            mock_inst = MagicMock()
            mock_inst.list_targets_for_user.return_value = (allowed_targets, 1, False)
            MockInventory.return_value = mock_inst
            
            response = self.client.post('/api/v1/executions/', {
                'action_id': self.action_patching.id,
                'target_names': ['srv-prod-01'],
                'parameters': {},
            }, format='json')
        
        # Verify counts unchanged
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Execution.objects.count(), initial_exec_count)
        self.assertEqual(ExecutionTarget.objects.count(), initial_target_count)

    def test_mutex_global_with_requires_target_false(self):
        """
        Code Review Fix (CRITICAL-3): Test mutex for actions with requires_target=False.
        Global actions (no targets) should still respect mutex rules.
        """
        # Create global action (no targets required)
        global_maintenance = Action.objects.create(
            name='Global Maintenance',
            category='Administration',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            requires_target=False,  # Global action
        )
        
        # Create mutex: patching ⊗ global_maintenance (global)
        ActionMutex.objects.create(
            action=self.action_patching,
            incompatible_with=global_maintenance,
            same_target=False,
            description='Patching incompatible with global maintenance'
        )
        
        # Create active execution for global maintenance
        maintenance_exec = Execution.objects.create(
            user=self.user,
            action=global_maintenance,
            environment='prod',
            status=ExecutionStatus.RUNNING,
        )
        # No ExecutionTarget for global action
        
        # Attempt patching on any target - should be blocked globally
        allowed_targets = [
            {'name': 'srv-prod-01', 'environment': 'prod', 'target_type': 'server', 'metadata': None},
        ]
        with patch('executions.validators.target_validator.InventoryService') as MockInventory:
            mock_inst = MagicMock()
            mock_inst.list_targets_for_user.return_value = (allowed_targets, 1, False)
            MockInventory.return_value = mock_inst
            
            response = self.client.post('/api/v1/executions/', {
                'action_id': self.action_patching.id,
                'target_names': ['srv-prod-01'],
                'parameters': {},
            }, format='json')
        
        # Should be blocked by global mutex
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['error']['code'], 'MUTEX_VIOLATION')

    def test_mutex_allows_global_action_without_targets(self):
        """
        Code Review Fix (CRITICAL-3): Test submitting global action (no targets) with no mutex conflict.
        Ensures validated_targets=[] doesn't cause NameError.
        """
        # Create global action
        global_report = Action.objects.create(
            name='Global Report',
            category='Monitoring',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            requires_target=False,
        )
        
        # Mock inventory to validate environment
        with patch('executions.validators.target_validator.InventoryService') as MockInventory, \
             patch('executions.validators.payload_validator._validate_environment_against_inventory'):
            mock_inst = MagicMock()
            mock_inst.list_environments.return_value = ['dev', 'staging', 'prod']
            MockInventory.return_value = mock_inst

            # Submit global action without targets
            response = self.client.post('/api/v1/executions/', {
                'action_id': global_report.id,
                'environment': 'prod',
                'parameters': {},
            }, format='json')
        
        # Should succeed (no mutex, no targets required)
        self.assertEqual(response.status_code, 201)
        self.assertIn('data', response.data)
        
        # Verify execution created
        global_execs = Execution.objects.filter(action=global_report)
        self.assertEqual(global_execs.count(), 1)
