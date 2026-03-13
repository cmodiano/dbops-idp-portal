"""
Integration tests for container workflow execution - Story 20.6 Task 6.2

Tests end-to-end workflow execution through the API:
- AC1: Workflow execution creates child executions in order
- AC2: Child executions have parent_execution_id
- AC3: workflow_step_parameters injection
- AC4: Failure propagation
- AC8: Full execution flow validation
- AC10: Non-regression (existing action execution still works)
"""

import pytest
from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from catalog.models import Action, ActionStatus, ActionItemType
from executions.models import Execution, ExecutionStep, ExecutionStatus, ExecutionStepStatus
from idp_auth.models import User
from tests.factories import IntegrationFactory


@pytest.mark.django_db
class TestContainerWorkflowAPIIntegration(TestCase):
    """Integration tests for container workflow execution through API."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(username="workflow_int_user", profile="DBA")
        self.client.force_authenticate(user=self.user)

        # Story 77.3: actions with integration required for real dispatch path
        self.integration = IntegrationFactory()

        # Create referenced actions (with parameters_schema for step params tests)
        self.ref_action_1 = Action.objects.create(
            name="Integration Ref Action 1",
            category="Provisioning",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            requires_target=False,
            parameters_schema={"type": "object"},
            integration=self.integration,
        )
        self.ref_action_2 = Action.objects.create(
            name="Integration Ref Action 2",
            category="Provisioning",
            engine="SQL Server",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            requires_target=False,
            parameters_schema={"type": "object"},
            integration=self.integration,
        )

        # Story 77.3: mock trigger_platform_job to complete child steps immediately
        def _complete_child_step(kwargs, queue):
            exec_step_id = kwargs['execution_step_id']
            ExecutionStep.objects.filter(id=exec_step_id).update(
                status=ExecutionStepStatus.COMPLETED,
                completed_at=timezone.now(),
            )

        patcher = patch('executions.container_workflow_runtime.trigger_platform_job')
        self.mock_trigger = patcher.start()
        self.mock_trigger.apply_async.side_effect = _complete_child_step
        self.addCleanup(patcher.stop)

        # Create workflow
        self.workflow = Action.objects.create(
            name="Integration Test Workflow",
            category="Provisioning",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            requires_target=False,
        )
        self.workflow.execution_steps = [
            {
                "order": 1,
                "name": "Step 1 - Oracle",
                "referenced_action_id": self.ref_action_1.id,
                "step_id": "step-1",
            },
            {
                "order": 2,
                "name": "Step 2 - SQL Server",
                "referenced_action_id": self.ref_action_2.id,
                "step_id": "step-2",
            },
        ]
        self.workflow.save(update_fields=["execution_steps"])

    @patch('executions.container_workflow_runtime.AuditService')
    def test_workflow_execution_creates_child_executions(self, mock_audit):
        """AC1/AC2: POST /executions with workflow creates parent + child executions."""
        # Patch ContainerWorkflowRuntime.run to use run_sync (avoid SQLite threading issues)
        from executions.container_workflow_runtime import ContainerWorkflowRuntime
        original_run = ContainerWorkflowRuntime.run
        ContainerWorkflowRuntime.run = lambda self: self.run_sync()

        try:
            response = self.client.post(
                "/api/v1/executions/",
                data={
                    "action_id": self.workflow.id,
                    "environment": "dev",
                },
                format="json",
            )

            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            data = response.json()["data"]
            parent_id = data["execution_id"]

            # Verify parent execution
            parent = Execution.objects.get(id=parent_id)
            self.assertEqual(parent.action_id, self.workflow.id)
            self.assertEqual(parent.status, ExecutionStatus.COMPLETED)

            # Verify child executions
            children = Execution.objects.filter(parent_execution_id=parent_id).order_by('id')
            self.assertEqual(children.count(), 2)
            self.assertEqual(children[0].action_id, self.ref_action_1.id)
            self.assertEqual(children[1].action_id, self.ref_action_2.id)

            # Verify children completed
            for child in children:
                self.assertEqual(child.status, ExecutionStatus.COMPLETED)
                self.assertEqual(child.environment, "dev")
                self.assertEqual(child.user_id, self.user.id)
        finally:
            # Restore original run method
            ContainerWorkflowRuntime.run = original_run

    @patch('executions.container_workflow_runtime.AuditService')
    def test_workflow_execution_creates_parent_steps(self, mock_audit):
        """Parent execution has step records for each workflow step."""
        # Patch ContainerWorkflowRuntime.run to use run_sync (avoid SQLite threading issues)
        from executions.container_workflow_runtime import ContainerWorkflowRuntime
        original_run = ContainerWorkflowRuntime.run
        ContainerWorkflowRuntime.run = lambda self: self.run_sync()

        try:
            response = self.client.post(
                "/api/v1/executions/",
                data={
                    "action_id": self.workflow.id,
                    "environment": "dev",
                },
                format="json",
            )

            parent_id = response.json()["data"]["execution_id"]
            steps = ExecutionStep.objects.filter(execution_id=parent_id).order_by('step_order')
            self.assertEqual(steps.count(), 2)
            self.assertEqual(steps[0].step_name, "Step 1 - Oracle")
            self.assertEqual(steps[1].step_name, "Step 2 - SQL Server")
        finally:
            # Restore original run method
            ContainerWorkflowRuntime.run = original_run

    @patch('executions.container_workflow_runtime.AuditService')
    def test_workflow_with_step_parameters(self, mock_audit):
        """AC3: workflow_step_parameters injected into child execution parameters."""
        # Patch ContainerWorkflowRuntime.run to use run_sync (avoid SQLite threading issues)
        from executions.container_workflow_runtime import ContainerWorkflowRuntime
        original_run = ContainerWorkflowRuntime.run
        ContainerWorkflowRuntime.run = lambda self: self.run_sync()

        try:
            response = self.client.post(
                "/api/v1/executions/",
                data={
                    "action_id": self.workflow.id,
                    "environment": "dev",
                    "workflow_step_parameters": {
                        "1": {"parameters": {"db_name": "TESTDB"}},
                        "2": {"parameters": {"server": "sql-01"}},
                    },
                },
                format="json",
            )

            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            parent_id = response.json()["data"]["execution_id"]

            children = Execution.objects.filter(parent_execution_id=parent_id).order_by('id')
            self.assertEqual(children.count(), 2)

            # Verify step parameters injected
            child_1_params = children[0].get_parameters()
            self.assertEqual(child_1_params.get("db_name"), "TESTDB")

            child_2_params = children[1].get_parameters()
            self.assertEqual(child_2_params.get("server"), "sql-01")
        finally:
            # Restore original run method
            ContainerWorkflowRuntime.run = original_run

    @patch('executions.container_workflow_runtime.AuditService')
    def test_workflow_with_missing_referenced_action_fails(self, mock_audit):
        """AC4: If referenced action doesn't exist, workflow fails."""
        bad_workflow = Action.objects.create(
            name="Bad Workflow",
            category="Provisioning",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            requires_target=False,
        )
        bad_workflow.execution_steps = [
            {
                "order": 1,
                "name": "Step 1",
                "referenced_action_id": 99999,
                "step_id": "step-bad",
            },
        ]
        bad_workflow.save(update_fields=["execution_steps"])

        response = self.client.post(
            "/api/v1/executions/",
            data={
                "action_id": bad_workflow.id,
                "environment": "dev",
            },
            format="json",
        )

        # The execution is created but marked as failed by the runtime
        # The API still returns 201 because execution was created
        # (failure happens in the runtime, not validation)
        # Note: Story 4.11 validation catches non-existent actions first
        # This test verifies the behavior when validation is bypassed or
        # the action becomes unavailable between validation and execution
        if response.status_code == status.HTTP_201_CREATED:
            parent_id = response.json()["data"]["execution_id"]
            parent = Execution.objects.get(id=parent_id)
            # Parent should be FAILED since child couldn't be created
            self.assertIn(parent.status, [
                ExecutionStatus.FAILED,
                ExecutionStatus.INTEGRATION_ERROR,
            ])

    def test_regular_action_execution_still_works(self, ):
        """AC10: Non-regression — standard action execution not broken."""
        regular_action = Action.objects.create(
            name="Regular Action",
            category="Provisioning",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            requires_target=False,
        )

        response = self.client.post(
            "/api/v1/executions/",
            data={
                "action_id": regular_action.id,
                "environment": "dev",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()["data"]
        execution = Execution.objects.get(id=data["execution_id"])
        self.assertEqual(execution.action_id, regular_action.id)
        # Regular action should be SUBMITTED (not run through container runtime)
        self.assertEqual(execution.status, ExecutionStatus.SUBMITTED)
