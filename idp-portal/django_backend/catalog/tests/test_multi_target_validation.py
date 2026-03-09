"""
Tests unitaires pour la validation multi-cibles — Story 67.1 AC #7.

Couvre : fan-out valide, rétrocompatibilité singulier→tableau, step_id inexistant,
cycle via multi-cibles, exit point, absence d'exit point, séquentiel sans champs multi-cibles.
"""
import pytest
from rest_framework.exceptions import ValidationError

from catalog.validation import validate_workflow_steps


def make_platform_step(step_id, ref_id=1, **kwargs):
    """Helper — construit un step platform minimal."""
    return {
        'step_id': step_id,
        'step_type': 'platform',
        'referenced_action_id': ref_id,
        **kwargs,
    }


class TestFanOutValid:
    """AC #1 — workflow valide avec on_success_step_ids (fan-out)."""

    def test_fan_out_two_successors(self):
        """Workflow valide : step A → [B, C] (fan-out 2)."""
        steps = [
            make_platform_step('a', on_success_step_ids=['b', 'c']),
            make_platform_step('b', on_success_step_ids=[]),
            make_platform_step('c', on_success_step_ids=[]),
        ]
        result = validate_workflow_steps(steps)
        assert result is not None

    def test_fan_out_three_successors(self):
        """Workflow valide : step A → [B, C, D]."""
        steps = [
            make_platform_step('a', on_success_step_ids=['b', 'c', 'd']),
            make_platform_step('b', on_success_step_ids=[]),
            make_platform_step('c', on_success_step_ids=[]),
            make_platform_step('d', on_success_step_ids=[]),
        ]
        result = validate_workflow_steps(steps)
        assert result is not None

    def test_fan_out_with_error_routing(self):
        """Workflow valide : fan-out succès + routing erreur séparé."""
        steps = [
            make_platform_step('a', on_success_step_ids=['b', 'c'], on_error_step_ids=['rollback']),
            make_platform_step('b', on_success_step_ids=[]),
            make_platform_step('c', on_success_step_ids=[]),
            make_platform_step('rollback', on_success_step_ids=[]),
        ]
        result = validate_workflow_steps(steps)
        assert result is not None

    def test_sequential_single_successor(self):
        """Workflow séquentiel : on_success_step_ids avec 1 seul élément."""
        steps = [
            make_platform_step('a', on_success_step_ids=['b']),
            make_platform_step('b', on_success_step_ids=[]),
        ]
        result = validate_workflow_steps(steps)
        assert result is not None

    def test_exit_point_null_ids(self):
        """AC #6 — exit point avec on_success_step_ids=None."""
        steps = [
            make_platform_step('a', on_success_step_ids=['b']),
            make_platform_step('b', on_success_step_ids=None),
        ]
        result = validate_workflow_steps(steps)
        assert result is not None


class TestRetrocompatSingularToList:
    """AC #2 — rétrocompatibilité : singulier normalisé en tableau."""

    def test_singular_success_normalized(self):
        """on_success_step_id singulier → on_success_step_ids=['b']."""
        steps = [
            make_platform_step('a', on_success_step_id='b'),
            make_platform_step('b', on_success_step_id=None),
        ]
        result = validate_workflow_steps(steps)
        assert result[0]['on_success_step_ids'] == ['b']

    def test_singular_error_normalized(self):
        """on_error_step_id singulier → on_error_step_ids=['rollback']."""
        steps = [
            make_platform_step('a', on_success_step_id=None, on_error_step_id='rollback'),
            make_platform_step('rollback', on_success_step_id=None),
        ]
        result = validate_workflow_steps(steps)
        assert result[0]['on_error_step_ids'] == ['rollback']

    def test_singular_null_normalized_to_empty_list(self):
        """on_success_step_id=None → on_success_step_ids=[]."""
        steps = [
            make_platform_step('a', on_success_step_id=None),
        ]
        result = validate_workflow_steps(steps)
        assert result[0]['on_success_step_ids'] == []

    def test_plural_not_overwritten_by_singular(self):
        """Si on_success_step_ids déjà présent, on_success_step_id singulier ne l'écrase pas."""
        steps = [
            make_platform_step('a', on_success_step_ids=['b', 'c'], on_success_step_id='b'),
            make_platform_step('b', on_success_step_ids=[]),
            make_platform_step('c', on_success_step_ids=[]),
        ]
        result = validate_workflow_steps(steps)
        assert result[0]['on_success_step_ids'] == ['b', 'c']

    def test_backward_compat_sequential_workflow_still_valid(self):
        """AC #7 — workflow séquentiel sans champs multi-cibles (backward compat)."""
        steps = [
            {'order': 1, 'name': 'Step 1', 'referenced_action_id': 10, 'step_id': 's1'},
            {'order': 2, 'name': 'Step 2', 'referenced_action_id': 20, 'step_id': 's2'},
        ]
        result = validate_workflow_steps(steps)
        assert result == steps


