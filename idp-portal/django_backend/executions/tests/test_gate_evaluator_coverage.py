"""
Tests complémentaires pour GateEvaluator — couverture des lignes manquantes.
Lignes cibles: 63->68, 69-75, 83-90, 96-103, 131-132, 138-143, 214->216, 267
"""
import json
import pytest
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.utils import timezone

from executions.gate_evaluator import GateEvaluator
from executions.models import ExecutionStepStatus
from inventory.services import InventoryService
from tests.factories import (
    ExecutionFactory,
    ExecutionStepFactory,
    ExecutionTargetFactory,
)


def _create_step_with_params(gate_conditions, params=None, created_at=None):
    """Helper: create an ExecutionStep with custom parameters."""
    execution = ExecutionFactory(
        status='RUNNING',
        parameters=json.dumps(params) if params else json.dumps({}),
    )
    step = ExecutionStepFactory(
        execution=execution,
        status=ExecutionStepStatus.WAITING,
    )
    step.set_output({
        'waiting_since': timezone.now().isoformat(),
        'gate_conditions': gate_conditions,
    })
    if created_at:
        step.created_at = created_at
    step.save()
    return step


@pytest.mark.django_db
class TestGateEvaluatorSchemaValidation:
    """Test schema validation — lignes 69-75, 83-90, 96-103."""

    def test_gate_conditions_not_list_returns_error(self):
        """Lignes 69-75: gate_conditions n'est pas une liste → False + error."""
        execution = ExecutionFactory(status='RUNNING')
        step = ExecutionStepFactory(
            execution=execution,
            status=ExecutionStepStatus.WAITING,
        )
        # gate_conditions est un dict, pas une liste
        step.set_output({'gate_conditions': {'type': 'maintenance_window'}})
        step.save()

        evaluator = GateEvaluator()
        satisfied, gate_status = evaluator.evaluate(step)

        assert satisfied is False
        assert 'error' in gate_status
        assert 'expected list' in gate_status['error']
        assert gate_status['gates'] == []

    def test_condition_not_dict_returns_error(self):
        """Lignes 83-90: une condition n'est pas un dict → False + error."""
        execution = ExecutionFactory(status='RUNNING')
        step = ExecutionStepFactory(
            execution=execution,
            status=ExecutionStepStatus.WAITING,
        )
        # Une condition est une chaîne, pas un dict
        step.set_output({'gate_conditions': ['maintenance_window']})
        step.save()

        evaluator = GateEvaluator()
        satisfied, gate_status = evaluator.evaluate(step)

        assert satisfied is False
        assert 'error' in gate_status
        assert 'expected dict' in gate_status['error']
        assert 'index 0' in gate_status['error']

    def test_condition_without_type_returns_error(self):
        """Lignes 96-103: condition sans 'type' → False + error."""
        execution = ExecutionFactory(status='RUNNING')
        step = ExecutionStepFactory(
            execution=execution,
            status=ExecutionStepStatus.WAITING,
        )
        # Condition sans champ 'type'
        step.set_output({'gate_conditions': [{'description': 'wait'}]})
        step.save()

        evaluator = GateEvaluator()
        satisfied, gate_status = evaluator.evaluate(step)

        assert satisfied is False
        assert 'error' in gate_status
        assert 'missing or invalid type' in gate_status['error']

    def test_condition_type_not_string_returns_error(self):
        """Lignes 96-103: condition avec type non-string → False + error."""
        execution = ExecutionFactory(status='RUNNING')
        step = ExecutionStepFactory(
            execution=execution,
            status=ExecutionStepStatus.WAITING,
        )
        # Type est un entier, pas une chaîne
        step.set_output({'gate_conditions': [{'type': 123}]})
        step.save()

        evaluator = GateEvaluator()
        satisfied, gate_status = evaluator.evaluate(step)

        assert satisfied is False
        assert 'error' in gate_status
        assert 'missing or invalid type' in gate_status['error']


