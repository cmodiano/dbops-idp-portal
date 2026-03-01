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


# ---------------------------------------------------------------------------
# Story 55.3 — Branches non couvertes (sous-tâches 6.1 à 6.10)
# ---------------------------------------------------------------------------

class TestStepExecutorActionDoesNotExist(TransactionTestCase):
    """Action.DoesNotExist → ValueError → StepResult ERROR (lines 154-155)."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory(item_type="workflow")
        from executions.models import Execution, ExecutionStatus
        self.execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.RUNNING,
        )
        self.executor = StepExecutor(self.execution, "test-corr")

    def test_action_does_not_exist_returns_validation_error(self):
        from catalog.models import Action
        step = {
            'step_id': 'step-notfound', 'name': 'Missing Action', 'order': 1,
            'referenced_action_id': 9999,
        }
        with patch("catalog.models.Action.objects") as mock_qs:
            mock_qs.select_related.return_value.get.side_effect = Action.DoesNotExist
            result = self.executor.execute(step, step_order=1, step_parameters={})

        from executions.workflow_runtime import StepOutcome
        assert result.outcome == StepOutcome.ERROR
        assert result.error_details.get('error_type') == 'validation'
        assert '9999' in result.error_message

        from executions.models import ExecutionStep, ExecutionStepStatus
        step_record = ExecutionStep.objects.filter(execution=self.execution).first()
        assert step_record.status == ExecutionStepStatus.FAILED


class TestStepExecutorInvalidIntegration(TransactionTestCase):
    """IntegrationStatus.INVALID → ValueError + audit BLOCKED_INVALID (lines 164-193)."""

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
    def test_invalid_integration_returns_error_with_audit(self, mock_audit):
        from integrations.models import IntegrationStatus

        ref_action = MagicMock()
        ref_action.id = 42
        ref_action.name = "Test Action"
        ref_action.platform = "AAP"

        mock_integration = MagicMock()
        mock_integration.status = IntegrationStatus.INVALID
        mock_integration.name = "Broken Integration"
        mock_integration.type = "aap"
        mock_integration.id = 10
        ref_action.integration = mock_integration

        step = {
            'step_id': 'step-inv', 'name': 'Invalid Step', 'order': 1,
            'referenced_action_id': 42,
        }

        with patch("catalog.models.Action.objects") as mock_qs:
            mock_qs.select_related.return_value.get.return_value = ref_action
            result = self.executor.execute(step, step_order=1, step_parameters={})

        from executions.workflow_runtime import StepOutcome
        assert result.outcome == StepOutcome.ERROR
        assert 'invalid' in result.error_message.lower()
        mock_audit.assert_called_once()
        from core.models import AuditActionType
        assert mock_audit.call_args.kwargs['action_type'] == AuditActionType.WORKFLOW_STEP_BLOCKED_INVALID_INTEGRATION

        from executions.models import ExecutionStep, ExecutionStepStatus
        step_record = ExecutionStep.objects.filter(execution=self.execution).first()
        assert step_record.status == ExecutionStepStatus.FAILED


class TestStepExecutorDeprecatedIntegration(TransactionTestCase):
    """IntegrationStatus.DEPRECATED → warning + audit, execution continues (lines 196-205)."""

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
    def test_deprecated_integration_audited_then_continues_to_success(self, mock_audit):
        from integrations.models import IntegrationStatus

        ref_action = MagicMock()
        ref_action.id = 43
        ref_action.name = "Deprecated Action"
        ref_action.platform = "AAP"

        mock_integration = MagicMock()
        mock_integration.status = IntegrationStatus.DEPRECATED
        mock_integration.name = "Old Integration"
        mock_integration.type = "aap"
        mock_integration.id = 11
        ref_action.integration = mock_integration

        step = {
            'step_id': 'step-dep', 'name': 'Deprecated Step', 'order': 1,
            'referenced_action_id': 43,
        }

        with patch("catalog.models.Action.objects") as mock_qs, \
             patch("executions.tasks.trigger.trigger_platform_job.apply_async"):
            mock_qs.select_related.return_value.get.return_value = ref_action
            result = self.executor.execute(step, step_order=1, step_parameters={})

        from executions.workflow_runtime import StepOutcome
        assert result.outcome == StepOutcome.SUCCESS
        mock_audit.assert_called_once()
        from core.models import AuditActionType
        assert mock_audit.call_args.kwargs['action_type'] == AuditActionType.EXECUTION_DEPRECATED_INTEGRATION_WARNING


class TestStepExecutorTriggerKwargsExtras(TransactionTestCase):
    """resource_type et extra_vars dans trigger_kwargs (lines 255, 257)."""

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
        self.executor = StepExecutor(self.execution, "test-corr-extras")

    @patch("executions.workflow_step_executor.AuditService.create_entry")
    def test_resource_type_added_to_trigger_kwargs(self, mock_audit):
        ref_action = MagicMock()
        ref_action.id = 50
        ref_action.name = "RT Action"
        ref_action.platform = "AAP"
        ref_action.integration = self.integration

        step = {'step_id': 'step-rt', 'name': 'RT Step', 'order': 1, 'referenced_action_id': 50}

        with patch("catalog.models.Action.objects") as mock_qs, \
             patch("executions.tasks.trigger.trigger_platform_job.apply_async") as mock_async:
            mock_qs.select_related.return_value.get.return_value = ref_action
            self.executor.execute(step, step_order=1, step_parameters={'resource_type': 'host'})

        trigger_kwargs = mock_async.call_args.kwargs['kwargs']['trigger_kwargs']
        assert trigger_kwargs.get('resource_type') == 'host'

    @patch("executions.workflow_step_executor.AuditService.create_entry")
    def test_extra_vars_added_to_trigger_kwargs(self, mock_audit):
        ref_action = MagicMock()
        ref_action.id = 51
        ref_action.name = "EV Action"
        ref_action.platform = "AAP"
        ref_action.integration = self.integration

        step = {'step_id': 'step-ev', 'name': 'EV Step', 'order': 1, 'referenced_action_id': 51}

        with patch("catalog.models.Action.objects") as mock_qs, \
             patch("executions.tasks.trigger.trigger_platform_job.apply_async") as mock_async:
            mock_qs.select_related.return_value.get.return_value = ref_action
            self.executor.execute(step, step_order=1, step_parameters={'extra_vars': {'env': 'prod'}})

        trigger_kwargs = mock_async.call_args.kwargs['kwargs']['trigger_kwargs']
        assert trigger_kwargs.get('extra_vars') == {'env': 'prod'}


class TestStepExecutorGenericException(TransactionTestCase):
    """Generic except Exception handler — non-ValueError exceptions (lines 373-391)."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory(item_type="workflow")
        from executions.models import Execution, ExecutionStatus
        self.execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.RUNNING,
        )
        self.executor = StepExecutor(self.execution, "test-corr-exc")

    def test_runtime_exception_caught_marks_step_failed_returns_error(self):
        step = {
            'step_id': 'step-boom', 'name': 'Boom Step', 'order': 1,
            'referenced_action_id': 99,
        }
        with patch("catalog.models.Action.objects") as mock_qs:
            mock_qs.select_related.return_value.get.side_effect = RuntimeError("unexpected boom!")
            result = self.executor.execute(step, step_order=1, step_parameters={})

        from executions.workflow_runtime import StepOutcome
        assert result.outcome == StepOutcome.ERROR
        assert result.error_details.get('error_type') == 'RuntimeError'
        assert 'unexpected boom!' in result.error_message

        from executions.models import ExecutionStep, ExecutionStepStatus
        step_record = ExecutionStep.objects.filter(execution=self.execution).first()
        assert step_record.status == ExecutionStepStatus.FAILED
        assert 'RuntimeError' in step_record.error_message


