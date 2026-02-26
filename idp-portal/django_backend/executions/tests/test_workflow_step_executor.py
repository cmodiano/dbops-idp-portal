"""Tests unitaires pour StepExecutor (Story 34.7)."""
from unittest.mock import MagicMock, patch

from django.test import TransactionTestCase
from django.utils import timezone

from executions.workflow_step_executor import StepExecutor
from tests.factories import UserFactory, ActionFactory


# ---------------------------------------------------------------------------
# TestStepExecutorWaiting — gate_conditions présentes
# ---------------------------------------------------------------------------

class TestStepExecutorWaiting(TransactionTestCase):
    """StepExecutor.execute retourne WAITING quand gate_conditions est présent."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory(item_type="workflow")
        from executions.models import Execution, ExecutionStatus
        self.execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.RUNNING,
        )
        self.executor = StepExecutor(self.execution, "test-corr")

    @patch("executions.workflow_step_executor.AuditService.create_entry")
    @patch("executions.gate_context.build_waiting_context", return_value={"gates": []})
    def test_gate_conditions_creates_waiting_step(self, mock_ctx, mock_audit):
        step = {
            'step_id': 'step-wait', 'name': 'Wait Step', 'order': 1,
            'gate_conditions': [{'type': 'time_window', 'start': '08:00', 'end': '18:00'}],
            'referenced_action_id': 99,
        }

        result = self.executor.execute(step, step_order=1, step_parameters={})

        assert result.is_waiting
        assert result.error_details['gate_conditions_count'] == 1

        from executions.models import ExecutionStep, ExecutionStepStatus
        step_record = ExecutionStep.objects.filter(execution=self.execution).first()
        assert step_record is not None
        assert step_record.status == ExecutionStepStatus.WAITING
        mock_audit.assert_called_once()


# ---------------------------------------------------------------------------
# TestStepExecutorSuccess — exécution réussie
# ---------------------------------------------------------------------------

class TestStepExecutorSuccess(TransactionTestCase):
    """StepExecutor.execute retourne SUCCESS quand l'adapter réussit."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory(item_type="workflow")
        from executions.models import Execution, ExecutionStatus
        self.execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.RUNNING,
        )
        self.executor = StepExecutor(self.execution, "test-corr")

    @patch("executions.workflow_step_executor.AuditService.create_entry")
    def test_step_success(self, mock_audit):
        """execute() avec integration → dispatch async, step RUNNING."""
        from tests.factories import IntegrationFactory
        ref_action = ActionFactory()
        ref_action.integration = IntegrationFactory.create(type="aap")

        step = {
            'step_id': 'step-ok', 'name': 'OK Step', 'order': 1,
            'referenced_action_id': ref_action.id,
        }

        with patch("catalog.models.Action.objects") as mock_qs:
            mock_qs.select_related.return_value.get.return_value = ref_action

            with patch("executions.tasks.trigger.trigger_platform_job.apply_async"):
                result = self.executor.execute(step, step_order=1, step_parameters={'key': 'val'})

        assert result.is_success
        from executions.models import ExecutionStep, ExecutionStepStatus
        step_record = ExecutionStep.objects.filter(execution=self.execution).first()
        assert step_record is not None
        assert step_record.status == ExecutionStepStatus.RUNNING  # async dispatched — reste RUNNING


# ---------------------------------------------------------------------------
# TestStepExecutorValidationError — action_id manquant
# ---------------------------------------------------------------------------

