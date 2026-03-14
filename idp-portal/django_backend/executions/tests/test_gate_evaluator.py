"""
Unit tests for GateEvaluator — Story 25.3 AC11

Tests:
- maintenance_window: all targets in window → satisfied
- maintenance_window: one target outside window → NOT satisfied + next_possible_at
- timeout: elapsed > timeout_hours + on_timeout='FAIL' → FAILED
- timeout: elapsed > timeout_hours + on_timeout='SKIP' → SKIPPED
- Multiple conditions: all satisfied → True
- Multiple conditions: one NOT satisfied → False
- InventoryService error → condition NOT satisfied
"""

import json
import pytest
from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone

from executions.gate_evaluator import GateEvaluator
from executions.models import ExecutionStepStatus
from inventory.services import InventoryService, InventoryServiceError
from tests.factories import (
    ExecutionFactory,
    ExecutionStepFactory,
    ExecutionTargetFactory,
)


def _create_waiting_step(gate_conditions, created_at=None, requires_maintenance_window=True):
    """Helper: create an ExecutionStep in WAITING with gate_conditions in output."""
    # Set up execution parameters with _env_config to control gate evaluation
    params = {
        "target_host": "db-test-01.example.com",
        "database_name": "TESTDB",
        "_env_config": {
            "requires_maintenance_window": requires_maintenance_window,
            "requires_approval": False,
        }
    }
    execution = ExecutionFactory(status='RUNNING', parameters=json.dumps(params))
    step = ExecutionStepFactory(
        execution=execution,
        status=ExecutionStepStatus.WAITING,
    )
    step.set_output({
        'waiting_since': timezone.now().isoformat(),
        'gate_conditions': gate_conditions,
        'gate_status': [
            {'type': c['type'], 'satisfied': False, 'reason': "En attente d'évaluation"}
            for c in gate_conditions
        ],
    })
    if created_at:
        step.created_at = created_at
    step.save()
    return step


@pytest.mark.django_db
class TestGateEvaluatorMaintenanceWindow:
    """Test _check_maintenance_window."""

    def test_all_targets_in_window_satisfied(self):
        """AC11: All targets in maintenance window → satisfied=True."""
        step = _create_waiting_step([
            {'type': 'maintenance_window', 'description': 'Wait for maintenance window'}
        ])
        ExecutionTargetFactory(execution=step.execution, target_id='SERVER1')
        ExecutionTargetFactory(execution=step.execution, target_id='SERVER2')

        with patch.object(
            InventoryService,
            'get_next_maintenance_window',
            return_value={'is_active': True, 'start': None, 'end': None},
        ):
            evaluator = GateEvaluator()
            satisfied, gate_status = evaluator.evaluate(step)

        assert satisfied is True
        assert gate_status['timeout_triggered'] is False
        assert gate_status['gates'][0]['type'] == 'maintenance_window'
        assert gate_status['gates'][0]['satisfied'] is True

    def test_one_target_outside_window_not_satisfied(self):
        """AC11: One target outside window → satisfied=False + next_possible_at."""
        step = _create_waiting_step([{'type': 'maintenance_window'}])
        ExecutionTargetFactory(execution=step.execution, target_id='SERVER1')
        ExecutionTargetFactory(execution=step.execution, target_id='SERVER2')

        next_start = timezone.now() + timedelta(hours=2)

        def mock_get_window(target_id):
            if target_id == 'SERVER1':
                return {'is_active': True, 'start': None, 'end': None}
            return {
                'is_active': False,
                'start': next_start,
                'end': next_start + timedelta(hours=4),
            }

        with patch.object(
            InventoryService,
            'get_next_maintenance_window',
            side_effect=mock_get_window,
        ):
            evaluator = GateEvaluator()
            satisfied, gate_status = evaluator.evaluate(step)

        assert satisfied is False
        assert gate_status['gates'][0]['satisfied'] is False
        assert 'next_possible_at' in gate_status['gates'][0]

    def test_no_targets_always_satisfied(self):
        """No ExecutionTargets → maintenance_window satisfied by default."""
        step = _create_waiting_step([{'type': 'maintenance_window'}], requires_maintenance_window=True)
        # No targets created

        evaluator = GateEvaluator()
        satisfied, gate_status = evaluator.evaluate(step)

        assert satisfied is True

    def test_no_maintenance_window_defined_not_satisfied(self):
        """
        Story 25.3 code review HIGH-3: get_next_maintenance_window returns None → NOT satisfied (fail-safe).

        Rationale: maintenance_window gates are security controls for PROD changes.
        If inventory doesn't define a window, safer to block than to allow.
        """
        step = _create_waiting_step([{'type': 'maintenance_window'}])
        ExecutionTargetFactory(execution=step.execution, target_id='SERVER1')

        with patch.object(
            InventoryService,
            'get_next_maintenance_window',
            return_value=None,
        ):
            evaluator = GateEvaluator()
            satisfied, gate_status = evaluator.evaluate(step)

        # Changed expectation: None → NOT satisfied (block by default)
        assert satisfied is False
        # Verify target details show the blocked state
        target_details = gate_status['gates'][0]['details'][0]
        assert target_details['is_active'] is False
        assert 'No maintenance window configured' in target_details['reason']

    def test_inventory_service_error_not_satisfied(self):
        """AC11: InventoryService error → condition NOT satisfied."""
        step = _create_waiting_step([{'type': 'maintenance_window'}])
        ExecutionTargetFactory(execution=step.execution, target_id='SERVER1')

        with patch.object(
            InventoryService,
            'get_next_maintenance_window',
            side_effect=InventoryServiceError("Service down"),
        ):
            evaluator = GateEvaluator()
            satisfied, gate_status = evaluator.evaluate(step)

        assert satisfied is False
        assert 'Inventory service error' in gate_status['gates'][0]['details'][0]['reason']


