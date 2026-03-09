"""
Tests unitaires pour la validation parallel_group — Story 65.1 AC #9.

Couvre : cas valide, parallel_steps < 2, référence invalide, cycle détecté,
champs manquants, auto-référence.
"""
import pytest
from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from catalog.validation import validate_workflow_steps


def _platform(step_id, on_success=None, on_error=None, ref_id=1):
    """Helper — construit un step platform minimal."""
    step = {
        'step_id': step_id,
        'step_type': 'platform',
        'referenced_action_id': ref_id,
        'on_success_step_id': on_success,
        'on_error_step_id': on_error,
    }
    return step


def _parallel(step_id, parallel_steps, on_all_success=None, on_any_error=None):
    """Helper — construit un step parallel_group minimal."""
    return {
        'step_id': step_id,
        'step_type': 'parallel_group',
        'parallel_steps': parallel_steps,
        'on_all_success_step_id': on_all_success,
        'on_any_error_step_id': on_any_error,
    }


class TestParallelGroupValid(SimpleTestCase):
    """Tests 4.1 — cas valides."""

    def test_valid_parallel_group_two_substeps(self):
        """AC #1, #2 — parallel_group valide avec 2 sous-steps et on_all_success_step_id référencé."""
        steps = [
            _parallel('pg-1', ['s1', 's2'], on_all_success='s3', on_any_error=None),
            _platform('s1', on_success=None, on_error=None),
            _platform('s2', on_success=None, on_error=None),
            _platform('s3', on_success=None, on_error=None),
        ]
        validate_workflow_steps(steps)  # Pas d'exception

    def test_valid_parallel_group_three_substeps(self):
        """AC #3 — parallel_group valide avec 3 sous-steps."""
        steps = [
            _parallel('pg-1', ['s1', 's2', 's3'], on_all_success=None, on_any_error=None),
            _platform('s1', on_success=None, on_error=None),
            _platform('s2', on_success=None, on_error=None),
            _platform('s3', on_success=None, on_error=None),
        ]
        validate_workflow_steps(steps)  # Pas d'exception

    def test_valid_parallel_group_both_success_error_set(self):
        """AC #6 — on_all_success_step_id ET on_any_error_step_id non-null et valides."""
        steps = [
            _parallel('pg-1', ['s1', 's2'], on_all_success='s3', on_any_error='rollback'),
            _platform('s1', on_success=None, on_error=None),
            _platform('s2', on_success=None, on_error=None),
            _platform('s3', on_success=None, on_error=None),
            _platform('rollback', on_success=None, on_error=None),
        ]
        validate_workflow_steps(steps)  # Pas d'exception


