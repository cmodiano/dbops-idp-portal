"""Tests unitaires pour RetryHandler (Story 34.7)."""
from unittest.mock import MagicMock, patch

from django.test import TestCase, TransactionTestCase

from executions.workflow_runtime import StepResult, StepOutcome
from executions.workflow_retry import RetryHandler
from tests.factories import UserFactory, ActionFactory


def _make_execution(exec_id=1, user_id=42):
    """Helper — crée un objet Execution mock."""
    execution = MagicMock()
    execution.id = exec_id
    execution.user_id = user_id
    return execution


def _make_handler(execution=None, correlation_id="test-corr"):
    """Helper — crée un RetryHandler avec dépendances mockées."""
    if execution is None:
        execution = _make_execution()
    return RetryHandler(execution, correlation_id)


# ---------------------------------------------------------------------------
# is_retryable_error
# ---------------------------------------------------------------------------

class TestIsRetryableError(TestCase):
    """Tests pour RetryHandler.is_retryable_error."""

    def setUp(self):
        self.handler = _make_handler()

    def test_empty_error_message_is_retryable(self):
        result = StepResult(outcome=StepOutcome.ERROR, error_message="")
        assert self.handler.is_retryable_error(result) is True

    def test_none_error_message_is_retryable(self):
        result = StepResult(outcome=StepOutcome.ERROR, error_message=None)
        assert self.handler.is_retryable_error(result) is True

    def test_timeout_is_retryable(self):
        result = StepResult(outcome=StepOutcome.ERROR, error_message="Connection timeout")
        assert self.handler.is_retryable_error(result) is True

    def test_5xx_is_retryable(self):
        for code in ("500", "502", "503"):
            result = StepResult(outcome=StepOutcome.ERROR, error_message=f"HTTP {code} error")
            assert self.handler.is_retryable_error(result) is True, f"{code} should be retryable"

    def test_validation_error_not_retryable(self):
        result = StepResult(outcome=StepOutcome.ERROR, error_message="Validation failed")
        assert self.handler.is_retryable_error(result) is False

    def test_permission_error_not_retryable(self):
        result = StepResult(outcome=StepOutcome.ERROR, error_message="Permission denied")
        assert self.handler.is_retryable_error(result) is False

    def test_4xx_http_not_retryable(self):
        for code in ("400", "401", "403", "404"):
            result = StepResult(outcome=StepOutcome.ERROR, error_message=f"HTTP {code}")
            assert self.handler.is_retryable_error(result) is False, f"{code} should not be retryable"

    def test_error_type_validation_not_retryable(self):
        result = StepResult(
            outcome=StepOutcome.ERROR,
            error_message="something",
            error_details={'error_type': 'validation'},
        )
        assert self.handler.is_retryable_error(result) is False

    def test_error_type_permission_not_retryable(self):
        result = StepResult(
            outcome=StepOutcome.ERROR,
            error_message="something",
            error_details={'error_type': 'permission'},
        )
        assert self.handler.is_retryable_error(result) is False

    def test_generic_error_is_retryable(self):
        result = StepResult(outcome=StepOutcome.ERROR, error_message="Some random exception")
        assert self.handler.is_retryable_error(result) is True


# ---------------------------------------------------------------------------
# execute_with_retry — retry disabled
# ---------------------------------------------------------------------------

class TestExecuteWithRetryDisabled(TransactionTestCase):
    """Tests execute_with_retry quand retry_enabled est False."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory(item_type="workflow")
        from executions.models import Execution, ExecutionStatus
        self.execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.SUBMITTED,
        )
        self.handler = _make_handler(self.execution)

    def test_retry_disabled_calls_execute_fn_once(self):
        """Quand retry_enabled=False, execute_fn est appelé une seule fois."""
        step = {'step_id': 's1', 'order': 1, 'retry_enabled': False}
        execute_fn = MagicMock(return_value=StepResult(outcome=StepOutcome.SUCCESS))
        counter = [0]
        def counter_fn():
            counter[0] += 1
            return counter[0]

        result = self.handler.execute_with_retry(step, execute_fn, counter_fn)

        execute_fn.assert_called_once_with(step, 1)
        assert result.is_success

    def test_retry_missing_calls_execute_fn_once(self):
        """Quand retry_enabled est absent, execute_fn est appelé directement."""
        step = {'step_id': 's1', 'order': 1}
        execute_fn = MagicMock(return_value=StepResult(outcome=StepOutcome.ERROR, error_message="err"))
        counter = [0]
        def counter_fn():
            counter[0] += 1
            return counter[0]

        result = self.handler.execute_with_retry(step, execute_fn, counter_fn)

        execute_fn.assert_called_once()
        assert result.is_error


# ---------------------------------------------------------------------------
# execute_with_retry — success au premier essai
# ---------------------------------------------------------------------------

class TestExecuteWithRetrySuccess(TransactionTestCase):
    """Tests execute_with_retry — succès au premier essai."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory(item_type="workflow")
        from executions.models import Execution, ExecutionStatus
        self.execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.SUBMITTED,
        )
        self.handler = _make_handler(self.execution)

    @patch("executions.workflow_retry.AuditService.create_entry")
    @patch("executions.cancellation_cache.is_cancelled", return_value=False)
    def test_success_first_attempt_returns_success(self, mock_cancelled, mock_audit):
        step = {'step_id': 's1', 'order': 1, 'retry_enabled': True, 'retry_max_attempts': 3}
        execute_fn = MagicMock(return_value=StepResult(outcome=StepOutcome.SUCCESS))
        counter = [0]
        def counter_fn():
            counter[0] += 1
            return counter[0]

        result = self.handler.execute_with_retry(step, execute_fn, counter_fn)

        assert result.is_success
        execute_fn.assert_called_once_with(step, 1)
        mock_audit.assert_called_once()
        call_kwargs = mock_audit.call_args[1]
        from core.models import AuditActionType
        assert call_kwargs['action_type'] == AuditActionType.EXECUTION_STEP_RETRY_SUCCESS