@pytest.mark.django_db
class TestGateEvaluatorTimeout:
    """Test timeout handling."""

    def test_timeout_triggered_fail(self):
        """AC11: Timeout exceeded + on_timeout='FAIL' → timeout_triggered, action=FAILED."""
        created_at = timezone.now() - timedelta(hours=50)
        step = _create_waiting_step(
            [{'type': 'maintenance_window', 'timeout_hours': 48, 'on_timeout': 'FAIL'}],
            created_at=created_at,
        )

        evaluator = GateEvaluator()
        satisfied, gate_status = evaluator.evaluate(step)

        assert satisfied is False
        assert gate_status['timeout_triggered'] is True
        assert gate_status['action'] == 'FAILED'

    def test_timeout_triggered_skip(self):
        """AC11: Timeout exceeded + on_timeout='SKIP' → timeout_triggered, action=SKIPPED."""
        created_at = timezone.now() - timedelta(hours=50)
        step = _create_waiting_step(
            [{'type': 'maintenance_window', 'timeout_hours': 48, 'on_timeout': 'SKIP'}],
            created_at=created_at,
        )

        evaluator = GateEvaluator()
        satisfied, gate_status = evaluator.evaluate(step)

        assert satisfied is False
        assert gate_status['timeout_triggered'] is True
        assert gate_status['action'] == 'SKIPPED'

    def test_timeout_not_yet_triggered(self):
        """Timeout NOT exceeded → normal evaluation continues."""
        step = _create_waiting_step(
            [{'type': 'maintenance_window', 'timeout_hours': 48, 'on_timeout': 'FAIL'}],
        )
        # Step just created, not yet 48h old
        ExecutionTargetFactory(execution=step.execution, target_id='SERVER1')

        with patch.object(
            InventoryService,
            'get_next_maintenance_window',
            return_value={'is_active': True, 'start': None, 'end': None},
        ):
            evaluator = GateEvaluator()
            satisfied, gate_status = evaluator.evaluate(step)

        assert satisfied is True
        assert gate_status['timeout_triggered'] is False

    def test_timeout_default_action_is_fail(self):
        """Timeout with no on_timeout specified defaults to FAILED."""
        created_at = timezone.now() - timedelta(hours=50)
        step = _create_waiting_step(
            [{'type': 'maintenance_window', 'timeout_hours': 48}],
            created_at=created_at,
        )

        evaluator = GateEvaluator()
        satisfied, gate_status = evaluator.evaluate(step)

        assert gate_status['timeout_triggered'] is True
        assert gate_status['action'] == 'FAILED'


