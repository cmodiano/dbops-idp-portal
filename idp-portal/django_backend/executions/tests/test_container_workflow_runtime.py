"""
Unit and integration tests for ContainerWorkflowRuntime - Story 20.6 Task 3

Tests:
- AC1: Sequential execution of referenced actions via child executions
- AC2: Child executions with parent_execution_id for traceability
- AC3: workflow_step_parameters injection into child execution parameters
- AC4: Failure/cancellation propagation
- Subtask 3.1: Detection of item_type == 'workflow' at execution start
- Subtask 3.4: Status management (RUNNING, COMPLETED, FAILED, CANCELLED)
- Subtask 3.5: Integration with existing WorkflowRuntime (no breaking)
"""

import pytest
from unittest.mock import patch


from executions.container_workflow_runtime import ContainerWorkflowRuntime
from executions.models import (
    Execution, ExecutionStep, ExecutionStatus, ExecutionStepStatus,
)
from catalog.models import ActionStatus, ActionItemType
from tests.factories import UserFactory, ActionFactory


def _make_workflow_steps(referenced_actions):
    """Helper: build workflow execution_steps as Python list (OracleJSONField handles serialization)."""
    return [
        {
            "order": i + 1,
            "name": f"Step {i + 1}",
            "referenced_action_id": action_id,
            "step_id": f"step-{i + 1}",
        }
        for i, action_id in enumerate(referenced_actions)
    ]


@pytest.mark.django_db
class TestContainerWorkflowRuntimeBasic:
    """Test basic container workflow execution (AC1, AC2)."""

    def setup_method(self):
        """Create test data: user, referenced actions, workflow action, execution."""
        self.user = UserFactory(username="workflow_test_user")

        # Create referenced actions (published)
        self.action_a = ActionFactory(
            name="Action A",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            created_by=self.user,
        )
        self.action_b = ActionFactory(
            name="Action B",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            created_by=self.user,
        )
        self.action_c = ActionFactory(
            name="Action C",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            created_by=self.user,
        )

        # Create workflow action referencing A, B, C
        self.workflow_action = ActionFactory(
            name="Test Container Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_workflow_steps([
                self.action_a.id, self.action_b.id, self.action_c.id,
            ]),
            created_by=self.user,
        )

    def _create_execution(self, action=None, parameters=None):
        """Helper: create execution for the workflow."""
        action = action or self.workflow_action
        execution = Execution.objects.create(
            action=action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.SUBMITTED,
        )
        if parameters:
            execution.set_parameters(parameters)
            execution.save()
        return execution

    @patch('executions.container_workflow_runtime.AuditService')
    def test_workflow_executes_all_steps_in_order(self, mock_audit):
        """AC1: Each step triggers execution of referenced action in order."""
        execution = self._create_execution()
        runtime = ContainerWorkflowRuntime(execution)
        result = runtime.run_sync()

        assert result == ExecutionStatus.COMPLETED

        # Verify 3 child executions were created
        assert len(runtime.child_executions) == 3

        # Verify child executions reference correct actions in order
        assert runtime.child_executions[0].action_id == self.action_a.id
        assert runtime.child_executions[1].action_id == self.action_b.id
        assert runtime.child_executions[2].action_id == self.action_c.id

    @patch('executions.container_workflow_runtime.AuditService')
    def test_child_executions_have_parent_id(self, mock_audit):
        """AC2: Each child execution has parent_execution_id set."""
        execution = self._create_execution()
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run_sync()

        for child in runtime.child_executions:
            child.refresh_from_db()
            assert child.parent_execution_id == execution.id

    @patch('executions.container_workflow_runtime.AuditService')
    def test_child_executions_inherit_environment(self, mock_audit):
        """Child executions use same environment as parent."""
        execution = self._create_execution()
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run_sync()

        for child in runtime.child_executions:
            assert child.environment == 'dev'

    @patch('executions.container_workflow_runtime.AuditService')
    def test_child_executions_inherit_user(self, mock_audit):
        """Child executions use same user as parent."""
        execution = self._create_execution()
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run_sync()

        for child in runtime.child_executions:
            assert child.user_id == self.user.id

    @patch('executions.container_workflow_runtime.AuditService')
    def test_parent_status_completed_on_success(self, mock_audit):
        """AC4: Parent workflow status is COMPLETED when all steps succeed."""
        execution = self._create_execution()
        runtime = ContainerWorkflowRuntime(execution)
        result = runtime.run_sync()

        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.COMPLETED
        assert execution.completed_at is not None
        assert execution.started_at is not None
        assert result == ExecutionStatus.COMPLETED

    @patch('executions.container_workflow_runtime.AuditService')
    def test_parent_execution_steps_created(self, mock_audit):
        """Parent execution has step records tracking each child."""
        execution = self._create_execution()
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run_sync()

        parent_steps = ExecutionStep.objects.filter(execution=execution).order_by('step_order')
        assert parent_steps.count() == 3

        for step in parent_steps:
            assert step.status == ExecutionStepStatus.COMPLETED
            assert step.completed_at is not None
            # platform_job_id links to child execution
            assert step.platform_job_id is not None

    @patch('executions.container_workflow_runtime.AuditService')
    def test_empty_workflow_fails(self, mock_audit):
        """Workflow with no steps fails immediately."""
        workflow = ActionFactory(
            name="Empty Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[],
            created_by=self.user,
        )
        execution = self._create_execution(action=workflow)
        runtime = ContainerWorkflowRuntime(execution)
        result = runtime.run_sync()

        assert result == ExecutionStatus.FAILED
        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.FAILED
        assert "no steps" in execution.error_message.lower()