# ---------------------------------------------------------------------------
# execute_with_retry — erreur non-retryable
# ---------------------------------------------------------------------------

class TestExecuteWithRetryNonRetryable(TransactionTestCase):
    """Tests execute_with_retry — erreur permanente, pas de retry."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory(item_type="workflow")
        from executions.models import Execution, ExecutionStatus
        self.execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.SUBMITTED,
        )
        self.handler = _make_handler(self.execution)

    @patch("executions.workflow_retry.AuditService.create_entry")
    @patch("executions.cancellation_cache.is_cancelled", return_value=False)
    def test_non_retryable_error_stops_immediately(self, mock_cancelled, mock_audit):
        step = {'step_id': 's1', 'order': 1, 'retry_enabled': True, 'retry_max_attempts': 3}
        execute_fn = MagicMock(return_value=StepResult(
            outcome=StepOutcome.ERROR,
            error_message="Validation error: bad input",
        ))
        counter = [0]
        def counter_fn():
            counter[0] += 1
            return counter[0]

        result = self.handler.execute_with_retry(step, execute_fn, counter_fn)

        assert result.is_error
        execute_fn.assert_called_once()
        from core.models import AuditActionType
        mock_audit.assert_called_once()
        call_kwargs = mock_audit.call_args[1]
        assert call_kwargs['action_type'] == AuditActionType.EXECUTION_STEP_RETRY_ABORTED


# ---------------------------------------------------------------------------
# execute_with_retry — exécution annulée
# ---------------------------------------------------------------------------

class TestExecuteWithRetryCancelled(TransactionTestCase):
    """Tests execute_with_retry — exécution annulée avant premier essai."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory(item_type="workflow")
        from executions.models import Execution, ExecutionStatus
        self.execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.SUBMITTED,
        )
        self.handler = _make_handler(self.execution)

    @patch("executions.cancellation_cache.is_cancelled", return_value=True)
    def test_cancelled_returns_error_without_calling_execute_fn(self, mock_cancelled):
        step = {
            'step_id': 's1', 'name': 'Step One', 'order': 1,
            'retry_enabled': True, 'retry_max_attempts': 3,
        }
        execute_fn = MagicMock()
        counter = [0]
        def counter_fn():
            counter[0] += 1
            return counter[0]

        result = self.handler.execute_with_retry(step, execute_fn, counter_fn)

        assert result.is_error
        assert "cancelled" in result.error_message.lower()
        execute_fn.assert_not_called()

        from executions.models import ExecutionStep, ExecutionStepStatus
        step_record = ExecutionStep.objects.filter(execution=self.execution).first()
        assert step_record is not None
        assert step_record.status == ExecutionStepStatus.FAILED
        assert "cancelled" in step_record.error_message.lower()


# ---------------------------------------------------------------------------
# execute_with_retry — Celery retry planifié
# ---------------------------------------------------------------------------

class TestExecuteWithRetryCeleryScheduled(TransactionTestCase):
    """Tests execute_with_retry — retry Celery planifié après premier échec temporaire."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory(item_type="workflow")
        from executions.models import Execution, ExecutionStatus
        self.execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.SUBMITTED,
        )
        self.handler = _make_handler(self.execution)

    @patch("executions.workflow_retry.AuditService.create_entry")
    @patch("executions.cancellation_cache.is_cancelled", return_value=False)
    def test_temporary_error_schedules_celery_retry(self, mock_cancelled, mock_audit):
        step = {
            'step_id': 's1', 'order': 1,
            'retry_enabled': True, 'retry_max_attempts': 3, 'retry_interval_seconds': 30,
        }
        execute_fn = MagicMock(return_value=StepResult(
            outcome=StepOutcome.ERROR,
            error_message="Connection timeout",  # retryable
        ))
        counter = [0]
        def counter_fn():
            counter[0] += 1
            return counter[0]

        with patch("executions.tasks.retry_workflow_step") as mock_celery_task:
            mock_celery_task.apply_async = MagicMock()
            result = self.handler.execute_with_retry(step, execute_fn, counter_fn)

        assert result.is_error
        assert result.error_details.get('retry_scheduled') is True
        assert result.error_details.get('next_attempt') == 2

        mock_celery_task.apply_async.assert_called_once()
        call_args = mock_celery_task.apply_async.call_args
        assert call_args.kwargs['countdown'] == 30
        assert call_args.kwargs['args'][0] == self.execution.id

        from core.models import AuditActionType
        audit_types = [c[1]['action_type'] for c in mock_audit.call_args_list]
        assert AuditActionType.EXECUTION_STEP_RETRY_ATTEMPT in audit_types
