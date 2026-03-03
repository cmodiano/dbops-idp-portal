"""
Tests unitaires pour StepExecutor._execute_schedule_step() (Story 57.15).

Couvre tous les AC : sources de date (parameter/fixed_offset/recurring),
inherit_parameters, parameter_mapping JSONPath, correlation_id, audit, output,
gestion des erreurs.
"""
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TransactionTestCase
from django.utils import timezone

from executions.workflow_step_executor import StepExecutor
from tests.factories import UserFactory, ActionFactory


def _make_execution(user, action, environment='dev'):
    """Crée une Execution en état RUNNING pour les tests."""
    from executions.models import Execution, ExecutionStatus
    return Execution.objects.create(
        action=action,
        user=user,
        environment=environment,
        status=ExecutionStatus.RUNNING,
    )


def _make_mock_scheduled_execution(exec_id=42):
    """Retourne un mock de ScheduledExecution."""
    se = MagicMock()
    se.id = exec_id
    se.correlation_id = None
    return se


# ---------------------------------------------------------------------------
# Test happy path — schedule_source: parameter
# ---------------------------------------------------------------------------

class TestScheduleStepParameterSource(TransactionTestCase):
    """AC #1, #2, #7 — source parameter, happy path."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory(item_type='workflow')
        self.execution = _make_execution(self.user, self.action)
        self.executor = StepExecutor(self.execution, 'test-corr-schedule')

    @patch('executions.workflow_step_executor.AuditService.create_entry')
    def test_schedule_step_creates_scheduled_execution(self, mock_audit):
        """AC #1 + #2 — happy path avec source=parameter, crée ScheduledExecution."""
        target_action = ActionFactory(status='published')
        mock_se = _make_mock_scheduled_execution(99)

        scheduled_at_str = '2026-06-01T10:00:00'

        step = {
            'step_id': 'schedule-step-1',
            'name': 'Schedule Step',
            'order': 1,
            'step_type': 'schedule_execution',
            'referenced_action_id': target_action.id,
            'schedule_config': {
                'schedule_source': 'parameter',
                'schedule_parameter_name': 'scheduled_at',
            },
        }

        with patch('catalog.models.Action.objects') as mock_qs, \
             patch('executions.scheduling_service.SchedulingService.create_scheduled_execution',
                   return_value=mock_se) as mock_create:
            mock_qs.get.return_value = target_action

            result = self.executor.execute(
                step, step_order=1,
                step_parameters={'scheduled_at': scheduled_at_str}
            )

        from executions.workflow_runtime import StepOutcome
        assert result.outcome == StepOutcome.SUCCESS
        assert result.output.get('scheduled_execution_id') == 99

        # Vérifier que ScheduledExecution a été créé
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs['action'] == target_action
        assert call_kwargs['environment'] == 'dev'

        # Vérifier audit
        mock_audit.assert_called()
        audit_call = mock_audit.call_args.kwargs
        from core.models import AuditActionType
        assert audit_call['action_type'] == AuditActionType.WORKFLOW_STEP_SCHEDULE_CREATED

    @patch('executions.workflow_step_executor.AuditService.create_entry')
    def test_schedule_step_output_contains_scheduled_exec_id(self, mock_audit):
        """AC #7 — step.output contient scheduled_execution_id."""
        target_action = ActionFactory(status='published')
        mock_se = _make_mock_scheduled_execution(77)

        step = {
            'step_id': 'sched-output',
            'name': 'Output Check',
            'order': 1,
            'step_type': 'schedule_execution',
            'referenced_action_id': target_action.id,
            'schedule_config': {
                'schedule_source': 'parameter',
                'schedule_parameter_name': 'scheduled_at',
            },
        }

        with patch('catalog.models.Action.objects') as mock_qs, \
             patch('executions.scheduling_service.SchedulingService.create_scheduled_execution',
                   return_value=mock_se):
            mock_qs.get.return_value = target_action

            self.executor.execute(
                step, step_order=1,
                step_parameters={'scheduled_at': '2026-06-01T10:00:00'}
            )

        from executions.models import ExecutionStep, ExecutionStepStatus
        step_record = ExecutionStep.objects.filter(execution=self.execution).first()
        assert step_record is not None
        assert step_record.status == ExecutionStepStatus.COMPLETED
        output = step_record.get_output()
        assert output.get('scheduled_execution_id') == 77


