"""
Integration tests for evaluate_waiting_gates Celery task — Story 25.3 AC12

Tests:
- No WAITING steps → task completes without error
- WAITING step + conditions satisfied → RUNNING + audit trail
- WAITING step + conditions NOT satisfied → stays WAITING + output updated
- WAITING step + timeout expired → FAILED/SKIPPED + audit trail
- Parent execution COMPLETED → WAITING step NOT processed
- GateEvaluator error → step skipped, task continues
"""

import pytest
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.test import override_settings

from django.utils import timezone

from executions.models import (
    ExecutionStepStatus,
)
from executions.gate_evaluator import GateEvaluator
from executions.tasks import evaluate_waiting_gates
from core.models import AuditActionType, AuditLog
from tests.factories import (
    ExecutionFactory,
    ExecutionStepFactory,
    ExecutionTargetFactory,
)


def _create_waiting_step(gate_conditions, execution_status='RUNNING', created_at=None):
    """Create an ExecutionStep in WAITING status with gate_conditions."""
    execution = ExecutionFactory(status=execution_status)
    step = ExecutionStepFactory(
        execution=execution,
        status=ExecutionStepStatus.WAITING,
    )
    step.set_output({
        'waiting_since': timezone.now().isoformat(),
        'gate_conditions': gate_conditions,
        'gate_status': [
            {'type': c['type'], 'satisfied': False, 'reason': "En attente"}
            for c in gate_conditions
        ],
    })
    if created_at:
        step.created_at = created_at
    step.save()
    return step