@pytest.mark.django_db
class TestContainerWorkflowParameterInjection:
    """Test workflow_step_parameters injection (AC3)."""

    def setup_method(self):
        self.user = UserFactory(username="param_test_user")
        self.action_a = ActionFactory(
            name="Param Action A",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            created_by=self.user,
            parameters_schema=None,
        )
        self.action_b = ActionFactory(
            name="Param Action B",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            created_by=self.user,
            parameters_schema=None,
        )
        self.workflow_action = ActionFactory(
            name="Param Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_workflow_steps([
                self.action_a.id, self.action_b.id,
            ]),
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_step_parameters_injected_into_child(self, mock_audit):
        """AC3: workflow_step_parameters are merged into child execution params."""
        parameters = {
            "global_param": "value",
            "workflow_step_parameters": {
                "1": {"parameters": {"host": "db-01", "port": 1521}},
                "2": {"parameters": {"host": "db-02", "port": 5432}},
            },
        }
        execution = Execution.objects.create(
            action=self.workflow_action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.SUBMITTED,
        )
        execution.set_parameters(parameters)
        execution.save()

        runtime = ContainerWorkflowRuntime(execution)
        runtime.run_sync()

        # Child 1 should have step-1 params merged with global
        child_1 = runtime.child_executions[0]
        child_1_params = child_1.get_parameters()
        assert child_1_params["host"] == "db-01"
        assert child_1_params["port"] == 1521
        assert child_1_params["global_param"] == "value"

        # Child 2 should have step-2 params merged with global
        child_2 = runtime.child_executions[1]
        child_2_params = child_2.get_parameters()
        assert child_2_params["host"] == "db-02"
        assert child_2_params["port"] == 5432
        assert child_2_params["global_param"] == "value"

    @patch('executions.container_workflow_runtime.AuditService')
    def test_step_params_override_global(self, mock_audit):
        """AC3: Step parameters override global parameters with same key."""
        parameters = {
            "host": "global-host",
            "workflow_step_parameters": {
                "1": {"parameters": {"host": "step-host"}},
            },
        }
        execution = Execution.objects.create(
            action=self.workflow_action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.SUBMITTED,
        )
        execution.set_parameters(parameters)
        execution.save()

        runtime = ContainerWorkflowRuntime(execution)
        runtime.run_sync()

        child_1_params = runtime.child_executions[0].get_parameters()
        assert child_1_params["host"] == "step-host"  # step overrides global

    @patch('executions.container_workflow_runtime.AuditService')
    def test_no_step_params_uses_global_only(self, mock_audit):
        """Without workflow_step_parameters, children get global params."""
        parameters = {"global_key": "global_value"}
        execution = Execution.objects.create(
            action=self.workflow_action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.SUBMITTED,
        )
        execution.set_parameters(parameters)
        execution.save()

        runtime = ContainerWorkflowRuntime(execution)
        runtime.run_sync()

        child_1_params = runtime.child_executions[0].get_parameters()
        assert child_1_params["global_key"] == "global_value"

    @patch('executions.container_workflow_runtime.AuditService')
    def test_env_config_excluded_from_child_params(self, mock_audit):
        """Internal _env_config key is not passed to children."""
        parameters = {
            "global_key": "value",
            "_env_config": {"change_required": True},
        }
        execution = Execution.objects.create(
            action=self.workflow_action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.SUBMITTED,
        )
        execution.set_parameters(parameters)
        execution.save()

        runtime = ContainerWorkflowRuntime(execution)
        runtime.run_sync()

        child_params = runtime.child_executions[0].get_parameters()
        assert "_env_config" not in child_params