# ---------------------------------------------------------------------------
# Test fixed_offset source
# ---------------------------------------------------------------------------

class TestScheduleStepFixedOffsetSource(TransactionTestCase):
    """AC #3 — source fixed_offset."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory(item_type='workflow')
        self.execution = _make_execution(self.user, self.action)
        self.executor = StepExecutor(self.execution, 'test-corr-offset')

    @patch('executions.workflow_step_executor.AuditService.create_entry')
    def test_schedule_step_fixed_offset_source(self, mock_audit):
        """AC #3 — date calculée depuis offset +2d."""
        target_action = ActionFactory(status='published')
        mock_se = _make_mock_scheduled_execution(50)

        step = {
            'step_id': 'sched-offset',
            'name': 'Fixed Offset Step',
            'order': 1,
            'step_type': 'schedule_execution',
            'referenced_action_id': target_action.id,
            'schedule_config': {
                'schedule_source': 'fixed_offset',
                'fixed_offset': '+2d',
            },
        }

        captured_scheduled_at = {}

        def capture_create(**kwargs):
            captured_scheduled_at['val'] = kwargs.get('scheduled_at')
            return mock_se

        with patch('catalog.models.Action.objects') as mock_qs, \
             patch('executions.scheduling_service.SchedulingService.create_scheduled_execution',
                   side_effect=capture_create):
            mock_qs.get.return_value = target_action

            result = self.executor.execute(step, step_order=1, step_parameters={})

        from executions.workflow_runtime import StepOutcome
        assert result.outcome == StepOutcome.SUCCESS

        # Vérifier que la date est approximativement now + 2 jours
        sched_at = captured_scheduled_at.get('val')
        assert sched_at is not None
        expected_min = timezone.now() + timedelta(days=1, hours=23)
        expected_max = timezone.now() + timedelta(days=2, hours=1)
        assert expected_min <= sched_at <= expected_max


# ---------------------------------------------------------------------------
# Test recurring source
# ---------------------------------------------------------------------------

class TestScheduleStepRecurringSource(TransactionTestCase):
    """AC #4 — source recurring."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory(item_type='workflow')
        self.execution = _make_execution(self.user, self.action)
        self.executor = StepExecutor(self.execution, 'test-corr-recurring')

    @patch('executions.workflow_step_executor.AuditService.create_entry')
    def test_schedule_step_recurring_source(self, mock_audit):
        """AC #4 — RecurringPattern créé, scheduled_at=None."""
        target_action = ActionFactory(status='published')
        mock_se = _make_mock_scheduled_execution(60)

        step = {
            'step_id': 'sched-recurring',
            'name': 'Recurring Step',
            'order': 1,
            'step_type': 'schedule_execution',
            'referenced_action_id': target_action.id,
            'schedule_config': {
                'schedule_source': 'recurring',
                'recurring_pattern': {
                    'pattern_type': 'daily',
                    'pattern_config': {'hour': 9, 'minute': 0},
                },
            },
        }

        captured = {}

        def capture_create(**kwargs):
            captured['scheduled_at'] = kwargs.get('scheduled_at')
            captured['recurring_pattern_data'] = kwargs.get('recurring_pattern_data')
            return mock_se

        mock_next_date = timezone.now() + timedelta(days=1)

        with patch('catalog.models.Action.objects') as mock_qs, \
             patch('executions.scheduling_service.SchedulingService.create_scheduled_execution',
                   side_effect=capture_create), \
             patch('executions.utils.calculate_next_execution_date', return_value=mock_next_date):
            mock_qs.get.return_value = target_action

            result = self.executor.execute(step, step_order=1, step_parameters={})

        from executions.workflow_runtime import StepOutcome
        assert result.outcome == StepOutcome.SUCCESS
        assert captured.get('scheduled_at') is None
        assert captured.get('recurring_pattern_data') is not None
        assert captured['recurring_pattern_data']['pattern_type'] == 'daily'


