"""
Tests Story 77.3 — Exécuter les steps platform via le chemin réel de dispatch

AC1 : action avec intégration → trigger_platform_job.apply_async appelé, child COMPLETED
AC2 : action sans intégration → child FAILED, apply_async non appelé
AC3 : échec plateforme → child FAILED → parent step FAILED
AC4 : branche placeholder supprimée (item_type='action' ne marque plus COMPLETED silencieusement)
Rétrocompatibilité : item_type='workflow' continue via ContainerWorkflowRuntime.run_sync()
"""
import pytest
from unittest.mock import patch, MagicMock
from django.test import override_settings
from django.utils import timezone

from executions.models import (
    Execution,
    ExecutionStep,
    ExecutionStatus,
    ExecutionStepStatus,
    ExecutionStepType,
)
from executions.container_workflow_runtime import (
    ContainerWorkflowRuntime,
)
from catalog.models import ActionStatus, ActionItemType
from tests.factories import UserFactory, ActionFactory, IntegrationFactory

TEST_ENVIRONMENT = 'developpement'


def _make_platform_step_config(ref_action_id, step_id='plat-1', **kwargs):
    """Build a platform step config referencing a given action."""
    step = {
        'order': 1,
        'name': 'Platform Step',
        'step_id': step_id,
        'referenced_action_id': ref_action_id,
    }
    step.update(kwargs)
    return step


# ---------------------------------------------------------------------------
# AC1 — Action avec intégration → dispatch réel, child COMPLETED
# ---------------------------------------------------------------------------

class TestAC1RealDispatchWithIntegration:
    """AC1 : trigger_platform_job.apply_async est appelé avec les bons kwargs."""

    @pytest.mark.django_db
    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.container_workflow_runtime.trigger_platform_job')
    @patch('executions.container_workflow_runtime.get_platform_queue', return_value='default')
    def test_trigger_apply_async_called_with_correct_kwargs(
        self, mock_queue, mock_trigger, mock_audit,
    ):
        """AC1 : apply_async appelé avec execution_step_id, execution_id, integration_id, trigger_kwargs."""
        user = UserFactory()
        integration = IntegrationFactory()
        ref_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            integration=integration,
            created_by=user,
        )
        workflow_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[_make_platform_step_config(ref_action.id)],
            created_by=user,
        )
        execution = Execution.objects.create(
            action=workflow_action,
            user=user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )

        def _trigger_side_effect(kwargs, queue):
            """Simule le job plateforme : marque le child step COMPLETED immédiatement."""
            exec_step_id = kwargs['execution_step_id']
            ExecutionStep.objects.filter(id=exec_step_id).update(
                status=ExecutionStepStatus.COMPLETED,
                completed_at=timezone.now(),
            )

        mock_trigger.apply_async.side_effect = _trigger_side_effect

        with override_settings(SIMULATE_EXECUTION_DEV=False):
            runtime = ContainerWorkflowRuntime(execution)
            runtime.run_sync()

        assert mock_trigger.apply_async.called, "trigger_platform_job.apply_async doit être appelé"
        call_kwargs = mock_trigger.apply_async.call_args[1]
        inner = call_kwargs['kwargs']
        assert 'execution_step_id' in inner
        assert inner['execution_id'] == Execution.objects.filter(
            parent_execution_id=execution.id
        ).first().id
        assert inner['integration_id'] == integration.id
        assert 'trigger_kwargs' in inner
        assert call_kwargs['queue'] == 'default'

    @pytest.mark.django_db
    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.container_workflow_runtime.trigger_platform_job')
    @patch('executions.container_workflow_runtime.get_platform_queue', return_value='default')
    def test_child_execution_completed_when_step_completed(
        self, mock_queue, mock_trigger, mock_audit,
    ):
        """AC1 : le child execution atteint COMPLETED via le résultat réel (pas placeholder)."""
        user = UserFactory()
        integration = IntegrationFactory()
        ref_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            integration=integration,
            created_by=user,
        )
        workflow_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[_make_platform_step_config(ref_action.id)],
            created_by=user,
        )
        execution = Execution.objects.create(
            action=workflow_action,
            user=user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )

        def _trigger_side_effect(kwargs, queue):
            exec_step_id = kwargs['execution_step_id']
            ExecutionStep.objects.filter(id=exec_step_id).update(
                status=ExecutionStepStatus.COMPLETED,
                completed_at=timezone.now(),
            )

        mock_trigger.apply_async.side_effect = _trigger_side_effect

        with override_settings(SIMULATE_EXECUTION_DEV=False):
            runtime = ContainerWorkflowRuntime(execution)
            runtime.run_sync()

        child = Execution.objects.filter(parent_execution_id=execution.id).first()
        assert child is not None
        assert child.status == ExecutionStatus.COMPLETED

        # L'exécution parent doit aussi être COMPLETED
        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.COMPLETED

    @pytest.mark.django_db
    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.container_workflow_runtime.trigger_platform_job')
    @patch('executions.container_workflow_runtime.get_platform_queue', return_value='default')
    def test_trigger_kwargs_includes_correlation_id(
        self, mock_queue, mock_trigger, mock_audit,
    ):
        """AC1 : trigger_kwargs contient le correlation_id."""
        user = UserFactory()
        integration = IntegrationFactory()
        ref_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            integration=integration,
            created_by=user,
        )
        workflow_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[_make_platform_step_config(ref_action.id)],
            created_by=user,
        )
        execution = Execution.objects.create(
            action=workflow_action,
            user=user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )

        def _trigger_side_effect(kwargs, queue):
            exec_step_id = kwargs['execution_step_id']
            ExecutionStep.objects.filter(id=exec_step_id).update(
                status=ExecutionStepStatus.COMPLETED,
                completed_at=timezone.now(),
            )

        mock_trigger.apply_async.side_effect = _trigger_side_effect

        with override_settings(SIMULATE_EXECUTION_DEV=False):
            runtime = ContainerWorkflowRuntime(execution)
            runtime.run_sync()

        inner_kwargs = mock_trigger.apply_async.call_args[1]['kwargs']
        trigger_kwargs = inner_kwargs['trigger_kwargs']
        assert 'correlation_id' in trigger_kwargs