class TestCallPlatformAdapterSuccess(TransactionTestCase):
    """call_platform_adapter config branches and success path (lines 431-476)."""

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
            step_order=2,
            step_name="Config Test Step",
            step_type='platform',
            status=ExecutionStepStatus.RUNNING,
            started_at=timezone.now(),
        )
        self.executor = StepExecutor(self.execution, "test-corr-cfg")

    def _make_integration(self, config=None):
        integration = MagicMock()
        integration.type = "aap"
        integration.base_url = "https://aap.example.com"
        integration.get_config.return_value = config or {}
        return integration

    def test_ssl_verify_and_ca_bundle_added_to_platform_kwargs(self):
        referenced_action = MagicMock()
        referenced_action.id = 60
        referenced_action.platform = "AAP"

        integration = self._make_integration({'ssl_verify': False, 'ca_bundle_path': '/etc/ssl/cert.pem'})
        mock_result = {'platform_job_id': 'job-456'}

        with patch("adapters.get_platform_adapter") as mock_get_adapter, \
             patch("adapters.utils.build_auth_headers", return_value={}), \
             patch("asgiref.sync.async_to_sync") as mock_a2s:
            mock_get_adapter.return_value = MagicMock()
            mock_a2s.return_value = lambda **kwargs: mock_result

            result = self.executor.call_platform_adapter(
                referenced_action, integration, {'parameters': {}}, self.execution_step
            )

        assert result == mock_result
        call_kwargs = mock_get_adapter.call_args.kwargs
        assert call_kwargs.get('ssl_verify') is False
        assert call_kwargs.get('ca_bundle_path') == '/etc/ssl/cert.pem'
        assert self.execution_step.platform_job_id == 'job-456'

    def test_adapter_result_without_platform_job_id_no_attribute_set(self):
        referenced_action = MagicMock()
        referenced_action.id = 61
        referenced_action.platform = "AAP"

        integration = self._make_integration()
        mock_result = {'status': 'running'}  # pas de platform_job_id

        with patch("adapters.get_platform_adapter") as mock_get_adapter, \
             patch("adapters.utils.build_auth_headers", return_value={}), \
             patch("asgiref.sync.async_to_sync") as mock_a2s:
            mock_get_adapter.return_value = MagicMock()
            mock_a2s.return_value = lambda **kwargs: mock_result

            result = self.executor.call_platform_adapter(
                referenced_action, integration,
                {'parameters': {'template_id': '5', 'resource_type': 'host', 'extra_vars': {'k': 'v'}}},
                self.execution_step,
            )

        assert result == mock_result

    def test_trigger_kwargs_resource_type_and_extra_vars_passed_to_adapter(self):
        referenced_action = MagicMock()
        referenced_action.id = 62
        referenced_action.platform = "AAP"

        integration = self._make_integration()
        captured = {}
        mock_result = {'platform_job_id': 'job-789'}

        def fake_sync(coro_fn):
            def wrapper(**kwargs):
                captured.update(kwargs)
                return mock_result
            return wrapper

        with patch("adapters.get_platform_adapter") as mock_get_adapter, \
             patch("adapters.utils.build_auth_headers", return_value={}), \
             patch("asgiref.sync.async_to_sync", side_effect=fake_sync):
            mock_get_adapter.return_value = MagicMock()

            self.executor.call_platform_adapter(
                referenced_action, integration,
                {'parameters': {'resource_type': 'inventory', 'extra_vars': {'x': 1}}},
                self.execution_step,
            )

        assert captured.get('resource_type') == 'inventory'
        assert captured.get('extra_vars') == {'x': 1}