# ---------------------------------------------------------------------------
# Test inherit_parameters
# ---------------------------------------------------------------------------

class TestScheduleStepInheritParameters(TransactionTestCase):
    """AC #5 — inherit_parameters."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory(item_type='workflow')
        self.execution = _make_execution(self.user, self.action)
        self.executor = StepExecutor(self.execution, 'test-corr-inherit')

    @patch('executions.workflow_step_executor.AuditService.create_entry')
    def test_schedule_step_inherit_parameters(self, mock_audit):
        """AC #5 — paramètres de l'exécution parent copiés (sauf workflow_step_parameters)."""
        target_action = ActionFactory(status='published')
        mock_se = _make_mock_scheduled_execution(70)

        # Simuler des paramètres sur l'exécution parent
        self.execution.set_parameters({
            'db_name': 'ORCL',
            'environment': 'prod',
            'workflow_step_parameters': {'1': {'parameters': {}}},  # doit être exclu
        })
        self.execution.save()

        step = {
            'step_id': 'sched-inherit',
            'name': 'Inherit Step',
            'order': 1,
            'step_type': 'schedule_execution',
            'referenced_action_id': target_action.id,
            'schedule_config': {
                'schedule_source': 'parameter',
                'schedule_parameter_name': 'scheduled_at',
                'inherit_parameters': True,
            },
        }

        captured = {}

        def capture_create(**kwargs):
            captured['parameters'] = kwargs.get('parameters')
            return mock_se

        with patch('catalog.models.Action.objects') as mock_qs, \
             patch('executions.scheduling_service.SchedulingService.create_scheduled_execution',
                   side_effect=capture_create):
            mock_qs.get.return_value = target_action

            self.executor.execute(
                step, step_order=1,
                step_parameters={'scheduled_at': '2026-06-01T10:00:00'}
            )

        params = captured.get('parameters') or {}
        assert params.get('db_name') == 'ORCL'
        assert params.get('environment') == 'prod'
        assert 'workflow_step_parameters' not in params


# ---------------------------------------------------------------------------
# Test parameter_mapping JSONPath
# ---------------------------------------------------------------------------

class TestScheduleStepParameterMapping(TransactionTestCase):
    """AC #6 — parameter_mapping JSONPath."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory(item_type='workflow')
        self.execution = _make_execution(self.user, self.action)
        self.executor = StepExecutor(self.execution, 'test-corr-jsonpath')

    @patch('executions.workflow_step_executor.AuditService.create_entry')
    def test_schedule_step_parameter_mapping_jsonpath(self, mock_audit):
        """AC #6 — JSONPath résolu depuis output d'un ExecutionStep précédent."""
        from executions.models import ExecutionStep, ExecutionStepStatus

        target_action = ActionFactory(status='published')
        mock_se = _make_mock_scheduled_execution(80)

        # Créer un ExecutionStep précédent avec output contenant snapshot_id
        prev_step = ExecutionStep.objects.create(
            execution=self.execution,
            step_order=1,
            step_name='prepare',
            step_type='platform',
            status=ExecutionStepStatus.COMPLETED,
            started_at=timezone.now(),
        )
        prev_step.set_output({'snapshot_id': 'snap-abc-123'})
        prev_step.save()

        step = {
            'step_id': 'sched-jsonpath',
            'name': 'JSONPath Step',
            'order': 2,
            'step_type': 'schedule_execution',
            'referenced_action_id': target_action.id,
            'schedule_config': {
                'schedule_source': 'parameter',
                'schedule_parameter_name': 'scheduled_at',
                'parameter_mapping': {
                    'snapshot_id': '$.steps.prepare.output.snapshot_id',
                },
            },
        }

        captured = {}

        def capture_create(**kwargs):
            captured['parameters'] = kwargs.get('parameters')
            return mock_se

        with patch('catalog.models.Action.objects') as mock_qs, \
             patch('executions.scheduling_service.SchedulingService.create_scheduled_execution',
                   side_effect=capture_create):
            mock_qs.get.return_value = target_action

            self.executor.execute(
                step, step_order=2,
                step_parameters={'scheduled_at': '2026-06-01T10:00:00'}
            )

        params = captured.get('parameters') or {}
        assert params.get('snapshot_id') == 'snap-abc-123'


