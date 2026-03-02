"""
Story 24.4 (AC4, AC5, AC6): Tests for integration validation guards in execution flow.
"""

import pytest

from django.test import TestCase

from core.exceptions import BadRequestError
from core.models import AuditLog, AuditActionType
from executions.models import Execution, ExecutionStatus
from executions.dtos import ExecutionRequest
from executions.services import ExecutionService
from integrations.models import IntegrationStatus
from tests.factories import (
    UserFactory, ActionFactory, IntegrationFactory,
    IntegrationTypeCatalogueFactory, ExecutionFactory,
)


@pytest.mark.django_db
class TestExecutionServiceIntegrationValidation(TestCase):
    """Tests for Story 24.4 AC4: guard in ExecutionService.create_execution()."""

    def setUp(self):
        self.user = UserFactory()
        self.service = ExecutionService()
        IntegrationTypeCatalogueFactory(code='aap', name='AAP', is_active=True)
        IntegrationTypeCatalogueFactory(code='old_type', name='Old', is_active=False)

    def test_trigger_execution_blocks_invalid_integration(self):
        """AC4: INVALID integration → BadRequestError + audit entry."""
        integration = IntegrationFactory(
            type='unknown_type', name='Invalid Int',
            status=IntegrationStatus.INVALID,
        )
        action = ActionFactory(integration=integration)

        with pytest.raises(BadRequestError) as exc_info:
            self.service.create_execution(ExecutionRequest(
                user=self.user,
                action=action,
                environment='dev',
                correlation_id='test-corr-001',
            ))

        assert exc_info.value.code == 'INVALID_INTEGRATION'
        assert 'Invalid Int' in exc_info.value.message

        # No execution should be created
        assert Execution.objects.filter(action=action).count() == 0

        # Audit entry should exist
        audit = AuditLog.objects.filter(
            action_type=AuditActionType.EXECUTION_BLOCKED_INVALID_INTEGRATION,
            entity_id=integration.id,
        ).first()
        assert audit is not None
        details = audit.get_details()
        assert details['integration_name'] == 'Invalid Int'
        assert details['integration_status'] == IntegrationStatus.INVALID

    def test_trigger_execution_warns_deprecated_integration(self):
        """AC4: DEPRECATED integration → warning audit + execution proceeds."""
        integration = IntegrationFactory(
            type='old_type', name='Deprecated Int',
            status=IntegrationStatus.DEPRECATED,
        )
        action = ActionFactory(integration=integration)

        execution = self.service.create_execution(ExecutionRequest(
            user=self.user,
            action=action,
            environment='dev',
            correlation_id='test-corr-002',
        ))

        # Execution should be created successfully
        assert execution is not None
        assert execution.status == ExecutionStatus.SUBMITTED

        # Warning audit entry should exist
        audit = AuditLog.objects.filter(
            action_type=AuditActionType.EXECUTION_DEPRECATED_INTEGRATION_WARNING,
            entity_id=integration.id,
        ).first()
        assert audit is not None
        details = audit.get_details()
        assert details['integration_name'] == 'Deprecated Int'

    def test_trigger_execution_allows_valid_integration(self):
        """AC4: VALID integration → no warning, execution proceeds normally."""
        integration = IntegrationFactory(
            type='aap', name='Valid Int',
            status=IntegrationStatus.VALID,
        )
        action = ActionFactory(integration=integration)

        execution = self.service.create_execution(ExecutionRequest(
            user=self.user,
            action=action,
            environment='dev',
            correlation_id='test-corr-003',
        ))

        # Execution should be created
        assert execution is not None
        assert execution.status == ExecutionStatus.SUBMITTED

        # No integration-related audit entries (only EXECUTION_SUBMITTED)
        assert AuditLog.objects.filter(
            action_type=AuditActionType.EXECUTION_BLOCKED_INVALID_INTEGRATION,
        ).count() == 0
        assert AuditLog.objects.filter(
            action_type=AuditActionType.EXECUTION_DEPRECATED_INTEGRATION_WARNING,
        ).count() == 0

    def test_trigger_execution_no_integration(self):
        """AC4: Action without integration → no validation, proceeds normally."""
        action = ActionFactory(integration=None)

        execution = self.service.create_execution(ExecutionRequest(
            user=self.user,
            action=action,
            environment='dev',
        ))

        assert execution is not None
        assert execution.status == ExecutionStatus.SUBMITTED


@pytest.mark.django_db
class TestWorkflowRuntimeIntegrationValidation(TestCase):
    """Tests for Story 24.4 AC5: guard in WorkflowRuntime._execute_step()."""

    def setUp(self):
        self.user = UserFactory()
        IntegrationTypeCatalogueFactory(code='aap', name='AAP', is_active=True)
        IntegrationTypeCatalogueFactory(code='old_type', name='Old', is_active=False)

    def test_workflow_step_fails_invalid_integration(self):
        """AC5: INVALID integration → workflow step fails with explicit error."""
        integration = IntegrationFactory(
            type='unknown', name='Bad Int',
            status=IntegrationStatus.INVALID,
        )
        referenced_action = ActionFactory(
            name='Deploy AAP', integration=integration,
        )
        # Create a workflow action with execution_steps referencing the action
        workflow_action = ActionFactory(
            name='My Workflow',
            item_type='workflow',
        )
        workflow_action.execution_steps = [
            {
                'step_id': 'step-1',
                'name': 'Deploy to AAP',
                'order': 1,
                'referenced_action_id': referenced_action.id,
            }
        ]
        workflow_action.save()

        execution = ExecutionFactory(
            action=workflow_action,
            user=self.user,
            status=ExecutionStatus.SUBMITTED,
        )

        from executions.workflow_runtime import WorkflowRuntime
        runtime = WorkflowRuntime(execution)
        final_status = runtime.run()

        # Workflow should fail
        assert final_status == ExecutionStatus.FAILED

        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.FAILED

        # Audit entry
        audit = AuditLog.objects.filter(
            action_type=AuditActionType.WORKFLOW_STEP_BLOCKED_INVALID_INTEGRATION,
        ).first()
        assert audit is not None
        details = audit.get_details()
        assert details['integration_name'] == 'Bad Int'
        assert details['step_name'] == 'Deploy to AAP'

    def test_workflow_step_warns_deprecated_integration(self):
        """AC5: DEPRECATED integration → log + audit warning, execution continues."""
        integration = IntegrationFactory(
            type='old_type', name='Dep Int',
            status=IntegrationStatus.DEPRECATED,
        )
        referenced_action = ActionFactory(
            name='Deploy SN', integration=integration,
        )
        workflow_action = ActionFactory(
            name='Dep Workflow',
            item_type='workflow',
        )
        workflow_action.execution_steps = [
            {
                'step_id': 'step-1',
                'name': 'Deploy ServiceNow',
                'order': 1,
                'referenced_action_id': referenced_action.id,
            }
        ]
        workflow_action.save()

        execution = ExecutionFactory(
            action=workflow_action,
            user=self.user,
            status=ExecutionStatus.SUBMITTED,
        )

        from executions.workflow_runtime import WorkflowRuntime
        runtime = WorkflowRuntime(execution)
        final_status = runtime.run()

        # Workflow should complete (deprecated = warning only)
        assert final_status == ExecutionStatus.COMPLETED

        # Deprecated warning audit entry
        audit = AuditLog.objects.filter(
            action_type=AuditActionType.EXECUTION_DEPRECATED_INTEGRATION_WARNING,
        ).first()
        assert audit is not None
        details = audit.get_details()
        assert details['integration_name'] == 'Dep Int'
