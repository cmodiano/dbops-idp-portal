"""
Tests for executions services (ExecutionService, SchedulingService).
"""

import pytest
from django.test import TestCase
from idp_auth.models import User
from catalog.models import Action
from executions.models import Execution, ExecutionStep, ExecutionStatus
from executions.services import ExecutionService
from core.models import AuditLog


@pytest.mark.django_db
class TestExecutionService(TestCase):
    """Tests for ExecutionService."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create(username='testuser', profile='DBA')
        self.action = Action.objects.create(
            name='Test Action',
            engine='Oracle',
            platform='AAP',
            status='published'
        )
        self.service = ExecutionService()
    
    def test_create_execution(self):
        """Test create_execution() creates execution with audit."""
        execution = self.service.create_execution(
            user=self.user,
            action=self.action,
            environment='dev',
            parameters={'db_name': 'testdb'}
        )
        
        self.assertIsNotNone(execution.id)
        self.assertEqual(execution.environment, 'dev')
        self.assertEqual(execution.status, ExecutionStatus.SUBMITTED)
        
        # Verify audit
        audit = AuditLog.objects.filter(
            entity_type='execution',
            entity_id=execution.id,
            action_type='EXECUTION_SUBMITTED'
        ).first()
        self.assertIsNotNone(audit)
    
    def test_create_execution_with_steps(self):
        """Test create_execution_with_steps() creates execution and steps atomically."""
        steps_data = [
            {'step_order': 1, 'step_name': 'Step 1', 'step_type': 'manual'},
            {'step_order': 2, 'step_name': 'Step 2', 'step_type': 'manual'}
        ]
        
        execution = self.service.create_execution_with_steps(
            user=self.user,
            action=self.action,
            environment='dev',
            steps_data=steps_data
        )
        
        self.assertIsNotNone(execution.id)
        
        # Verify steps created
        steps = ExecutionStep.objects.filter(execution=execution)
        self.assertEqual(steps.count(), 2)
    
    def test_update_status(self):
        """Test update_status() updates status with validation."""
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.SUBMITTED
        )
        
        updated = self.service.update_status(
            execution.id,
            ExecutionStatus.RUNNING,
            str(self.user.id)
        )
        
        self.assertEqual(updated.status, ExecutionStatus.RUNNING)
        
        # Verify audit
        audit = AuditLog.objects.filter(
            entity_type='execution',
            entity_id=execution.id,
            action_type='EXECUTION_RUNNING'
        ).first()
        self.assertIsNotNone(audit)