class TestEvaluatePolicyRemainingBranches(TransactionTestCase):
    """_evaluate_policy_if_needed: empty rules, PolicyEvaluationError, auto-approved."""

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
            step_order=3,
            step_name="Policy Step",
            step_type='platform',
            status=ExecutionStepStatus.RUNNING,
            started_at=timezone.now(),
        )
        self.executor = StepExecutor(self.execution, "test-corr-policy")

    def test_empty_on_step_output_rules_returns_none(self):
        """policies dict sans on_step_output → rules=[] → return None (line 513)."""
        action = MagicMock()
        action.business_rule_policies = {'other_key': 'value'}

        result = self.executor._evaluate_policy_if_needed(self.execution_step, action, {})
        assert result is None

    def test_on_step_output_empty_list_returns_none(self):
        """policies dict avec on_step_output=[] → rules=[] → return None (line 513)."""
        action = MagicMock()
        action.business_rule_policies = {'on_step_output': []}

        result = self.executor._evaluate_policy_if_needed(self.execution_step, action, {})
        assert result is None

    @patch("executions.workflow_step_executor.AuditService.create_entry")
    def test_policy_evaluation_error_marks_step_failed_returns_error(self, mock_audit):
        """PolicyEvaluationError → step FAILED, StepResult ERROR (lines 529-557)."""
        from executions.policy_evaluator import PolicyEvaluationError

        action = MagicMock()
        action.business_rule_policies = {
            'on_step_output': [{'when': {'step_type': 'platform'}}]
        }

        exc = PolicyEvaluationError("schema invalid")
        exc.message = "schema invalid"

        with patch("executions.policy_evaluator.PolicyEvaluator") as MockEval:
            MockEval.return_value.evaluate_policy.side_effect = exc
            result = self.executor._evaluate_policy_if_needed(self.execution_step, action, {})

        from executions.workflow_runtime import StepOutcome
        assert result.outcome == StepOutcome.ERROR
        assert result.error_details.get('policy_evaluation_failed') is True
        mock_audit.assert_called_once()
        from core.models import AuditActionType
        assert mock_audit.call_args.kwargs['action_type'] == AuditActionType.EXECUTION_STEP_POLICY_EVALUATION_FAILED

        from executions.models import ExecutionStepStatus
        self.execution_step.refresh_from_db()
        assert self.execution_step.status == ExecutionStepStatus.FAILED

    @patch("executions.workflow_step_executor.AuditService.create_entry")
    def test_auto_approved_policy_returns_success_with_audit(self, mock_audit):
        """require_approval=False → StepResult SUCCESS, audit AUTO_APPROVED (lines 607-626)."""
        from dataclasses import dataclass

        @dataclass
        class FakeDecision:
            require_approval: bool = False
            decision_reason: str = "Auto-approved"

        action = MagicMock()
        action.business_rule_policies = {
            'on_step_output': [{'when': {'step_type': 'platform'}}]
        }

        with patch("executions.policy_evaluator.PolicyEvaluator") as MockEval:
            MockEval.return_value.evaluate_policy.return_value = FakeDecision(require_approval=False)
            result = self.executor._evaluate_policy_if_needed(self.execution_step, action, {})

        from executions.workflow_runtime import StepOutcome
        assert result.outcome == StepOutcome.SUCCESS
        assert result.output.get('auto_approved') is True
        mock_audit.assert_called_once()
        from core.models import AuditActionType
        assert mock_audit.call_args.kwargs['action_type'] == AuditActionType.EXECUTION_STEP_POLICY_AUTO_APPROVED