@pytest.mark.django_db
class TestContainerWorkflowFailurePropagation:
    """Test failure and cancellation propagation (AC4)."""

    def setup_method(self):
        self.user = UserFactory(username="failure_test_user")
        self.action_a = ActionFactory(
            name="OK Action",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            created_by=self.user,
        )
        self.action_b = ActionFactory(
            name="OK Action 2",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_missing_referenced_action_fails_workflow(self, mock_audit):
        """AC4: If referenced action doesn't exist, workflow fails."""
        workflow = ActionFactory(
            name="Bad Ref Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[
                {"order": 1, "name": "Step 1", "referenced_action_id": self.action_a.id, "step_id": "s1"},
                {"order": 2, "name": "Step 2", "referenced_action_id": 99999, "step_id": "s2"},  # non-existent
            ],
            created_by=self.user,
        )
        execution = Execution.objects.create(
            action=workflow, user=self.user,
            environment='dev', status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        result = runtime.run_sync()

        assert result == ExecutionStatus.FAILED
        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.FAILED

        # First child should have succeeded, second should not exist
        assert len(runtime.child_executions) == 1  # only first step created child

    @patch('executions.container_workflow_runtime.AuditService')
    def test_unpublished_referenced_action_fails_workflow(self, mock_audit):
        """AC4: If referenced action is not published, workflow fails."""
        draft_action = ActionFactory(
            name="Draft Action",
            status=ActionStatus.DRAFT,
            item_type=ActionItemType.ACTION,
            created_by=self.user,
        )
        workflow = ActionFactory(
            name="Draft Ref Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_workflow_steps([draft_action.id]),
            created_by=self.user,
        )
        execution = Execution.objects.create(
            action=workflow, user=self.user,
            environment='dev', status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        result = runtime.run_sync()

        assert result == ExecutionStatus.FAILED

    @patch('executions.container_workflow_runtime.AuditService')
    def test_missing_referenced_action_id_fails_step(self, mock_audit):
        """Step without referenced_action_id fails the workflow."""
        workflow = ActionFactory(
            name="No Ref ID Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[
                {"order": 1, "name": "Step 1", "step_id": "s1"},  # no referenced_action_id
            ],
            created_by=self.user,
        )
        execution = Execution.objects.create(
            action=workflow, user=self.user,
            environment='dev', status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        result = runtime.run_sync()

        assert result == ExecutionStatus.FAILED

    @patch('executions.container_workflow_runtime.is_cancelled', return_value=True)
    @patch('executions.container_workflow_runtime.AuditService')
    def test_cancellation_detected_before_first_step(self, mock_audit, mock_cancelled):
        """AC4: If parent is cancelled before execution, workflow is cancelled."""
        workflow = ActionFactory(
            name="Cancel Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_workflow_steps([self.action_a.id]),
            created_by=self.user,
        )
        execution = Execution.objects.create(
            action=workflow, user=self.user,
            environment='dev', status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        result = runtime.run_sync()

        assert result == ExecutionStatus.CANCELLED
        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.CANCELLED

    @patch('executions.container_workflow_runtime.AuditService')
    def test_subsequent_steps_not_executed_after_failure(self, mock_audit):
        """AC4: Steps after a failed step are not executed."""
        workflow = ActionFactory(
            name="Fail Early Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[
                {"order": 1, "name": "Step 1", "referenced_action_id": 99999, "step_id": "s1"},  # will fail
                {"order": 2, "name": "Step 2", "referenced_action_id": self.action_a.id, "step_id": "s2"},
            ],
            created_by=self.user,
        )
        execution = Execution.objects.create(
            action=workflow, user=self.user,
            environment='dev', status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        result = runtime.run_sync()

        assert result == ExecutionStatus.FAILED
        # No child executions should have been created (first step failed before child creation)
        assert len(runtime.child_executions) == 0
        # Only 1 parent step should exist (the failed one)
        assert ExecutionStep.objects.filter(execution=execution).count() == 1


@pytest.mark.django_db
class TestContainerWorkflowStatusManagement:
    """Test status transitions and management (Subtask 3.4)."""

    def setup_method(self):
        self.user = UserFactory(username="status_test_user")
        self.action_a = ActionFactory(
            name="Status Action A",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_parent_transitions_to_running_then_completed(self, mock_audit):
        """Parent execution goes SUBMITTED -> RUNNING -> COMPLETED."""
        workflow = ActionFactory(
            name="Status Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_workflow_steps([self.action_a.id]),
            created_by=self.user,
        )
        execution = Execution.objects.create(
            action=workflow, user=self.user,
            environment='dev', status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run_sync()

        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.COMPLETED
        assert execution.started_at is not None
        assert execution.completed_at is not None

    @patch('executions.container_workflow_runtime.AuditService')
    def test_child_executions_completed_status(self, mock_audit):
        """Child executions are marked COMPLETED after successful execution."""
        workflow = ActionFactory(
            name="Child Status Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_workflow_steps([self.action_a.id]),
            created_by=self.user,
        )
        execution = Execution.objects.create(
            action=workflow, user=self.user,
            environment='dev', status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run_sync()

        child = runtime.child_executions[0]
        child.refresh_from_db()
        assert child.status == ExecutionStatus.COMPLETED
        assert child.started_at is not None
        assert child.completed_at is not None

    @patch('executions.container_workflow_runtime.AuditService')
    def test_audit_entry_on_completion(self, mock_audit):
        """Audit trail entry created on workflow completion."""
        workflow = ActionFactory(
            name="Audit Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_workflow_steps([self.action_a.id]),
            created_by=self.user,
        )
        execution = Execution.objects.create(
            action=workflow, user=self.user,
            environment='dev', status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run_sync()

        # Verify audit was called (2 calls: child creation + parent completion)
        assert mock_audit.create_entry.call_count >= 1

        # Check the final completion audit call
        last_call = mock_audit.create_entry.call_args_list[-1]
        assert last_call.kwargs.get('entity_id') == execution.id
        details = last_call.kwargs.get('details', {})
        assert details.get('workflow_type') == 'container'
        assert details.get('final_status') == ExecutionStatus.COMPLETED


@pytest.mark.django_db
class TestContainerWorkflowIntegration:
    """Integration tests: verify container workflow doesn't break existing runtime (Subtask 3.5)."""

    def setup_method(self):
        self.user = UserFactory(username="integration_test_user")

    @patch('executions.container_workflow_runtime.AuditService')
    def test_single_step_workflow(self, mock_audit):
        """Workflow with single referenced action completes."""
        action = ActionFactory(
            name="Single Ref Action",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            created_by=self.user,
        )
        workflow = ActionFactory(
            name="Single Step Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_workflow_steps([action.id]),
            created_by=self.user,
        )
        execution = Execution.objects.create(
            action=workflow, user=self.user,
            environment='dev', status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        result = runtime.run_sync()

        assert result == ExecutionStatus.COMPLETED
        assert len(runtime.child_executions) == 1

    @patch('executions.container_workflow_runtime.AuditService')
    def test_step_output_contains_child_info(self, mock_audit):
        """Parent step output contains child execution details."""
        action = ActionFactory(
            name="Output Ref Action",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            created_by=self.user,
        )
        workflow = ActionFactory(
            name="Output Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_workflow_steps([action.id]),
            created_by=self.user,
        )
        execution = Execution.objects.create(
            action=workflow, user=self.user,
            environment='dev', status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run_sync()

        parent_step = ExecutionStep.objects.get(execution=execution, step_order=1)
        output = parent_step.get_output()
        assert output is not None
        assert output['child_execution_id'] == runtime.child_executions[0].id
        assert output['referenced_action_id'] == action.id
        assert output['referenced_action_name'] == action.name

    @patch('executions.container_workflow_runtime.AuditService')
    def test_invalid_execution_steps_format_fails(self, mock_audit):
        """Workflow with non-list execution_steps (dict) fails gracefully."""
        workflow = ActionFactory(
            name="Invalid Steps Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps={"not": "a list"},  # dict instead of list
            created_by=self.user,
        )
        execution = Execution.objects.create(
            action=workflow, user=self.user,
            environment='dev', status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        result = runtime.run_sync()

        assert result == ExecutionStatus.FAILED