# ---------------------------------------------------------------------------
# AC2 — Action sans intégration → child FAILED, apply_async non appelé
# ---------------------------------------------------------------------------

class TestAC2NoIntegrationFails:
    """AC2 : action sans intégration → child FAILED explicitement, apply_async non appelé."""

    @pytest.mark.django_db
    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.container_workflow_runtime.trigger_platform_job')
    @patch('executions.container_workflow_runtime.get_platform_queue', return_value='default')
    def test_child_failed_with_explicit_message(self, mock_queue, mock_trigger, mock_audit):
        """AC2 : child execution FAILED avec message 'Action has no integration configured'."""
        user = UserFactory()
        # Action sans intégration
        ref_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            integration=None,
            created_by=user,
        )
        workflow_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[_make_platform_step_config(ref_action.id)],
            created_by=user,
        )
        execution = Execution.objects.create(
            action=workflow_action,
            user=user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )

        with override_settings(SIMULATE_EXECUTION_DEV=False):
            runtime = ContainerWorkflowRuntime(execution)
            runtime.run_sync()

        child = Execution.objects.filter(parent_execution_id=execution.id).first()
        assert child is not None
        assert child.status == ExecutionStatus.FAILED
        child.refresh_from_db()
        assert child.error_message == "Action has no integration configured"

    @pytest.mark.django_db
    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.container_workflow_runtime.trigger_platform_job')
    @patch('executions.container_workflow_runtime.get_platform_queue', return_value='default')
    def test_apply_async_not_called_without_integration(self, mock_queue, mock_trigger, mock_audit):
        """AC2 : apply_async n'est pas appelé quand pas d'intégration."""
        user = UserFactory()
        ref_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            integration=None,
            created_by=user,
        )
        workflow_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[_make_platform_step_config(ref_action.id)],
            created_by=user,
        )
        execution = Execution.objects.create(
            action=workflow_action,
            user=user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )

        with override_settings(SIMULATE_EXECUTION_DEV=False):
            runtime = ContainerWorkflowRuntime(execution)
            runtime.run_sync()

        assert not mock_trigger.apply_async.called, "apply_async ne doit pas être appelé sans intégration"

    @pytest.mark.django_db
    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.container_workflow_runtime.trigger_platform_job')
    @patch('executions.container_workflow_runtime.get_platform_queue', return_value='default')
    def test_parent_step_failed_without_integration(self, mock_queue, mock_trigger, mock_audit):
        """AC2 : le parent ExecutionStep est FAILED quand pas d'intégration."""
        user = UserFactory()
        ref_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            integration=None,
            created_by=user,
        )
        workflow_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[_make_platform_step_config(ref_action.id)],
            created_by=user,
        )
        execution = Execution.objects.create(
            action=workflow_action,
            user=user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )

        with override_settings(SIMULATE_EXECUTION_DEV=False):
            runtime = ContainerWorkflowRuntime(execution)
            runtime.run_sync()

        parent_step = ExecutionStep.objects.filter(
            execution=execution,
            config_step_id='plat-1',
        ).first()
        assert parent_step is not None
        assert parent_step.status == ExecutionStepStatus.FAILED


