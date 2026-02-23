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
        ref_action = ActionFactory()
        ref_action.integration = None  # no integration → simulated adapter

        step = {
            'step_id': 'step-ok', 'name': 'OK Step', 'order': 1,
            'referenced_action_id': ref_action.id,
        }

        with patch("catalog.models.Action.objects") as mock_qs:
            mock_qs.select_related.return_value.get.return_value = ref_action

            with patch.object(self.executor, 'call_platform_adapter',
                              return_value={'status': 'success', 'simulated': True}):
                with patch.object(self.executor, '_evaluate_policy_if_needed',
                                  return_value=None):
                    result = self.executor.execute(step, step_order=1, step_parameters={'key': 'val'})

        assert result.is_success
        from executions.models import ExecutionStep, ExecutionStepStatus
        step_record = ExecutionStep.objects.filter(execution=self.execution).first()
        assert step_record is not None
        assert step_record.status == ExecutionStepStatus.COMPLETED


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

    @patch("executions.workflow_step_executor.AuditService.create_entry")
    def test_no_integration_returns_simulated_response(self, mock_audit):
        """Sans integration, retourne une réponse simulée."""
        referenced_action = MagicMock()
        referenced_action.id = 1
        referenced_action.name = "Test Action"
        referenced_action.platform = "AAP"

        result = self.executor.call_platform_adapter(
            referenced_action, None, {'parameters': {}}, self.execution_step
        )

        assert result['simulated'] is True
        assert result['status'] == 'success'
        mock_audit.assert_called_once()

    def test_adapter_call_failure_falls_back_to_simulated(self):
        """Quand l'adapter échoue, retourne une réponse simulée avec log CRITICAL."""
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
            with patch("executions.workflow_step_executor.AuditService.create_entry"):
                with patch("adapters.utils.build_auth_headers", return_value={}):
                    result = self.executor.call_platform_adapter(
                        referenced_action, integration, {'parameters': {}}, self.execution_step
                    )

        assert result['simulated'] is True


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