class TestStepExecutorValidationError(TransactionTestCase):
    """StepExecutor.execute retourne ERROR sur erreur de validation."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory(item_type="workflow")
        from executions.models import Execution, ExecutionStatus
        self.execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.RUNNING,
        )
        self.executor = StepExecutor(self.execution, "test-corr")

    def test_missing_referenced_action_id_returns_error(self):
        step = {'step_id': 'step-bad', 'name': 'Bad Step', 'order': 1}

        result = self.executor.execute(step, step_order=1, step_parameters={})

        assert result.is_error
        assert result.error_details['error_type'] == 'validation'
        assert 'missing referenced_action_id' in result.error_message

        from executions.models import ExecutionStep, ExecutionStepStatus
        step_record = ExecutionStep.objects.filter(execution=self.execution).first()
        assert step_record is not None
        assert step_record.status == ExecutionStepStatus.FAILED


# ---------------------------------------------------------------------------
# TestCallPlatformAdapter — appel adapter plateforme
# ---------------------------------------------------------------------------

class TestCallPlatformAdapter(TransactionTestCase):
    """StepExecutor._call_platform_adapter tests."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory(item_type="workflow")
        from executions.models import Execution, ExecutionStatus
        self.execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.RUNNING,
        )
        from executions.models import ExecutionStep, ExecutionStepStatus
        self.execution_step = ExecutionStep.objects.create(
            execution=self.execution,
            step_order=1,
            step_name="Test Step",
            step_type='platform',
            status=ExecutionStepStatus.RUNNING,
            started_at=timezone.now(),
        )
        self.executor = StepExecutor(self.execution, "test-corr")

    def test_no_integration_raises_value_error(self):
        """Sans integration, lève ValueError avec message explicite (Story 47.3 fail-fast)."""
        referenced_action = MagicMock()
        referenced_action.id = 1
        referenced_action.name = "Test Action"
        referenced_action.platform = "AAP"

        with self.assertRaises(ValueError) as ctx:
            self.executor.call_platform_adapter(
                referenced_action, None, {'parameters': {}}, self.execution_step
            )

        assert "No integration configured for action 1" in str(ctx.exception)
        assert "AAP" in str(ctx.exception)

    def test_adapter_call_failure_reraises_exception(self):
        """Quand l'adapter échoue, l'exception est re-raised (Story 47.3 fail-fast)."""
        referenced_action = MagicMock()
        referenced_action.id = 1
        referenced_action.name = "Test Action"
        referenced_action.platform = "AAP"

        integration = MagicMock()
        integration.type = "aap"
        integration.base_url = "https://aap.example.com"
        integration.get_config.return_value = {}

        with patch("adapters.get_platform_adapter",
                   side_effect=Exception("Adapter not found")):
            with patch("adapters.utils.build_auth_headers", return_value={}):
                with self.assertRaises(Exception) as ctx:
                    self.executor.call_platform_adapter(
                        referenced_action, integration, {'parameters': {}}, self.execution_step
                    )

        assert "Adapter not found" in str(ctx.exception)


# ---------------------------------------------------------------------------
# TestEvaluatePolicyIfNeeded — évaluation policy
# ---------------------------------------------------------------------------

class TestEvaluatePolicyIfNeeded(TransactionTestCase):
    """StepExecutor._evaluate_policy_if_needed tests."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory(item_type="workflow")
        from executions.models import Execution, ExecutionStatus
        self.execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.RUNNING,
        )
        from executions.models import ExecutionStep, ExecutionStepStatus
        self.execution_step = ExecutionStep.objects.create(
            execution=self.execution,
            step_order=1,
            step_name="Policy Test Step",
            step_type='platform',
            status=ExecutionStepStatus.RUNNING,
            started_at=timezone.now(),
        )
        self.executor = StepExecutor(self.execution, "test-corr")

    def test_no_policies_returns_none(self):
        """Sans policies sur l'action, retourne None (pas de décision)."""
        action = MagicMock()
        action.business_rule_policies = None

        result = self.executor._evaluate_policy_if_needed(
            self.execution_step, action, {}
        )

        assert result is None

    def test_no_matching_rule_returns_none(self):
        """Si aucune règle ne correspond au step_type, retourne None."""
        action = MagicMock()
        action.business_rule_policies = {
            'on_step_output': [{'when': {'step_type': 'other_type'}}]
        }

        result = self.executor._evaluate_policy_if_needed(
            self.execution_step, action, {}
        )

        assert result is None

    @patch("executions.workflow_step_executor.AuditService.create_entry")
    def test_approval_required_returns_waiting(self, mock_audit):
        """Si la policy exige une approbation, retourne WAITING."""
        from dataclasses import dataclass

        @dataclass
        class FakeDecision:
            require_approval: bool = True
            decision_reason: str = "Approval needed"

        action = MagicMock()
        action.business_rule_policies = {
            'on_step_output': [{'when': {'step_type': 'platform'}}]
        }

        with patch("executions.policy_evaluator.PolicyEvaluator") as MockEval:
            MockEval.return_value.evaluate_policy.return_value = FakeDecision(require_approval=True)
            with patch("dataclasses.asdict",
                       return_value={'require_approval': True, 'decision_reason': 'Approval needed'}):
                result = self.executor._evaluate_policy_if_needed(
                    self.execution_step, action, {}
                )

        assert result is not None
        assert result.is_waiting