class TestParallelGroupParallelStepsInvalid(SimpleTestCase):
    """Tests 4.2, 4.3, 4.7 — parallel_steps invalide."""

    def test_parallel_steps_one_element_raises(self):
        """AC #3 Test 4.2 — parallel_steps avec 1 seul élément → ValidationError."""
        steps = [
            _parallel('pg-1', ['s1'], on_all_success=None, on_any_error=None),
            _platform('s1', on_success=None, on_error=None),
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_workflow_steps(steps)
        assert 'at least 2' in str(exc_info.value.detail).lower()

    def test_parallel_steps_empty_raises(self):
        """AC #3 — parallel_steps vide → ValidationError."""
        steps = [
            _parallel('pg-1', [], on_all_success=None, on_any_error=None),
            _platform('s1', on_success=None, on_error=None),
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_workflow_steps(steps)
        assert 'at least 2' in str(exc_info.value.detail).lower()

    def test_parallel_steps_invalid_reference_raises(self):
        """AC #4 Test 4.3 — parallel_steps référençant un step_id inexistant → ValidationError."""
        steps = [
            _parallel('pg-1', ['s1', 'nonexistent'], on_all_success=None, on_any_error=None),
            _platform('s1', on_success=None, on_error=None),
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_workflow_steps(steps)
        assert 'nonexistent' in str(exc_info.value.detail)

    def test_parallel_steps_absent_raises(self):
        """AC #2 Test 4.7 — parallel_steps absent → ValidationError."""
        step = {
            'step_id': 'pg-1',
            'step_type': 'parallel_group',
            # pas de parallel_steps
            'on_all_success_step_id': None,
            'on_any_error_step_id': None,
        }
        steps = [
            step,
            _platform('s1', on_success=None, on_error=None),
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_workflow_steps(steps)
        assert 'parallel_steps' in str(exc_info.value.detail).lower()

    def test_parallel_steps_duplicate_step_ids_raises(self):
        """AC #3 — parallel_steps avec 2 éléments identiques → ValidationError (doit être distinct)."""
        steps = [
            _parallel('pg-1', ['s1', 's1'], on_all_success=None, on_any_error=None),
            _platform('s1', on_success=None, on_error=None),
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_workflow_steps(steps)
        assert 'at least 2' in str(exc_info.value.detail).lower()

    def test_parallel_steps_not_a_list_raises(self):
        """AC #2 — parallel_steps est une string (pas une liste) → ValidationError."""
        step = {
            'step_id': 'pg-1',
            'step_type': 'parallel_group',
            'parallel_steps': 's1',  # devrait être une liste
            'on_all_success_step_id': None,
            'on_any_error_step_id': None,
        }
        steps = [
            step,
            _platform('s1', on_success=None, on_error=None),
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_workflow_steps(steps)
        assert 'parallel_steps' in str(exc_info.value.detail).lower()


class TestParallelGroupSuccessErrorRefInvalid(SimpleTestCase):
    """Test 4.4 — on_all_success_step_id / on_any_error_step_id invalides."""

    def test_on_all_success_step_id_invalid_raises(self):
        """AC #6 Test 4.4 — on_all_success_step_id référençant un step_id inexistant → ValidationError."""
        steps = [
            _parallel('pg-1', ['s1', 's2'], on_all_success='nonexistent', on_any_error=None),
            _platform('s1', on_success=None, on_error=None),
            _platform('s2', on_success=None, on_error=None),
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_workflow_steps(steps)
        assert 'nonexistent' in str(exc_info.value.detail)
        assert 'on_all_success_step_id' in str(exc_info.value.detail)

    def test_on_any_error_step_id_invalid_raises(self):
        """AC #6 — on_any_error_step_id référençant un step_id inexistant → ValidationError."""
        steps = [
            _parallel('pg-1', ['s1', 's2'], on_all_success=None, on_any_error='nonexistent'),
            _platform('s1', on_success=None, on_error=None),
            _platform('s2', on_success=None, on_error=None),
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_workflow_steps(steps)
        assert 'nonexistent' in str(exc_info.value.detail)
        assert 'on_any_error_step_id' in str(exc_info.value.detail)


class TestParallelGroupSelfReference(SimpleTestCase):
    """Test 4.6 — auto-référence dans parallel_steps."""

    def test_parallel_steps_contains_own_step_id_raises(self):
        """AC #7 Test 4.6 — parallel_steps contient le step_id du parallel_group lui-même → ValidationError."""
        steps = [
            _parallel('pg-1', ['pg-1', 's1'], on_all_success=None, on_any_error=None),
            _platform('s1', on_success=None, on_error=None),
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_workflow_steps(steps)
        assert 'own step_id' in str(exc_info.value.detail).lower() or 'cannot contain' in str(exc_info.value.detail).lower()


class TestParallelGroupCycleDetection(SimpleTestCase):
    """Test 4.5 — détection de cycles impliquant parallel_group."""

    def test_cycle_parallel_group_points_back_to_itself_via_on_all_success(self):
        """AC #5 Test 4.5 — cycle via on_all_success_step_id pointant vers pg-1 → ValidationError."""
        # pg-1 → s1, s2 (via parallel_steps)
        # pg-1 → pg-1 (via on_all_success_step_id) = cycle direct
        steps = [
            _parallel('pg-1', ['s1', 's2'], on_all_success='pg-1', on_any_error=None),
            _platform('s1', on_success=None, on_error=None),
            _platform('s2', on_success=None, on_error=None),
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_workflow_steps(steps)
        assert 'loop' in str(exc_info.value.detail).lower() or 'cycle' in str(exc_info.value.detail).lower() or 'infinite' in str(exc_info.value.detail).lower()

    def test_cycle_substep_points_back_to_parallel_group(self):
        """AC #5 — cycle indirect : s1.on_success_step_id = pg-1 → ValidationError.

        Note: The validator catches this scenario as "parallel_group member must not have
        on_success_step_id" before reaching cycle detection, which is equally correct.
        Either a cycle detection error or a routing-edge restriction error is acceptable.
        """
        steps = [
            _parallel('pg-1', ['s1', 's2'], on_all_success=None, on_any_error=None),
            _platform('s1', on_success='pg-1', on_error=None),  # cycle: s1 → pg-1 → s1
            _platform('s2', on_success=None, on_error=None),
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_workflow_steps(steps)
        error_str = str(exc_info.value.detail).lower()
        assert (
            'loop' in error_str
            or 'cycle' in error_str
            or 'infinite' in error_str
            or 'on_success_step_id' in error_str  # routing-edge restriction (caught before cycle detection)
        )
