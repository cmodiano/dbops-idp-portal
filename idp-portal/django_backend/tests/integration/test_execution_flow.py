"""
Integration tests for execution flow.

Story M.9: Tests unitaires et d'intégration
Tests: soumission execution → moteur → plateforme → résultat → audit
"""

import pytest
from django.test import TestCase
from django.utils import timezone

from idp_auth.models import User
from catalog.models import Action, ActionStatus
from integrations.models import Integration
from executions.models import (
    Execution, ExecutionStatus,
    ExecutionStep, ExecutionStepStatus, ExecutionStepType
)
from executions.services import ExecutionService
from core.models import AuditLog


@pytest.mark.django_db
@pytest.mark.integration
class TestExecutionFlow(TestCase):
    """Integration tests for complete execution flow."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create(
            username='exec_user',
            display_name='Execution Test User',
            profile='DBA'
        )
        self.approver = User.objects.create(
            username='approver_user',
            display_name='Approver User',
            profile='DBOPS'
        )
        self.integration = Integration.objects.create(
            type='aap',
            name='Execution AAP',
            base_url='https://aap.example.com'
        )
        self.action = Action.objects.create(
            name='Execution Test Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            created_by=self.user,
            integration=self.integration
        )

    def test_complete_execution_flow_success(self):
        """Test complete execution flow from submission to completion."""
        # Step 1: Submit execution
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.SUBMITTED
        )
        execution.set_parameters({
            'target_host': 'db-dev-01.example.com',
            'database_name': 'DEVDB'
        })
        execution.save()

        # Log submission
        AuditLog.objects.create_entry(
            user_id=str(self.user.id),
            action_type='EXECUTION_SUBMITTED',
            entity_type='execution',
            entity_id=execution.id
        )

        self.assertEqual(execution.status, ExecutionStatus.SUBMITTED)

        # Step 2: Create execution steps
        step_vault = ExecutionStep.objects.create(
            execution=execution,
            step_order=1,
            step_name='Fetch credentials from Vault',
            step_type=ExecutionStepType.VAULT,
            status=ExecutionStepStatus.PENDING
        )
        step_snow = ExecutionStep.objects.create(
            execution=execution,
            step_order=2,
            step_name='Create ServiceNow change',
            step_type=ExecutionStepType.SERVICENOW,
            status=ExecutionStepStatus.PENDING
        )
        step_platform = ExecutionStep.objects.create(
            execution=execution,
            step_order=3,
            step_name='Execute on AAP',
            step_type=ExecutionStepType.PLATFORM,
            status=ExecutionStepStatus.PENDING
        )

        # Step 3: Transition to RUNNING (use state machine - Story 22.12 review fix)
        execution_service = ExecutionService()
        execution = execution_service.update_status(execution.id, ExecutionStatus.RUNNING, str(self.user.id))

        # Step 4: Complete each step
        step_vault.status = ExecutionStepStatus.COMPLETED
        step_vault.started_at = timezone.now()
        step_vault.completed_at = timezone.now()
        step_vault.save()

        step_snow.status = ExecutionStepStatus.COMPLETED
        step_snow.started_at = timezone.now()
        step_snow.completed_at = timezone.now()
        step_snow.save()

        execution.servicenow_change_id = 'CHG0001234'
        execution.save()

        step_platform.status = ExecutionStepStatus.COMPLETED
        step_platform.started_at = timezone.now()
        step_platform.completed_at = timezone.now()
        step_platform.platform_job_id = '12345'
        step_platform.set_output({'job_status': 'successful', 'changes_made': 5})
        step_platform.save()

        # Step 5: Complete execution (use state machine - Story 22.12 review fix)
        execution = execution_service.update_status(execution.id, ExecutionStatus.COMPLETED, str(self.user.id))

        # Verify final state
        self.assertEqual(execution.status, ExecutionStatus.COMPLETED)
        self.assertIsNotNone(execution.started_at)
        self.assertIsNotNone(execution.completed_at)
        self.assertEqual(execution.servicenow_change_id, 'CHG0001234')

        # Verify all steps completed
        steps = ExecutionStep.objects.filter(execution=execution)
        for step in steps:
            self.assertEqual(step.status, ExecutionStepStatus.COMPLETED)

        # Verify audit trail
        audit_entries = AuditLog.objects.list_by_entity('execution', execution.id)
        self.assertGreaterEqual(audit_entries.count(), 3)

    def test_execution_flow_with_failure(self):
        """Test execution flow when a step fails."""
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.SUBMITTED
        )

        # Create steps
        step_vault = ExecutionStep.objects.create(
            execution=execution,
            step_order=1,
            step_name='Fetch credentials',
            step_type=ExecutionStepType.VAULT,
            status=ExecutionStepStatus.PENDING
        )
        step_platform = ExecutionStep.objects.create(
            execution=execution,
            step_order=2,
            step_name='Execute on platform',
            step_type=ExecutionStepType.PLATFORM,
            status=ExecutionStepStatus.PENDING
        )

        # Start execution (use state machine - Story 22.12 review fix)
        execution_service = ExecutionService()
        execution_service.update_status(execution.id, ExecutionStatus.RUNNING, str(self.user.id))

        # First step completes
        step_vault.status = ExecutionStepStatus.COMPLETED
        step_vault.completed_at = timezone.now()
        step_vault.save()

        # Second step fails
        step_platform.status = ExecutionStepStatus.FAILED
        step_platform.started_at = timezone.now()
        step_platform.completed_at = timezone.now()
        step_platform.error_message = 'Connection timeout to AAP server'
        step_platform.save()

        # Execution fails (use state machine - Story 22.12 review fix)
        execution_service.update_status(execution.id, ExecutionStatus.FAILED, str(self.user.id))

        # Verify state
        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.FAILED)

        step_platform.refresh_from_db()
        self.assertEqual(step_platform.status, ExecutionStepStatus.FAILED)
        self.assertIsNotNone(step_platform.error_message)

    def test_execution_approval_flow(self):
        """
        Test execution flow with approval for production.

        Story 22.12 review fix: Use state machine for status transitions.
        Note: Approval workflow endpoints (/approve, /reject) are not yet implemented (Story 7.4).
        This test simulates the approval by directly updating approval metadata and
        transitioning to RUNNING via update_status().
        """
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='prod',
            status=ExecutionStatus.PENDING_APPROVAL
        )

        AuditLog.objects.create_entry(
            user_id=str(self.user.id),
            action_type='EXECUTION_PENDING_APPROVAL',
            entity_type='execution',
            entity_id=execution.id,
            details={'environment': 'prod', 'requires_approval': True}
        )

        # Approver approves (simulate approval metadata update)
        execution.approved_by = self.approver
        execution.approved_at = timezone.now()
        execution.approval_comment = 'Approved for prod deployment'
        execution.save(update_fields=['approved_by', 'approved_at', 'approval_comment'])

        # Transition to RUNNING via state machine (Story 22.12 review fix)
        # In production, this would be done by POST /api/v1/executions/{id}/approve endpoint
        execution_service = ExecutionService()
        execution_service.update_status(execution.id, ExecutionStatus.RUNNING, str(self.approver.id))

        # Verify approval metadata
        execution.refresh_from_db()
        self.assertEqual(execution.approved_by_id, self.approver.id)
        self.assertIsNotNone(execution.approved_at)
        self.assertEqual(execution.approval_comment, 'Approved for prod deployment')
        self.assertEqual(execution.status, ExecutionStatus.RUNNING)

    def test_execution_rejection_flow(self):
        """
        Test execution rejection for production.

        Story 22.12 review fix: Use state machine for status transitions.
        """
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='prod',
            status=ExecutionStatus.PENDING_APPROVAL
        )

        # Approver rejects (simulate rejection metadata update)
        execution.approved_by = self.approver
        execution.approved_at = timezone.now()
        execution.approval_comment = 'Rejected - missing change window'
        execution.save(update_fields=['approved_by', 'approved_at', 'approval_comment'])

        # Transition to REJECTED via state machine (Story 22.12 review fix)
        execution_service = ExecutionService()
        execution_service.update_status(execution.id, ExecutionStatus.REJECTED, str(self.approver.id))

        # Verify rejection
        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.REJECTED)

    def test_execution_cancellation(self):
        """
        Test execution cancellation.

        Story 22.12 review fix: Use state machine for status transitions.
        """
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.RUNNING
        )

        # User cancels (use state machine - Story 22.12 review fix)
        execution_service = ExecutionService()
        execution_service.update_status(execution.id, ExecutionStatus.CANCELLED, str(self.user.id))

        # Verify cancellation
        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.CANCELLED)


@pytest.mark.django_db
@pytest.mark.integration
class TestExecutionConcurrency(TestCase):
    """Integration tests for concurrent executions."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create(username='concurrent_user', profile='DBA')
        self.integration = Integration.objects.create(
            type='aap',
            name='Concurrent AAP',
            base_url='https://aap.example.com'
        )
        self.action = Action.objects.create(
            name='Concurrent Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            integration=self.integration
        )

    def test_multiple_executions_same_action(self):
        """Test multiple concurrent executions of same action."""
        executions = []
        for i in range(5):
            exec = Execution.objects.create(
                action=self.action,
                user=self.user,
                environment='dev',
                status=ExecutionStatus.SUBMITTED
            )
            executions.append(exec)

        # Verify all executions created
        self.assertEqual(Execution.objects.filter(action=self.action).count(), 5)

        # Each should have unique ID
        ids = [e.id for e in executions]
        self.assertEqual(len(ids), len(set(ids)))

    def test_execution_isolation_per_user(self):
        """Test that executions are properly isolated per user."""
        user2 = User.objects.create(username='user2', profile='DBA')

        Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.SUBMITTED
        )
        Execution.objects.create(
            action=self.action,
            user=user2,
            environment='dev',
            status=ExecutionStatus.SUBMITTED
        )

        # Each user sees only their executions
        user1_execs = Execution.objects.list_by_user(self.user.id)
        user2_execs = Execution.objects.list_by_user(user2.id)

        self.assertEqual(user1_execs.count(), 1)
        self.assertEqual(user2_execs.count(), 1)
        self.assertNotEqual(user1_execs[0].id, user2_execs[0].id)