@pytest.mark.django_db
class TestGateEvaluatorEnvConfig:
    """Test env_config parsing — lignes 63->68."""

    def test_env_config_with_requires_maintenance_window_true(self):
        """Lignes 63-68 + 131-132: env_config avec requires_maintenance_window=True → évaluation réelle."""
        params = {
            '_env_config': {
                'requires_maintenance_window': True,
                'requires_approval': False,
            }
        }
        step = _create_step_with_params(
            [{'type': 'maintenance_window'}],
            params=params,
        )
        ExecutionTargetFactory(execution=step.execution, target_id='SERVER1')

        with patch.object(
            InventoryService,
            'get_next_maintenance_window',
            return_value={'is_active': True, 'start': None, 'end': None},
        ):
            evaluator = GateEvaluator()
            satisfied, gate_status = evaluator.evaluate(step)

        assert satisfied is True
        assert gate_status['gates'][0]['type'] == 'maintenance_window'

    def test_approval_granted_never_auto_satisfied(self):
        """approval_granted requires explicit approval via approve endpoint — never auto-satisfied."""
        params = {
            '_env_config': {
                'requires_maintenance_window': False,
                'requires_approval': False,
            }
        }
        step = _create_step_with_params(
            [{'type': 'approval_granted'}],
            params=params,
        )

        evaluator = GateEvaluator()
        satisfied, gate_status = evaluator.evaluate(step)

        assert satisfied is False
        assert gate_status['gates'][0]['type'] == 'approval_granted'
        assert gate_status['gates'][0]['satisfied'] is False
        assert "attente d'approbation" in gate_status['gates'][0]['reason']

    def test_approval_granted_required_not_satisfied(self):
        """approval_granted avec requires_approval=True → non satisfait (même comportement)."""
        params = {
            '_env_config': {
                'requires_maintenance_window': False,
                'requires_approval': True,
            }
        }
        step = _create_step_with_params(
            [{'type': 'approval_granted'}],
            params=params,
        )

        evaluator = GateEvaluator()
        satisfied, gate_status = evaluator.evaluate(step)

        assert satisfied is False
        assert gate_status['gates'][0]['satisfied'] is False
        assert "attente d'approbation" in gate_status['gates'][0]['reason']

    def test_env_config_not_dict_ignored(self):
        """env_config qui n'est pas un dict → ignoré. approval_granted never auto-satisfied."""
        params = {
            '_env_config': 'not_a_dict',
        }
        step = _create_step_with_params(
            [{'type': 'approval_granted'}],
            params=params,
        )

        evaluator = GateEvaluator()
        satisfied, gate_status = evaluator.evaluate(step)

        # approval_granted always requires explicit approval
        assert satisfied is False

    def test_no_env_config_param(self):
        """Pas de _env_config dans les params → requires_* restent False."""
        params = {'some_param': 'value'}
        step = _create_step_with_params(
            [{'type': 'maintenance_window'}],
            params=params,
        )

        evaluator = GateEvaluator()
        satisfied, gate_status = evaluator.evaluate(step)

        # requires_maintenance_window = False → auto-satisfait
        assert satisfied is True
        assert 'non requise' in gate_status['gates'][0]['reason']


@pytest.mark.django_db
class TestGateEvaluatorMaintenanceWindowEdgeCases:
    """Tests pour les cas limites de _check_maintenance_window — ligne 214->216."""

    def test_target_outside_window_no_next_start(self):
        """Ligne 214->216: target hors fenêtre mais sans next_start → pas de next_possible_at."""
        params = {
            '_env_config': {
                'requires_maintenance_window': True,
                'requires_approval': False,
            }
        }
        step = _create_step_with_params(
            [{'type': 'maintenance_window'}],
            params=params,
        )
        ExecutionTargetFactory(execution=step.execution, target_id='SERVER1')

        # Window is_active=False et start=None (pas de next_start)
        with patch.object(
            InventoryService,
            'get_next_maintenance_window',
            return_value={'is_active': False, 'start': None, 'end': None},
        ):
            evaluator = GateEvaluator()
            satisfied, gate_status = evaluator.evaluate(step)

        assert satisfied is False
        gate = gate_status['gates'][0]
        assert gate['satisfied'] is False
        # Pas de next_possible_at quand start est None
        assert 'next_possible_at' not in gate


class TestGateEvaluatorCheckTimeout:
    """Tests pour _check_timeout — ligne 267."""

    def test_check_timeout_with_zero_timeout_hours(self):
        """Ligne 267: timeout_hours=0 (falsy) → retourne (False, None)."""
        evaluator = GateEvaluator()
        step = MagicMock()
        step.id = 1
        step.created_at = timezone.now() - timedelta(hours=100)

        condition = {'type': 'maintenance_window', 'timeout_hours': 0}
        triggered, action = evaluator._check_timeout(step, condition)

        assert triggered is False
        assert action is None

    def test_check_timeout_without_timeout_hours(self):
        """Ligne 267: pas de timeout_hours dans condition → retourne (False, None)."""
        evaluator = GateEvaluator()
        step = MagicMock()
        step.id = 1
        step.created_at = timezone.now() - timedelta(hours=100)

        condition = {'type': 'maintenance_window'}
        triggered, action = evaluator._check_timeout(step, condition)

        assert triggered is False
        assert action is None

    def test_evaluate_with_no_output(self):
        """Step avec output=None → True + gates vides."""
        evaluator = GateEvaluator()
        step = MagicMock()
        step.id = 1
        step.get_output.return_value = None

        satisfied, gate_status = evaluator.evaluate(step)

        assert satisfied is True
        assert gate_status['gates'] == []
        assert gate_status['timeout_triggered'] is False