# ---------------------------------------------------------------------------
# Test correlation_id propagé
# ---------------------------------------------------------------------------

class TestScheduleStepCorrelationId(TransactionTestCase):
    """AC #7 — correlation_id stocké sur ScheduledExecution."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory(item_type='workflow')
        self.execution = _make_execution(self.user, self.action)
        self.executor = StepExecutor(self.execution, 'corr-id-test-xyz')

    @patch('executions.workflow_step_executor.AuditService.create_entry')
    def test_schedule_step_correlation_id_propagated(self, mock_audit):
        """AC #7 — correlation_id assigné sur scheduled_execution."""
        target_action = ActionFactory(status='published')
        mock_se = _make_mock_scheduled_execution(90)

        step = {
            'step_id': 'sched-corr',
            'name': 'Corr Step',
            'order': 1,
            'step_type': 'schedule_execution',
            'referenced_action_id': target_action.id,
            'schedule_config': {
                'schedule_source': 'parameter',
                'schedule_parameter_name': 'scheduled_at',
            },
        }

        with patch('catalog.models.Action.objects') as mock_qs, \
             patch('executions.scheduling_service.SchedulingService.create_scheduled_execution',
                   return_value=mock_se):
            mock_qs.get.return_value = target_action

            self.executor.execute(
                step, step_order=1,
                step_parameters={'scheduled_at': '2026-06-01T10:00:00'}
            )

        assert mock_se.correlation_id == 'corr-id-test-xyz'
        mock_se.save.assert_called()


# ---------------------------------------------------------------------------
# Test fallback global params (_resolve_schedule_date AC #2)
# ---------------------------------------------------------------------------

class TestScheduleStepGlobalParamsFallback(TransactionTestCase):
    """AC #2 — fallback vers execution.get_parameters() quand param absent de step_parameters."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory(item_type='workflow')
        self.execution = _make_execution(self.user, self.action)
        self.executor = StepExecutor(self.execution, 'test-corr-fallback')

    @patch('executions.workflow_step_executor.AuditService.create_entry')
    def test_schedule_step_date_from_execution_global_params(self, mock_audit):
        """AC #2 — date récupérée depuis execution.get_parameters() si absente de step_parameters."""
        target_action = ActionFactory(status='published')
        mock_se = _make_mock_scheduled_execution(88)

        # Le paramètre scheduled_at est dans les params globaux de l'exécution, pas dans step_parameters
        self.execution.set_parameters({'scheduled_at': '2026-09-15T08:00:00'})
        self.execution.save()

        step = {
            'step_id': 'sched-fallback',
            'name': 'Fallback Step',
            'order': 1,
            'step_type': 'schedule_execution',
            'referenced_action_id': target_action.id,
            'schedule_config': {
                'schedule_source': 'parameter',
                'schedule_parameter_name': 'scheduled_at',
            },
        }

        captured = {}

        def capture_create(**kwargs):
            captured['scheduled_at'] = kwargs.get('scheduled_at')
            return mock_se

        with patch('catalog.models.Action.objects') as mock_qs, \
             patch('executions.scheduling_service.SchedulingService.create_scheduled_execution',
                   side_effect=capture_create):
            mock_qs.get.return_value = target_action

            result = self.executor.execute(step, step_order=1, step_parameters={})

        from executions.workflow_runtime import StepOutcome
        assert result.outcome == StepOutcome.SUCCESS
        # Vérifier que la date a bien été récupérée depuis les params globaux
        assert captured.get('scheduled_at') is not None


