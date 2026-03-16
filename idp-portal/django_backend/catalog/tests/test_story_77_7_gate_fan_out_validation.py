"""Tests pour la validation des gate steps dans les branches parallèles — Story 77.7."""
import pytest
from rest_framework.exceptions import ValidationError

from catalog.validation import validate_workflow_steps


def make_platform_step(step_id, ref_id=1, **kwargs):
    return {'step_id': step_id, 'step_type': 'platform', 'referenced_action_id': ref_id, **kwargs}


def make_gate_step(step_id, gate_type='approval', **kwargs):
    return {'step_id': step_id, 'step_type': 'gate', 'gate_type': gate_type, **kwargs}


class TestAC1GateDirectlyInFanOut:

    def test_gate_approval_directly_in_fan_out_raises(self):
        """AC1 : gate approval directement dans on_success_step_ids avec 2+ cibles → ValidationError."""
        steps = [
            make_platform_step('a', on_success_step_ids=['gate-approval', 'step-b']),
            make_gate_step('gate-approval', on_success_step_ids=[]),
            make_platform_step('step-b', on_success_step_ids=[]),
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_workflow_steps(steps)
        assert 'gate-approval' in str(exc_info.value)
        assert 'fan-out' in str(exc_info.value).lower() or 'parallèle' in str(exc_info.value)

    def test_gate_maintenance_window_directly_in_fan_out_raises(self):
        """AC1 : gate maintenance_window directement dans fan-out → ValidationError."""
        steps = [
            make_platform_step('a', on_success_step_ids=['gate-mw', 'step-b']),
            make_gate_step('gate-mw', gate_type='maintenance_window', on_success_step_ids=[]),
            make_platform_step('step-b', on_success_step_ids=[]),
        ]
        with pytest.raises(ValidationError):
            validate_workflow_steps(steps)

    def test_gate_via_on_error_step_ids_fan_out_raises(self):
        """AC1 : fan-out via on_error_step_ids → ValidationError si gate dedans."""
        steps = [
            make_platform_step('a', on_success_step_ids=[], on_error_step_ids=['gate-approval', 'step-b']),
            make_gate_step('gate-approval', on_success_step_ids=[]),
            make_platform_step('step-b', on_success_step_ids=[]),
        ]
        with pytest.raises(ValidationError):
            validate_workflow_steps(steps)


class TestAC2GateInSubBranch:

    def test_gate_in_sub_branch_of_fan_out_raises(self):
        """AC2 : A → [B, C], B → gate-1 → gate dans sous-branche du fan-out → ValidationError."""
        steps = [
            make_platform_step('a', on_success_step_ids=['b', 'c']),
            make_platform_step('b', on_success_step_ids=['gate-1']),
            make_platform_step('c', on_success_step_ids=[]),
            make_gate_step('gate-1', on_success_step_ids=[]),
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_workflow_steps(steps)
        assert 'gate-1' in str(exc_info.value)

    def test_gate_in_nested_fan_out_raises(self):
        """AC2 : A → [B, C], B → [D, E], D → gate-1 (fan-out imbriqué) → ValidationError."""
        steps = [
            make_platform_step('a', on_success_step_ids=['b', 'c']),
            make_platform_step('b', on_success_step_ids=['d', 'e']),
            make_platform_step('c', on_success_step_ids=[]),
            make_platform_step('d', on_success_step_ids=['gate-1']),
            make_platform_step('e', on_success_step_ids=[]),
            make_gate_step('gate-1', on_success_step_ids=[]),
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_workflow_steps(steps)
        assert 'gate-1' in str(exc_info.value)


class TestAC3SequentialGateValid:

    def test_sequential_gate_is_valid(self):
        """AC3 : gate séquentiel (on_success_step_ids avec 1 seule cible) → pas d'erreur."""
        steps = [
            make_platform_step('a', on_success_step_ids=['gate-1']),
            make_gate_step('gate-1', on_success_step_ids=['b']),
            make_platform_step('b', on_success_step_ids=[]),
        ]
        result = validate_workflow_steps(steps)
        assert result is not None

    def test_gate_after_join_is_valid(self):
        """AC3 : gate après convergence (join) des branches → pas d'erreur."""
        # A → [B, C] → join → gate-1 → final
        # join a in_degree=2 → join_point → BFS s'arrête là
        # gate-1 est APRÈS le join → séquentiel → pas d'erreur
        steps = [
            make_platform_step('a', on_success_step_ids=['b', 'c']),
            make_platform_step('b', on_success_step_ids=['join']),
            make_platform_step('c', on_success_step_ids=['join']),
            make_platform_step('join', on_success_step_ids=['gate-1']),
            make_gate_step('gate-1', on_success_step_ids=[]),
        ]
        result = validate_workflow_steps(steps)
        assert result is not None


class TestAC4FanOutWithoutGateValid:

    def test_fan_out_without_gate_is_valid(self):
        """AC4 : fan-out sans gate → pas d'erreur."""
        steps = [
            make_platform_step('a', on_success_step_ids=['b', 'c']),
            make_platform_step('b', on_success_step_ids=[]),
            make_platform_step('c', on_success_step_ids=[]),
        ]
        result = validate_workflow_steps(steps)
        assert result is not None

    def test_fan_out_with_join_without_gate_is_valid(self):
        """AC4 : fan-out complet avec join mais sans gate → pas d'erreur."""
        steps = [
            make_platform_step('a', on_success_step_ids=['b', 'c']),
            make_platform_step('b', on_success_step_ids=['join']),
            make_platform_step('c', on_success_step_ids=['join']),
            make_platform_step('join', on_success_step_ids=[]),
        ]
        result = validate_workflow_steps(steps)
        assert result is not None


class TestAC5ErrorMessage:

    def test_error_message_contains_gate_step_id_and_origin(self):
        """AC5 : le message d'erreur mentionne le step_id du gate ET l'origin du fan-out."""
        steps = [
            make_platform_step('fan-origin', on_success_step_ids=['gate-approval', 'parallel-b']),
            make_gate_step('gate-approval', on_success_step_ids=[]),
            make_platform_step('parallel-b', on_success_step_ids=[]),
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_workflow_steps(steps)
        error_str = str(exc_info.value)
        assert 'gate-approval' in error_str
        assert 'fan-origin' in error_str