# ---------------------------------------------------------------------------
# AC3 — Échec plateforme → parent step FAILED
# ---------------------------------------------------------------------------

class TestAC3PlatformFailurePropagated:
    """AC3 : si le job plateforme échoue (child step FAILED), le parent step est FAILED."""

    @pytest.mark.django_db
    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.container_workflow_runtime.trigger_platform_job')
    @patch('executions.container_workflow_runtime.get_platform_queue', return_value='default')
    def test_parent_step_failed_when_platform_job_fails(self, mock_queue, mock_trigger, mock_audit):
        """AC3 : apply_async side_effect marque child step FAILED → parent ExecutionStep FAILED."""
        user = UserFactory()
        integration = IntegrationFactory()
        ref_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            integration=integration,
            created_by=user,
        )
        workflow_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[_make_platform_step_config(ref_action.id)],
            created_by=user,
        )
        execution = Execution.objects.create(
            action=workflow_action,
            user=user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )

        def _trigger_side_effect(kwargs, queue):
            """Simule un échec plateforme : marque child step FAILED."""
            exec_step_id = kwargs['execution_step_id']
            ExecutionStep.objects.filter(id=exec_step_id).update(
                status=ExecutionStepStatus.FAILED,
                completed_at=timezone.now(),
                error_message="Platform job failed: connection refused",
            )

        mock_trigger.apply_async.side_effect = _trigger_side_effect

        with override_settings(SIMULATE_EXECUTION_DEV=False):
            runtime = ContainerWorkflowRuntime(execution)
            runtime.run_sync()

        # Child execution doit être FAILED
        child = Execution.objects.filter(parent_execution_id=execution.id).first()
        assert child is not None
        assert child.status == ExecutionStatus.FAILED

        # Parent step doit être FAILED
        parent_step = ExecutionStep.objects.filter(
            execution=execution,
            config_step_id='plat-1',
        ).first()
        assert parent_step is not None
        assert parent_step.status == ExecutionStepStatus.FAILED

    @pytest.mark.django_db
    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.container_workflow_runtime.trigger_platform_job')
    @patch('executions.container_workflow_runtime.get_platform_queue', return_value='default')
    def test_child_execution_failed_when_platform_job_fails(self, mock_queue, mock_trigger, mock_audit):
        """AC3 : child execution est FAILED quand le job plateforme échoue."""
        user = UserFactory()
        integration = IntegrationFactory()
        ref_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            integration=integration,
            created_by=user,
        )
        workflow_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[_make_platform_step_config(ref_action.id)],
            created_by=user,
        )
        execution = Execution.objects.create(
            action=workflow_action,
            user=user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )

        def _trigger_side_effect(kwargs, queue):
            exec_step_id = kwargs['execution_step_id']
            ExecutionStep.objects.filter(id=exec_step_id).update(
                status=ExecutionStepStatus.FAILED,
                completed_at=timezone.now(),
            )

        mock_trigger.apply_async.side_effect = _trigger_side_effect

        with override_settings(SIMULATE_EXECUTION_DEV=False):
            runtime = ContainerWorkflowRuntime(execution)
            runtime.run_sync()

        child = Execution.objects.filter(parent_execution_id=execution.id).first()
        assert child is not None
        assert child.status == ExecutionStatus.FAILED