# ---------------------------------------------------------------------------
# Test erreurs
# ---------------------------------------------------------------------------

class TestScheduleStepErrors(TransactionTestCase):
    """AC #2 (missing/invalid param), #8 (exception → step FAILED)."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory(item_type='workflow')
        self.execution = _make_execution(self.user, self.action)
        self.executor = StepExecutor(self.execution, 'test-corr-errors')

    def test_schedule_step_missing_parameter_fails(self):
        """AC #2 — ValueError si paramètre de date absent."""
        target_action = ActionFactory(status='published')

        step = {
            'step_id': 'sched-missing',
            'name': 'Missing Param Step',
            'order': 1,
            'step_type': 'schedule_execution',
            'referenced_action_id': target_action.id,
            'schedule_config': {
                'schedule_source': 'parameter',
                'schedule_parameter_name': 'scheduled_at',
            },
        }

        with patch('catalog.models.Action.objects') as mock_qs:
            mock_qs.get.return_value = target_action

            result = self.executor.execute(step, step_order=1, step_parameters={})

        from executions.workflow_runtime import StepOutcome
        assert result.outcome == StepOutcome.ERROR
        assert 'scheduled_at' in result.error_message

        from executions.models import ExecutionStep, ExecutionStepStatus
        step_record = ExecutionStep.objects.filter(execution=self.execution).first()
        assert step_record.status == ExecutionStepStatus.FAILED

    def test_schedule_step_invalid_offset_fails(self):
        """AC #3 — ValueError si format offset invalide."""
        target_action = ActionFactory(status='published')

        step = {
            'step_id': 'sched-bad-offset',
            'name': 'Bad Offset Step',
            'order': 1,
            'step_type': 'schedule_execution',
            'referenced_action_id': target_action.id,
            'schedule_config': {
                'schedule_source': 'fixed_offset',
                'fixed_offset': 'invalid-offset',
            },
        }

        with patch('catalog.models.Action.objects') as mock_qs:
            mock_qs.get.return_value = target_action

            result = self.executor.execute(step, step_order=1, step_parameters={})

        from executions.workflow_runtime import StepOutcome
        assert result.outcome == StepOutcome.ERROR
        assert 'offset' in result.error_message.lower() or 'Format' in result.error_message

    def test_schedule_step_missing_action_fails(self):
        """AC #1 — ValueError si referenced_action_id inexistant."""
        from catalog.models import Action

        step = {
            'step_id': 'sched-no-action',
            'name': 'No Action Step',
            'order': 1,
            'step_type': 'schedule_execution',
            'referenced_action_id': 9999,
            'schedule_config': {
                'schedule_source': 'parameter',
                'schedule_parameter_name': 'scheduled_at',
            },
        }

        with patch('catalog.models.Action.objects') as mock_qs:
            mock_qs.get.side_effect = Action.DoesNotExist

            result = self.executor.execute(
                step, step_order=1,
                step_parameters={'scheduled_at': '2026-06-01T10:00:00'}
            )

        from executions.workflow_runtime import StepOutcome
        assert result.outcome == StepOutcome.ERROR
        assert '9999' in result.error_message

        from executions.models import ExecutionStep, ExecutionStepStatus
        step_record = ExecutionStep.objects.filter(execution=self.execution).first()
        assert step_record.status == ExecutionStepStatus.FAILED

    def test_schedule_step_exception_marks_step_failed(self):
        """AC #8 — exception quelconque → ExecutionStep FAILED, StepResult ERROR."""
        target_action = ActionFactory(status='published')

        step = {
            'step_id': 'sched-boom',
            'name': 'Boom Step',
            'order': 1,
            'step_type': 'schedule_execution',
            'referenced_action_id': target_action.id,
            'schedule_config': {
                'schedule_source': 'parameter',
                'schedule_parameter_name': 'scheduled_at',
            },
        }

        with patch('catalog.models.Action.objects') as mock_qs, \
             patch('executions.scheduling_service.SchedulingService.create_scheduled_execution',
                   side_effect=RuntimeError('unexpected error')):
            mock_qs.get.return_value = target_action

            result = self.executor.execute(
                step, step_order=1,
                step_parameters={'scheduled_at': '2026-06-01T10:00:00'}
            )

        from executions.workflow_runtime import StepOutcome
        assert result.outcome == StepOutcome.ERROR
        assert 'unexpected error' in result.error_message

        from executions.models import ExecutionStep, ExecutionStepStatus
        step_record = ExecutionStep.objects.filter(execution=self.execution).first()
        assert step_record.status == ExecutionStepStatus.FAILED


