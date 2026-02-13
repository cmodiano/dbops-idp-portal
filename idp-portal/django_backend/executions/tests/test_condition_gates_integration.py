"""
Integration tests for condition gates — Story 25.2

Tests:
- AC2: gate_conditions schema support in execution_steps JSON
- AC3: Full workflow execution with gate_conditions creates WAITING step
- AC4: Waiting context accessible after execution
- AC5: API validation of gate_conditions
"""

import json
import pytest
from django.utils import timezone

from executions.models import Execution, ExecutionStep, ExecutionStatus, ExecutionStepStatus
from executions.workflow_runtime import WorkflowRuntime
from catalog.models import Action, ActionStatus, ActionItemType
from catalog.services import CatalogService
from tests.factories import UserFactory, ActionFactory, IntegrationFactory


@pytest.mark.django_db
class TestGateConditionsIntegrationFlow:
    """Integration tests for the full gate_conditions flow."""

    def setup_method(self):
        self.user = UserFactory(username="integration_gate_user")

    def test_full_flow_action_with_gate_conditions_creates_waiting_step(self):
        """
        Integration: create action with gate_conditions → execute → verify WAITING step.
        """
        # 1. Create referenced action
        ref_action = ActionFactory(
            name="Oracle Patch",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            integration=IntegrationFactory(),
        )

        # 2. Create workflow with gate_conditions
        workflow_action = ActionFactory(
            name="Deploy Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )
        workflow_action.execution_steps = [
            {
                'order': 1,
                'step_id': 'deploy',
                'name': 'Deploy patch Oracle',
                'type': 'platform',
                'referenced_action_id': ref_action.id,
                'gate_conditions': [
                    {
                        'type': 'maintenance_window',
                        'description': 'Attendre la plage de maintenance',
                        'timeout_hours': 72,
                        'on_timeout': 'FAIL',
                    }
                ],
            }
        ]
        workflow_action.save()

        # 3. Create execution
        execution = Execution.objects.create(
            action=workflow_action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.SUBMITTED,
        )

        # 4. Run workflow
        runtime = WorkflowRuntime(execution)
        final_status = runtime.run()

        # 5. Verify workflow stays RUNNING
        assert final_status == ExecutionStatus.RUNNING

        # 6. Verify ExecutionStep is WAITING
        step = ExecutionStep.objects.get(execution=execution, step_order=1)
        assert step.status == 'WAITING'

        # 7. Verify output context
        output = step.get_output()
        assert output is not None
        assert output['waiting_since'] is not None
        assert len(output['gate_conditions']) == 1
        assert output['gate_conditions'][0]['type'] == 'maintenance_window'
        assert output['gate_conditions'][0]['timeout_hours'] == 72
        assert output['gate_conditions'][0]['on_timeout'] == 'FAIL'
        assert len(output['gate_status']) == 1
        assert output['gate_status'][0]['satisfied'] is False

    def test_mixed_steps_normal_then_waiting(self):
        """
        Integration: workflow with normal step followed by gated step.
        First step completes, second step goes to WAITING.
        """
        ref_action1 = ActionFactory(
            name="Prepare",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            integration=IntegrationFactory(),
        )
        ref_action2 = ActionFactory(
            name="Deploy Gated",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            integration=IntegrationFactory(),
        )

        workflow_action = ActionFactory(
            name="Mixed Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )
        workflow_action.execution_steps = [
            {
                'order': 1,
                'step_id': 'prepare',
                'name': 'Prepare deployment',
                'type': 'platform',
                'referenced_action_id': ref_action1.id,
                'on_success_step_id': 'deploy',
            },
            {
                'order': 2,
                'step_id': 'deploy',
                'name': 'Deploy with maintenance gate',
                'type': 'platform',
                'referenced_action_id': ref_action2.id,
                'gate_conditions': [
                    {'type': 'maintenance_window', 'timeout_hours': 48, 'on_timeout': 'FAIL'},
                    {'type': 'approval_granted', 'timeout_hours': 24, 'on_timeout': 'FAIL'},
                ],
            },
        ]
        workflow_action.save()

        execution = Execution.objects.create(
            action=workflow_action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.SUBMITTED,
        )

        runtime = WorkflowRuntime(execution)
        final_status = runtime.run()

        assert final_status == ExecutionStatus.RUNNING

        steps = ExecutionStep.objects.filter(execution=execution).order_by('step_order')
        assert steps.count() == 2
        assert steps[0].status == 'COMPLETED'
        assert steps[1].status == 'WAITING'

        # Verify both gate conditions are tracked
        output = steps[1].get_output()
        assert len(output['gate_status']) == 2
        assert output['gate_status'][0]['type'] == 'maintenance_window'
        assert output['gate_status'][1]['type'] == 'approval_granted'

    def test_execution_stays_running_after_waiting(self):
        """
        Integration: Execution.completed_at is NOT set when workflow pauses for WAITING.
        """
        ref_action = ActionFactory(
            name="Gated Action",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            integration=IntegrationFactory(),
        )

        workflow_action = ActionFactory(
            name="Wait Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )
        workflow_action.execution_steps = [
            {
                'order': 1,
                'step_id': 'gated',
                'name': 'Gated step',
                'type': 'platform',
                'referenced_action_id': ref_action.id,
                'gate_conditions': [
                    {'type': 'time_window', 'timeout_hours': 24, 'on_timeout': 'SKIP'}
                ],
            }
        ]
        workflow_action.save()

        execution = Execution.objects.create(
            action=workflow_action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.SUBMITTED,
        )

        runtime = WorkflowRuntime(execution)
        runtime.run()

        execution.refresh_from_db()
        assert execution.status == 'RUNNING'
        assert execution.started_at is not None
        # AC4: completed_at should not be set because the workflow is paused
        assert execution.completed_at is None


@pytest.mark.django_db
class TestGateConditionsValidationIntegration:
    """Integration tests for gate_conditions validation in catalog service."""

    def setup_method(self):
        self.user = UserFactory(username="validation_gate_user")
        self.service = CatalogService()

    def test_update_execution_steps_valid_gate_conditions(self):
        """Valid gate_conditions in execution steps pass validation."""
        action = ActionFactory(
            name="Test Action Valid",
            status=ActionStatus.DRAFT,
            item_type=ActionItemType.WORKFLOW,
        )

        steps = [
            {
                'order': 1,
                'step_id': 'deploy',
                'name': 'Deploy',
                'referenced_action_id': 999,
                'gate_conditions': [
                    {'type': 'maintenance_window', 'timeout_hours': 48, 'on_timeout': 'FAIL'}
                ],
            }
        ]

        result = self.service.update_execution_steps(
            action_id=action.id,
            steps=steps,
            user=self.user,
        )

        assert result is not None
        assert result.execution_steps == steps

    def test_update_execution_steps_invalid_gate_conditions_type(self):
        """Invalid gate_conditions type raises ValidationError."""
        from rest_framework.exceptions import ValidationError

        action = ActionFactory(
            name="Test Action Invalid",
            status=ActionStatus.DRAFT,
            item_type=ActionItemType.WORKFLOW,
        )

        steps = [
            {
                'order': 1,
                'step_id': 'deploy',
                'name': 'Deploy',
                'referenced_action_id': 999,
                'gate_conditions': [
                    {'type': 'unknown_type'}
                ],
            }
        ]

        with pytest.raises(ValidationError, match="'type' must be one of"):
            self.service.update_execution_steps(
                action_id=action.id,
                steps=steps,
                user=self.user,
            )

    def test_update_execution_steps_invalid_timeout(self):
        """Invalid timeout_hours raises ValidationError."""
        from rest_framework.exceptions import ValidationError

        action = ActionFactory(
            name="Test Action Timeout",
            status=ActionStatus.DRAFT,
            item_type=ActionItemType.WORKFLOW,
        )

        steps = [
            {
                'order': 1,
                'step_id': 'deploy',
                'name': 'Deploy',
                'referenced_action_id': 999,
                'gate_conditions': [
                    {'type': 'maintenance_window', 'timeout_hours': -5}
                ],
            }
        ]

        with pytest.raises(ValidationError, match="'timeout_hours' must be a positive number"):
            self.service.update_execution_steps(
                action_id=action.id,
                steps=steps,
                user=self.user,
            )

    def test_update_execution_steps_no_gate_conditions_unchanged(self):
        """Steps without gate_conditions work normally."""
        action = ActionFactory(
            name="Test Action No Gates",
            status=ActionStatus.DRAFT,
            item_type=ActionItemType.WORKFLOW,
        )

        steps = [
            {
                'order': 1,
                'step_id': 'deploy',
                'name': 'Deploy',
                'referenced_action_id': 999,
            }
        ]

        result = self.service.update_execution_steps(
            action_id=action.id,
            steps=steps,
            user=self.user,
        )

        assert result is not None
        assert result.execution_steps == steps