class TestInvalidStepIdReference:
    """AC #3 — step_id inexistant dans on_success_step_ids / on_error_step_ids."""

    def test_invalid_success_step_id_raises(self):
        """on_success_step_ids contient un step_id inexistant → ValidationError."""
        steps = [
            make_platform_step('a', on_success_step_ids=['nonexistent']),
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_workflow_steps(steps)
        assert 'nonexistent' in str(exc_info.value.detail)

    def test_invalid_error_step_id_raises(self):
        """on_error_step_ids contient un step_id inexistant → ValidationError."""
        steps = [
            make_platform_step('a', on_success_step_ids=[], on_error_step_ids=['ghost']),
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_workflow_steps(steps)
        assert 'ghost' in str(exc_info.value.detail)

    def test_one_valid_one_invalid_raises(self):
        """on_success_step_ids=['b', 'nonexistent'] → ValidationError sur 'nonexistent'."""
        steps = [
            make_platform_step('a', on_success_step_ids=['b', 'nonexistent']),
            make_platform_step('b', on_success_step_ids=[]),
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_workflow_steps(steps)
        assert 'nonexistent' in str(exc_info.value.detail)

    def test_empty_string_in_ids_raises(self):
        """on_success_step_ids contient une chaîne vide → ValidationError."""
        steps = [
            make_platform_step('a', on_success_step_ids=['']),
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_workflow_steps(steps)
        assert 'non-empty' in str(exc_info.value.detail).lower()

    def test_non_string_in_ids_raises(self):
        """on_success_step_ids contient un non-string → ValidationError."""
        steps = [
            make_platform_step('a', on_success_step_ids=[42]),
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_workflow_steps(steps)
        assert 'non-empty' in str(exc_info.value.detail).lower()

    def test_not_a_list_raises(self):
        """on_success_step_ids est une string (pas une liste) → ValidationError."""
        steps = [
            make_platform_step('a', on_success_step_ids='b'),
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_workflow_steps(steps)
        assert 'list' in str(exc_info.value.detail).lower()


class TestCycleDetectionMultiTarget:
    """AC #4 — détection de cycles via multi-cibles."""

    def test_direct_cycle_raises(self):
        """A→B, B→A → cycle → ValidationError."""
        steps = [
            make_platform_step('a', on_success_step_ids=['b'], on_error_step_ids=[]),
            make_platform_step('b', on_success_step_ids=['a'], on_error_step_ids=[]),
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_workflow_steps(steps)
        error_str = str(exc_info.value.detail).lower()
        assert 'loop' in error_str or 'cycle' in error_str or 'infinite' in error_str

    def test_fan_out_cycle_raises(self):
        """A→[B,C], B→A → cycle via fan-out → ValidationError."""
        steps = [
            make_platform_step('a', on_success_step_ids=['b', 'c'], on_error_step_ids=[]),
            make_platform_step('b', on_success_step_ids=['a'], on_error_step_ids=[]),
            make_platform_step('c', on_success_step_ids=[]),
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_workflow_steps(steps)
        error_str = str(exc_info.value.detail).lower()
        assert 'loop' in error_str or 'cycle' in error_str or 'infinite' in error_str

    def test_indirect_cycle_raises(self):
        """A→B, B→C, C→A → cycle indirect → ValidationError."""
        steps = [
            make_platform_step('a', on_success_step_ids=['b'], on_error_step_ids=[]),
            make_platform_step('b', on_success_step_ids=['c'], on_error_step_ids=[]),
            make_platform_step('c', on_success_step_ids=['a'], on_error_step_ids=[]),
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_workflow_steps(steps)
        error_str = str(exc_info.value.detail).lower()
        assert 'loop' in error_str or 'cycle' in error_str or 'infinite' in error_str

    def test_no_cycle_dag_valid(self):
        """DAG valide : A→[B,C], B→D, C→D, D→[] → pas de cycle."""
        steps = [
            make_platform_step('a', on_success_step_ids=['b', 'c'], on_error_step_ids=[]),
            make_platform_step('b', on_success_step_ids=['d']),
            make_platform_step('c', on_success_step_ids=['d']),
            make_platform_step('d', on_success_step_ids=[]),
        ]
        result = validate_workflow_steps(steps)
        assert result is not None


class TestExitPoint:
    """AC #6 — exit point rules."""

    def test_no_exit_point_raises(self):
        """Workflow sans exit point → ValidationError."""
        steps = [
            make_platform_step('a', on_success_step_ids=['b']),
            make_platform_step('b', on_success_step_ids=['a']),
        ]
        # (also a cycle, but exit point check fires first or alongside)
        with pytest.raises(ValidationError):
            validate_workflow_steps(steps)

    def test_all_steps_routing_no_exit_raises(self):
        """Tous les steps routent vers un autre step (aucun exit) → ValidationError."""
        steps = [
            make_platform_step('a', on_success_step_ids=['b']),
            make_platform_step('b', on_success_step_ids=['c']),
            make_platform_step('c', on_success_step_ids=['a']),
        ]
        with pytest.raises(ValidationError):
            validate_workflow_steps(steps)

    def test_exit_point_via_error_ids_empty(self):
        """Exit point via on_error_step_ids=[] (success route présent)."""
        steps = [
            make_platform_step('a', on_success_step_ids=['b'], on_error_step_ids=[]),
            make_platform_step('b', on_success_step_ids=[]),
        ]
        result = validate_workflow_steps(steps)
        assert result is not None