# ---------------------------------------------------------------------------
# AC4 — Branche placeholder supprimée
# ---------------------------------------------------------------------------

class TestAC4PlaceholderRemoved:
    """AC4 : item_type='action' ne marque plus COMPLETED silencieusement."""

    @pytest.mark.django_db
    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.container_workflow_runtime.trigger_platform_job')
    @patch('executions.container_workflow_runtime.get_platform_queue', return_value='default')
    def test_action_with_integration_not_marked_completed_by_placeholder(
        self, mock_queue, mock_trigger, mock_audit,
    ):
        """AC4 : avec intégration, le child n'est pas marqué COMPLETED par un placeholder — dispatch réel."""
        user = UserFactory()
        integration = IntegrationFactory()
        ref_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            integration=integration,
            created_by=user,
        )
        workflow_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[_make_platform_step_config(ref_action.id)],
            created_by=user,
        )
        execution = Execution.objects.create(
            action=workflow_action,
            user=user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )

        # Side effect: marque le child step FAILED (pas COMPLETED via placeholder)
        def _trigger_side_effect(kwargs, queue):
            exec_step_id = kwargs['execution_step_id']
            ExecutionStep.objects.filter(id=exec_step_id).update(
                status=ExecutionStepStatus.FAILED,
                completed_at=timezone.now(),
            )

        mock_trigger.apply_async.side_effect = _trigger_side_effect

        with override_settings(SIMULATE_EXECUTION_DEV=False):
            runtime = ContainerWorkflowRuntime(execution)
            runtime.run_sync()

        # Le child doit être FAILED (le job plateforme a échoué), pas COMPLETED via placeholder
        child = Execution.objects.filter(parent_execution_id=execution.id).first()
        assert child is not None
        assert child.status == ExecutionStatus.FAILED, (
            f"Le child execution doit être FAILED (via job plateforme), pas COMPLETED via placeholder. "
            f"Statut actuel: {child.status}"
        )
        assert mock_trigger.apply_async.called, "Le dispatch réel doit avoir été appelé (pas le placeholder)"

    @pytest.mark.django_db
    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.container_workflow_runtime.trigger_platform_job')
    @patch('executions.container_workflow_runtime.get_platform_queue', return_value='default')
    def test_action_without_integration_marked_failed_not_completed(
        self, mock_queue, mock_trigger, mock_audit,
    ):
        """AC4 : sans intégration, le child est FAILED (explicite), jamais COMPLETED silencieusement."""
        user = UserFactory()
        ref_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            integration=None,
            created_by=user,
        )
        workflow_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[_make_platform_step_config(ref_action.id)],
            created_by=user,
        )
        execution = Execution.objects.create(
            action=workflow_action,
            user=user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )

        with override_settings(SIMULATE_EXECUTION_DEV=False):
            runtime = ContainerWorkflowRuntime(execution)
            runtime.run_sync()

        child = Execution.objects.filter(parent_execution_id=execution.id).first()
        assert child is not None
        assert child.status == ExecutionStatus.FAILED, (
            f"Sans intégration, le child doit être FAILED, pas COMPLETED silencieusement. "
            f"Statut: {child.status}"
        )
        assert not mock_trigger.apply_async.called