# ---------------------------------------------------------------------------
# Test audit entry
# ---------------------------------------------------------------------------

class TestScheduleStepAuditEntry(TransactionTestCase):
    """AC #7 — WORKFLOW_STEP_SCHEDULE_CREATED créé."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory(item_type='workflow')
        self.execution = _make_execution(self.user, self.action)
        self.executor = StepExecutor(self.execution, 'test-corr-audit')

    @patch('executions.workflow_step_executor.AuditService.create_entry')
    def test_schedule_step_creates_audit_entry(self, mock_audit):
        """AC #7 — entrée audit WORKFLOW_STEP_SCHEDULE_CREATED créée."""
        target_action = ActionFactory(status='published')
        mock_se = _make_mock_scheduled_execution(55)

        step = {
            'step_id': 'sched-audit',
            'name': 'Audit Step',
            'order': 1,
            'step_type': 'schedule_execution',
            'referenced_action_id': target_action.id,
            'schedule_config': {
                'schedule_source': 'parameter',
                'schedule_parameter_name': 'scheduled_at',
            },
        }

        with patch('catalog.models.Action.objects') as mock_qs, \
             patch('executions.scheduling_service.SchedulingService.create_scheduled_execution',
                   return_value=mock_se):
            mock_qs.get.return_value = target_action

            self.executor.execute(
                step, step_order=1,
                step_parameters={'scheduled_at': '2026-06-01T10:00:00'}
            )

        mock_audit.assert_called_once()
        from core.models import AuditActionType
        assert mock_audit.call_args.kwargs['action_type'] == AuditActionType.WORKFLOW_STEP_SCHEDULE_CREATED
        details = mock_audit.call_args.kwargs['details']
        assert details['scheduled_execution_id'] == 55


# ---------------------------------------------------------------------------
# Test routing via execute() — step_type dispatching
# ---------------------------------------------------------------------------

class TestScheduleStepRouting(TransactionTestCase):
    """AC #1 — routing step_type='schedule_execution' dans execute()."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory(item_type='workflow')
        self.execution = _make_execution(self.user, self.action)
        self.executor = StepExecutor(self.execution, 'test-corr-routing')

    @patch('executions.workflow_step_executor.StepExecutor._execute_schedule_step')
    def test_execute_routes_to_schedule_step(self, mock_handler):
        """step_type='schedule_execution' dans execute() → _execute_schedule_step() appelé."""
        from executions.workflow_runtime import StepResult, StepOutcome
        mock_handler.return_value = StepResult(outcome=StepOutcome.SUCCESS, output={})

        step = {
            'step_id': 'route-test',
            'name': 'Route Test',
            'order': 1,
            'step_type': 'schedule_execution',
            'referenced_action_id': 1,
            'schedule_config': {'schedule_source': 'parameter', 'schedule_parameter_name': 'x'},
        }

        result = self.executor.execute(step, step_order=1, step_parameters={})

        mock_handler.assert_called_once_with(step, 1, {})
        assert result.outcome == StepOutcome.SUCCESS