@pytest.mark.django_db
class TestGateEvaluatorMultipleConditions:
    """Test multiple gate conditions."""

    def test_all_conditions_satisfied(self):
        """AC11: Multiple conditions, all satisfied → all_satisfied=True."""
        step = _create_waiting_step([
            {'type': 'maintenance_window'},
            {'type': 'maintenance_window'},
        ])
        ExecutionTargetFactory(execution=step.execution, target_id='SERVER1')

        with patch.object(
            InventoryService,
            'get_next_maintenance_window',
            return_value={'is_active': True, 'start': None, 'end': None},
        ):
            evaluator = GateEvaluator()
            satisfied, gate_status = evaluator.evaluate(step)

        assert satisfied is True
        assert len(gate_status['gates']) == 2
        assert all(g['satisfied'] for g in gate_status['gates'])

    def test_one_condition_not_satisfied(self):
        """AC11: Multiple conditions, one NOT satisfied → all_satisfied=False."""
        step = _create_waiting_step([
            {'type': 'maintenance_window'},
            {'type': 'maintenance_window'},
        ])
        ExecutionTargetFactory(execution=step.execution, target_id='SERVER1')

        call_count = [0]
        next_start = timezone.now() + timedelta(hours=2)

        def mock_alternating(target_id):
            call_count[0] += 1
            if call_count[0] <= 1:
                return {'is_active': True, 'start': None, 'end': None}
            return {'is_active': False, 'start': next_start, 'end': next_start + timedelta(hours=4)}

        with patch.object(
            InventoryService,
            'get_next_maintenance_window',
            side_effect=mock_alternating,
        ):
            evaluator = GateEvaluator()
            satisfied, gate_status = evaluator.evaluate(step)

        assert satisfied is False

    def test_no_gate_conditions_in_output(self):
        """Step with no gate_conditions in output → all_satisfied=True."""
        execution = ExecutionFactory(status='RUNNING')
        step = ExecutionStepFactory(
            execution=execution,
            status=ExecutionStepStatus.WAITING,
        )
        step.set_output({'some_other_key': 'value'})
        step.save()

        evaluator = GateEvaluator()
        satisfied, gate_status = evaluator.evaluate(step)

        assert satisfied is True
        assert gate_status['gates'] == []

    def test_unsupported_gate_type_not_satisfied(self):
        """Unsupported gate types are NOT satisfied."""
        step = _create_waiting_step([
            {'type': 'unsupported_future_gate'},
        ], requires_maintenance_window=False)

        evaluator = GateEvaluator()
        satisfied, gate_status = evaluator.evaluate(step)

        assert satisfied is False
        assert 'Unsupported gate type' in gate_status['gates'][0]['reason']


# =============================================================================
# Migré depuis test_condition_gates.py (AC5) — Epic 81 PR4
# =============================================================================


class TestValidateGateConditionsMigrated:
    """
    Tests minimaux de validate_gate_conditions migrés depuis test_condition_gates.py.
    Couvre le schéma valide et invalide (2 cas requis par AC2/AC3).
    """

    def test_valid_gate_condition_passes(self):
        """Condition valide (type maintenance_window) ne lève pas d'exception."""
        from catalog.validators import validate_gate_conditions
        validate_gate_conditions([{'type': 'maintenance_window', 'timeout_hours': 48, 'on_timeout': 'FAIL'}])

    def test_invalid_gate_condition_raises_validation_error(self):
        """Condition sans 'type' lève ValidationError."""
        from catalog.validators import validate_gate_conditions
        from rest_framework.exceptions import ValidationError
        with pytest.raises(ValidationError):
            validate_gate_conditions([{'description': 'missing type field'}])