# ---------------------------------------------------------------------------
# Rétrocompatibilité — item_type='workflow' passe toujours par run_sync()
# ---------------------------------------------------------------------------

class TestBackwardCompatibilityWorkflowItemType:
    """Rétrocompatibilité : item_type='workflow' continue d'utiliser ContainerWorkflowRuntime.run_sync()."""

    @pytest.mark.django_db
    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.container_workflow_runtime.trigger_platform_job')
    @patch('executions.container_workflow_runtime.get_platform_queue', return_value='default')
    def test_workflow_item_type_uses_run_sync_not_dispatch(self, mock_queue, mock_trigger, mock_audit):
        """Rétrocompatibilité : step platform avec item_type='workflow' → run_sync(), pas apply_async."""
        user = UserFactory()
        # Action enfant de type workflow (sans steps pour éviter récursion)
        child_workflow_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[],  # Workflow vide
            created_by=user,
        )
        parent_workflow = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[_make_platform_step_config(child_workflow_action.id)],
            created_by=user,
        )
        execution = Execution.objects.create(
            action=parent_workflow,
            user=user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )

        with override_settings(SIMULATE_EXECUTION_DEV=False):
            runtime = ContainerWorkflowRuntime(execution)
            runtime.run_sync()

        # apply_async ne doit PAS être appelé pour item_type='workflow'
        assert not mock_trigger.apply_async.called, (
            "trigger_platform_job.apply_async ne doit PAS être appelé pour item_type='workflow'"
        )

        # Le child execution doit exister et être terminal
        child = Execution.objects.filter(parent_execution_id=execution.id).first()
        assert child is not None
        assert child.status in (ExecutionStatus.COMPLETED, ExecutionStatus.FAILED)


# ---------------------------------------------------------------------------
# Task 4.4 — Timeout de polling → child FAILED avec message explicite
# ---------------------------------------------------------------------------

class TestPollingTimeout:
    """Task 4.4 : si le child step reste RUNNING au-delà du timeout, child FAILED."""

    @pytest.mark.django_db
    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.platform_step_executor.PLATFORM_ACTION_MAX_WAIT_SECONDS', 0)
    @patch('executions.platform_step_executor.PLATFORM_ACTION_POLL_INTERVAL_SECONDS', 0)
    @patch('executions.container_workflow_runtime.trigger_platform_job')
    @patch('executions.container_workflow_runtime.get_platform_queue', return_value='default')
    def test_timeout_marks_child_failed_with_message(self, mock_queue, mock_trigger, mock_audit):
        """Task 4.4 : timeout → child step FAILED 'Platform action wait timeout', child execution FAILED."""
        user = UserFactory()
        integration = IntegrationFactory()
        ref_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            integration=integration,
            created_by=user,
        )
        workflow_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[_make_platform_step_config(ref_action.id)],
            created_by=user,
        )
        execution = Execution.objects.create(
            action=workflow_action,
            user=user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )

        # apply_async ne marque PAS le step → polling expire immédiatement (MAX_WAIT=0)
        mock_trigger.apply_async.side_effect = None
        mock_trigger.apply_async.return_value = MagicMock()

        with override_settings(SIMULATE_EXECUTION_DEV=False):
            runtime = ContainerWorkflowRuntime(execution)
            runtime.run_sync()

        # Child execution doit être FAILED
        child = Execution.objects.filter(parent_execution_id=execution.id).first()
        assert child is not None
        assert child.status == ExecutionStatus.FAILED

        # Le child step doit avoir le message de timeout
        child_step = ExecutionStep.objects.filter(
            execution=child,
            step_type=ExecutionStepType.PLATFORM,
        ).first()
        assert child_step is not None
        assert child_step.status == ExecutionStepStatus.FAILED
        assert child_step.error_message == "Platform action wait timeout"