@pytest.mark.django_db
class TestEvaluateWaitingGatesTask:
    """Integration tests for the evaluate_waiting_gates Celery task."""

    def test_no_waiting_steps_completes_without_error(self):
        """AC12: No WAITING steps → task completes without error."""
        result = evaluate_waiting_gates()

        assert result['waiting_steps'] == 0
        assert result['unblocked'] == 0
        assert result['still_waiting'] == 0
        assert result['errors'] == 0

    def test_waiting_step_satisfied_transitions_to_running(self):
        """AC12: WAITING step + satisfied → RUNNING + audit trail."""
        step = _create_waiting_step([{'type': 'maintenance_window'}])
        ExecutionTargetFactory(execution=step.execution, target_id='SERVER1')

        with patch.object(
            GateEvaluator,
            'evaluate',
            return_value=(True, {
                'gates': [{'type': 'maintenance_window', 'satisfied': True}],
                'timeout_triggered': False,
            }),
        ):
            with patch('executions.tasks.gates.resume_container_workflow_from_gate') as mock_resume:
                mock_resume.apply_async = MagicMock()
                result = evaluate_waiting_gates()

        assert result['unblocked'] == 1
        assert result['still_waiting'] == 0

        step.refresh_from_db()
        assert step.status == ExecutionStepStatus.RUNNING
        assert step.started_at is not None

        # Verify audit trail
        audit = AuditLog.objects.filter(
            action_type=AuditActionType.EXECUTION_STEP_GATE_SATISFIED,
            entity_id=step.execution_id,
        )
        assert audit.exists()

    def test_waiting_step_not_satisfied_stays_waiting(self):
        """AC12: WAITING step + NOT satisfied → stays WAITING + output updated."""
        step = _create_waiting_step([{'type': 'maintenance_window'}])

        next_start = timezone.now() + timedelta(hours=3)
        with patch.object(
            GateEvaluator,
            'evaluate',
            return_value=(False, {
                'gates': [{
                    'type': 'maintenance_window',
                    'satisfied': False,
                    'reason': 'Outside window',
                    'next_possible_at': next_start.isoformat(),
                }],
                'timeout_triggered': False,
            }),
        ):
            result = evaluate_waiting_gates()

        assert result['still_waiting'] == 1
        assert result['unblocked'] == 0

        step.refresh_from_db()
        assert step.status == ExecutionStepStatus.WAITING

        output = step.get_output()
        assert 'last_evaluated_at' in output

    def test_waiting_step_timeout_fail(self):
        """AC12: WAITING step + timeout → FAILED + audit trail."""
        created_at = timezone.now() - timedelta(hours=50)
        step = _create_waiting_step(
            [{'type': 'maintenance_window', 'timeout_hours': 48, 'on_timeout': 'FAIL'}],
            created_at=created_at,
        )

        with patch.object(
            GateEvaluator,
            'evaluate',
            return_value=(False, {
                'gates': [],
                'timeout_triggered': True,
                'action': 'FAILED',
                'timeout_hours': 48,
            }),
        ):
            result = evaluate_waiting_gates()

        assert result['errors'] == 1  # Timeout counts as processed

        step.refresh_from_db()
        assert step.status == ExecutionStepStatus.FAILED
        assert step.completed_at is not None

        # Verify timeout audit trail
        audit = AuditLog.objects.filter(
            action_type=AuditActionType.EXECUTION_STEP_GATE_TIMEOUT,
            entity_id=step.execution_id,
        )
        assert audit.exists()

    def test_waiting_step_timeout_skip(self):
        """AC12: WAITING step + timeout + on_timeout=SKIP → SKIPPED."""
        created_at = timezone.now() - timedelta(hours=50)
        step = _create_waiting_step(
            [{'type': 'maintenance_window', 'timeout_hours': 48, 'on_timeout': 'SKIP'}],
            created_at=created_at,
        )

        with patch.object(
            GateEvaluator,
            'evaluate',
            return_value=(False, {
                'gates': [],
                'timeout_triggered': True,
                'action': 'SKIPPED',
                'timeout_hours': 48,
            }),
        ):
            evaluate_waiting_gates()

        step.refresh_from_db()
        assert step.status == ExecutionStepStatus.SKIPPED

    def test_parent_execution_completed_not_processed(self):
        """AC12: Parent execution COMPLETED → WAITING step NOT selected."""
        step = _create_waiting_step(
            [{'type': 'maintenance_window'}],
            execution_status='COMPLETED',
        )

        result = evaluate_waiting_gates()

        # Step should NOT be processed (filter: execution.status=RUNNING)
        assert result['waiting_steps'] == 0

        step.refresh_from_db()
        assert step.status == ExecutionStepStatus.WAITING  # Unchanged

    def test_evaluator_error_step_skipped_task_continues(self):
        """AC12: GateEvaluator error → step skipped, task continues."""
        _create_waiting_step([{'type': 'maintenance_window'}])
        _create_waiting_step([{'type': 'maintenance_window'}])

        call_count = [0]

        def mock_evaluate(self_eval, step):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("Unexpected error")
            return (True, {
                'gates': [{'type': 'maintenance_window', 'satisfied': True}],
                'timeout_triggered': False,
            })

        with patch.object(GateEvaluator, 'evaluate', mock_evaluate):
            with patch('executions.tasks.gates.resume_container_workflow_from_gate') as mock_resume:
                mock_resume.apply_async = MagicMock()
                result = evaluate_waiting_gates()

        # One errored, one unblocked
        assert result['errors'] == 1
        assert result['unblocked'] == 1

    def test_multiple_waiting_steps_all_processed(self):
        """Multiple WAITING steps are all evaluated in one pass."""
        _create_waiting_step([{'type': 'maintenance_window'}])
        _create_waiting_step([{'type': 'maintenance_window'}])
        _create_waiting_step([{'type': 'maintenance_window'}])

        with patch.object(
            GateEvaluator,
            'evaluate',
            return_value=(False, {
                'gates': [{'type': 'maintenance_window', 'satisfied': False, 'reason': 'Waiting'}],
                'timeout_triggered': False,
            }),
        ):
            result = evaluate_waiting_gates()

        assert result['waiting_steps'] == 3
        assert result['still_waiting'] == 3

    def test_action_execution_steps_none_edge_case(self):
        """Story 25.3 code review LOW-3: Edge case action.execution_steps = None."""
        from tests.factories import ActionFactory

        # Use ActionFactory with execution_steps explicitly set to None
        action = ActionFactory(execution_steps=None)
        execution = ExecutionFactory(action=action, status='RUNNING')
        step = _create_waiting_step([{'type': 'maintenance_window'}])
        step.execution = execution
        step.save()

        with patch.object(
            GateEvaluator,
            'evaluate',
            return_value=(True, {
                'gates': [{'type': 'maintenance_window', 'satisfied': True}],
                'timeout_triggered': False,
            }),
        ):
            with patch('executions.tasks.gates.resume_container_workflow_from_gate') as mock_resume:
                mock_resume.apply_async = MagicMock()
                evaluate_waiting_gates()

        # Step transitions to RUNNING even though execution_steps is None
        step.refresh_from_db()
        assert step.status == ExecutionStepStatus.RUNNING

        # resume_container_workflow_from_gate may or may not be called depending on step_def.
        # Avec execution_steps=None, step_def=None → _resume_workflow_after_gate logue gate_resume_step_def_not_found.
        assert mock_resume.apply_async.call_count == 0