# ---------------------------------------------------------------------------
# TestStepExecutorAsyncDispatch — Story 47.2 : dispatch async via Celery
# ---------------------------------------------------------------------------

class TestStepExecutorAsyncDispatch(TransactionTestCase):
    """StepExecutor.execute() avec integration → dispatch async trigger_platform_job."""

    def setUp(self):
        from tests.factories import IntegrationFactory
        self.user = UserFactory()
        self.action = ActionFactory(item_type="workflow")
        from executions.models import Execution, ExecutionStatus
        self.execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.RUNNING,
        )
        self.integration = IntegrationFactory.create(type="aap")
        self.executor = StepExecutor(self.execution, "test-corr-async")

    @patch("executions.workflow_step_executor.AuditService.create_entry")
    def test_execute_with_integration_dispatches_async(self, mock_audit):
        """execute() avec integration → trigger_platform_job.apply_async appelé, step reste RUNNING."""
        ref_action = ActionFactory()
        ref_action.integration = self.integration

        step = {
            'step_id': 'step-async',
            'name': 'Async Step',
            'order': 1,
            'referenced_action_id': ref_action.id,
        }

        with patch("executions.tasks.trigger.trigger_platform_job.apply_async") as mock_apply_async:
            with patch("catalog.models.Action.objects") as mock_qs:
                mock_qs.select_related.return_value.get.return_value = ref_action

                result = self.executor.execute(step, step_order=1, step_parameters={'template_id': '5'})

        from executions.workflow_runtime import StepOutcome
        assert result.outcome == StepOutcome.SUCCESS
        assert result.output.get('async_dispatched') is True
        mock_apply_async.assert_called_once()
        call_kwargs = mock_apply_async.call_args
        assert call_kwargs.kwargs['kwargs']['integration_id'] == self.integration.id

        from executions.models import ExecutionStep, ExecutionStepStatus
        step_record = ExecutionStep.objects.filter(execution=self.execution).first()
        assert step_record is not None
        assert step_record.status == ExecutionStepStatus.RUNNING  # PAS COMPLETED

    @patch("executions.workflow_step_executor.AuditService.create_entry")
    def test_execute_without_integration_returns_error_step_failed(self, mock_audit):
        """execute() sans integration → StepResult(ERROR), step FAILED (Story 47.3 fail-fast)."""
        ref_action = ActionFactory()
        ref_action.integration = None  # pas d'integration → fail-fast

        step = {
            'step_id': 'step-noint',
            'name': 'No Integration Step',
            'order': 1,
            'referenced_action_id': ref_action.id,
        }

        with patch("catalog.models.Action.objects") as mock_qs:
            mock_qs.select_related.return_value.get.return_value = ref_action

            result = self.executor.execute(step, step_order=1, step_parameters={})

        from executions.workflow_runtime import StepOutcome
        assert result.outcome == StepOutcome.ERROR
        assert result.error_details['error_type'] == 'NO_INTEGRATION'

        from executions.models import ExecutionStep, ExecutionStepStatus
        step_record = ExecutionStep.objects.filter(execution=self.execution).first()
        assert step_record is not None
        assert step_record.status == ExecutionStepStatus.FAILED
        assert "No integration configured" in step_record.error_message

        # Vérifier audit EXECUTION_INTEGRATION_ERROR créé
        mock_audit.assert_called_once()
        call_kwargs = mock_audit.call_args
        from core.models import AuditActionType
        assert call_kwargs.kwargs.get('action_type') == AuditActionType.EXECUTION_INTEGRATION_ERROR