@pytest.mark.django_db
class TestGatePollingBackoff:
    """Story 86.3 — Tests unitaires du backoff exponentiel pour evaluate_waiting_gates."""

    def test_poll_attempt_incremented_after_unsatisfied_evaluation(self):
        """AC#7: Après _update_waiting_context, output['poll_attempt'] == 1."""
        step = _create_waiting_step([{'type': 'maintenance_window'}])

        with patch.object(
            GateEvaluator,
            'evaluate',
            return_value=(False, {'gates': [], 'timeout_triggered': False}),
        ):
            result = evaluate_waiting_gates()

        assert result['still_waiting'] == 1
        step.refresh_from_db()
        output = step.get_output()
        assert output['poll_attempt'] == 1
        assert 'next_poll_at' in output

    @override_settings(GATE_BASE_POLL_INTERVAL=60, GATE_POLL_BACKOFF_FACTOR=2.0, GATE_MAX_POLL_INTERVAL=120)
    def test_next_poll_at_computed_from_backoff_formula(self):
        """AC#6 + AC#7: Vérifier les intervalles pour poll_attempt=0 (60s) et poll_attempt=1 (120s cap)."""
        from executions.tasks.gates import _update_waiting_context

        # poll_attempt=0 → interval = 60 * 2.0^0 = 60s
        step0 = _create_waiting_step([{'type': 'maintenance_window'}])
        before = timezone.now()
        _update_waiting_context(step0, {'gates': []}, None)
        after = timezone.now()

        step0.refresh_from_db()
        output0 = step0.get_output()
        from datetime import datetime, timezone as dt_timezone
        npa0 = datetime.fromisoformat(output0['next_poll_at'])
        if npa0.tzinfo is None:
            npa0 = npa0.replace(tzinfo=dt_timezone.utc)
        assert before + timedelta(seconds=55) <= npa0 <= after + timedelta(seconds=65)
        assert output0['poll_attempt'] == 1

        # poll_attempt=1 → interval = 60 * 2.0^1 = 120s = MAX
        step1 = _create_waiting_step([{'type': 'maintenance_window'}])
        # Simuler un poll_attempt déjà à 1
        existing = step1.get_output() or {}
        existing['poll_attempt'] = 1
        step1.set_output(existing)
        step1.save()

        before2 = timezone.now()
        _update_waiting_context(step1, {'gates': []}, None)
        after2 = timezone.now()

        step1.refresh_from_db()
        output1 = step1.get_output()
        npa1 = datetime.fromisoformat(output1['next_poll_at'])
        if npa1.tzinfo is None:
            npa1 = npa1.replace(tzinfo=dt_timezone.utc)
        assert before2 + timedelta(seconds=115) <= npa1 <= after2 + timedelta(seconds=125)
        assert output1['poll_attempt'] == 2

    def test_step_skipped_when_next_poll_at_future(self):
        """AC#3 + AC#7: next_poll_at dans le futur → skipped=1, evaluate non appelé."""
        step = _create_waiting_step([{'type': 'maintenance_window'}])
        output = step.get_output() or {}
        output['next_poll_at'] = (timezone.now() + timedelta(seconds=300)).isoformat()
        step.set_output(output)
        step.save()

        with patch.object(GateEvaluator, 'evaluate') as mock_eval:
            result = evaluate_waiting_gates()

        assert result['skipped'] == 1
        mock_eval.assert_not_called()

    def test_step_evaluated_when_next_poll_at_past(self):
        """AC#3: next_poll_at dans le passé → évalué normalement."""
        step = _create_waiting_step([{'type': 'maintenance_window'}])
        output = step.get_output() or {}
        output['next_poll_at'] = (timezone.now() - timedelta(seconds=60)).isoformat()
        step.set_output(output)
        step.save()

        with patch.object(
            GateEvaluator,
            'evaluate',
            return_value=(False, {'gates': [], 'timeout_triggered': False}),
        ):
            result = evaluate_waiting_gates()

        assert result['skipped'] == 0
        assert result['still_waiting'] == 1

    def test_step_evaluated_when_no_next_poll_at(self):
        """AC#3: Pas de next_poll_at (premier passage) → évalué normalement."""
        step = _create_waiting_step([{'type': 'maintenance_window'}])
        # S'assurer qu'aucun next_poll_at n'est présent
        output = step.get_output() or {}
        output.pop('next_poll_at', None)
        step.set_output(output)
        step.save()

        with patch.object(
            GateEvaluator,
            'evaluate',
            return_value=(False, {'gates': [], 'timeout_triggered': False}),
        ):
            result = evaluate_waiting_gates()

        assert result['skipped'] == 0
        assert result['still_waiting'] == 1

    def test_invalid_next_poll_at_evaluates_anyway(self):
        """AC#3: next_poll_at invalide → évalué normalement, pas d'exception."""
        step = _create_waiting_step([{'type': 'maintenance_window'}])
        output = step.get_output() or {}
        output['next_poll_at'] = 'not-a-date'
        step.set_output(output)
        step.save()

        with patch.object(
            GateEvaluator,
            'evaluate',
            return_value=(False, {'gates': [], 'timeout_triggered': False}),
        ):
            result = evaluate_waiting_gates()

        assert result['skipped'] == 0
        assert result['still_waiting'] == 1

    @override_settings(GATE_BASE_POLL_INTERVAL=10, GATE_POLL_BACKOFF_FACTOR=2.0, GATE_MAX_POLL_INTERVAL=50)
    def test_max_poll_interval_capped(self):
        """AC#6 + AC#7: poll_attempt=10 → interval plafonné à MAX=50s."""
        from executions.tasks.gates import _update_waiting_context

        step = _create_waiting_step([{'type': 'maintenance_window'}])
        existing = step.get_output() or {}
        existing['poll_attempt'] = 10
        step.set_output(existing)
        step.save()

        before = timezone.now()
        _update_waiting_context(step, {'gates': []}, None)
        after = timezone.now()

        step.refresh_from_db()
        output = step.get_output()
        from datetime import datetime, timezone as dt_timezone
        npa = datetime.fromisoformat(output['next_poll_at'])
        if npa.tzinfo is None:
            npa = npa.replace(tzinfo=dt_timezone.utc)
        # Interval should be capped at 50s
        assert before + timedelta(seconds=45) <= npa <= after + timedelta(seconds=55)

    def test_skipped_counter_in_return_dict(self):
        """AC#4: Deux steps WAITING (l'un en backoff, l'autre non) → skipped=1, still_waiting=1."""
        # Step avec next_poll_at dans le futur
        step_future = _create_waiting_step([{'type': 'maintenance_window'}])
        output_f = step_future.get_output() or {}
        output_f['next_poll_at'] = (timezone.now() + timedelta(seconds=300)).isoformat()
        step_future.set_output(output_f)
        step_future.save()

        # Step sans next_poll_at (premier passage)
        _create_waiting_step([{'type': 'maintenance_window'}])

        with patch.object(
            GateEvaluator,
            'evaluate',
            return_value=(False, {'gates': [], 'timeout_triggered': False}),
        ):
            result = evaluate_waiting_gates()

        assert result['skipped'] == 1
        assert result['still_waiting'] == 1

    def test_settings_validation_invalid_base_poll_interval(self):
        """AC#1: GATE_BASE_POLL_INTERVAL invalide → ImproperlyConfigured.

        On patche l'env var pour éviter que la valeur réelle de l'environnement
        CI ne rende le test non-déterministe.
        """
        from unittest.mock import patch
        from django.core.exceptions import ImproperlyConfigured
        from idp_backend.settings import _parse_gate_poll_setting

        with patch.dict('os.environ', {'GATE_BASE_POLL_INTERVAL': '-1'}):
            with pytest.raises(ImproperlyConfigured):
                _parse_gate_poll_setting('GATE_BASE_POLL_INTERVAL', '30')

    def test_poll_attempt_persisted_across_multiple_calls_stable_gate_status(self):
        """Régression HIGH-1: poll_attempt doit être persisté à chaque appel de
        _update_waiting_context, même si gate_status est identique entre deux appels
        (scénario output_changed=False avant fix).

        Sans le fix, poll_attempt restait bloqué à 1 après la première évaluation stable,
        et next_poll_at n'était jamais avancé → le skip logic ne fonctionnait plus.
        """
        from executions.tasks.gates import _update_waiting_context

        step = _create_waiting_step([{'type': 'maintenance_window'}])

        stable_gate_status = {
            'gates': [{'type': 'maintenance_window', 'satisfied': False, 'reason': 'Outside window'}],
        }

        # Appel #1 : gate_status change (initial → évaluation) → output_changed=True → sauvegarde OK
        _update_waiting_context(step, stable_gate_status, None)
        step.refresh_from_db()
        assert step.get_output()['poll_attempt'] == 1, "poll_attempt doit être 1 après le 1er appel"

        # Appel #2 : gate_status identique → avant fix: output_changed=False → poll_attempt NON sauvegardé
        _update_waiting_context(step, stable_gate_status, None)
        step.refresh_from_db()
        output = step.get_output()
        assert output['poll_attempt'] == 2, (
            "poll_attempt doit être 2 après le 2ème appel, même si gate_status est stable "
            "(régression HIGH-1 : if output_changed empêchait la sauvegarde du backoff state)"
        )

        # Appel #3 : idem
        _update_waiting_context(step, stable_gate_status, None)
        step.refresh_from_db()
        assert step.get_output()['poll_attempt'] == 3, "poll_attempt doit progresser à chaque appel"

    @override_settings(GATE_BASE_POLL_INTERVAL=10)
    def test_base_poll_interval_override_settings(self):
        """AC#7: override_settings(GATE_BASE_POLL_INTERVAL=10) → intervalle calculé = 10s pour poll_attempt=0."""
        from executions.tasks.gates import _update_waiting_context

        step = _create_waiting_step([{'type': 'maintenance_window'}])
        before = timezone.now()
        _update_waiting_context(step, {'gates': []}, None)
        after = timezone.now()

        step.refresh_from_db()
        output = step.get_output()
        from datetime import datetime, timezone as dt_timezone
        npa = datetime.fromisoformat(output['next_poll_at'])
        if npa.tzinfo is None:
            npa = npa.replace(tzinfo=dt_timezone.utc)
        assert before + timedelta(seconds=5) <= npa <= after + timedelta(seconds=15)
