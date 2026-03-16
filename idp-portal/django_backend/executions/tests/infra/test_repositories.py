"""Tests pour executions.infra.repositories — Story 85.2."""
import pytest

from executions.infra.repositories import ExecutionRepository
from executions.models import ExecutionStep, ExecutionStepStatus
from tests.factories import ExecutionFactory, ExecutionStepFactory


@pytest.mark.django_db
def test_get_step_with_relations(django_assert_num_queries):
    """Charge un step existant avec ses relations select_related en une seule requête."""
    step = ExecutionStepFactory()
    with django_assert_num_queries(1):
        loaded = ExecutionRepository.get_step_with_relations(step.id)
    assert loaded.id == step.id
    assert loaded.execution is not None
    assert loaded.execution.action is not None
    assert loaded.execution.user is not None


@pytest.mark.django_db
def test_get_step_with_relations_not_found():
    """Lève ExecutionStep.DoesNotExist si le step n'existe pas."""
    with pytest.raises(ExecutionStep.DoesNotExist):
        ExecutionRepository.get_step_with_relations(step_id=999999)


@pytest.mark.django_db
def test_get_completed_steps_returns_only_completed():
    """Filtre par statut COMPLETED, ordonnés par step_order."""
    execution = ExecutionFactory()
    step1 = ExecutionStepFactory(
        execution=execution, status=ExecutionStepStatus.COMPLETED, step_order=1
    )
    step2 = ExecutionStepFactory(
        execution=execution, status=ExecutionStepStatus.PENDING, step_order=2
    )
    step3 = ExecutionStepFactory(
        execution=execution, status=ExecutionStepStatus.COMPLETED, step_order=3
    )

    result = list(ExecutionRepository.get_completed_steps(execution.id))
    assert len(result) == 2
    ids = [s.id for s in result]
    assert step1.id in ids
    assert step3.id in ids
    assert step2.id not in ids
    # Ordonnés par step_order
    assert result[0].step_order < result[1].step_order


@pytest.mark.django_db
def test_get_max_step_order_returns_max():
    """Renvoie le step_order maximal."""
    execution = ExecutionFactory()
    ExecutionStepFactory(execution=execution, step_order=1)
    ExecutionStepFactory(execution=execution, step_order=5)
    ExecutionStepFactory(execution=execution, step_order=3)
    assert ExecutionRepository.get_max_step_order(execution.id) == 5


@pytest.mark.django_db
def test_get_max_step_order_returns_none_when_no_steps():
    """Renvoie None si aucun step pour l'execution."""
    execution = ExecutionFactory()
    assert ExecutionRepository.get_max_step_order(execution.id) is None


@pytest.mark.django_db
def test_step_exists_active_true_for_pending():
    """True si un step PENDING existe avec ce config_step_id."""
    step = ExecutionStepFactory(status=ExecutionStepStatus.PENDING)
    result = ExecutionRepository.step_exists_active(
        execution_id=step.execution_id,
        config_step_id=step.config_step_id,
    )
    assert result is True


@pytest.mark.django_db
def test_step_exists_active_true_for_running():
    """True si un step RUNNING existe avec ce config_step_id."""
    step = ExecutionStepFactory(status=ExecutionStepStatus.RUNNING)
    result = ExecutionRepository.step_exists_active(
        execution_id=step.execution_id,
        config_step_id=step.config_step_id,
    )
    assert result is True


@pytest.mark.django_db
def test_step_exists_active_true_for_completed():
    """True si un step COMPLETED existe avec ce config_step_id."""
    step = ExecutionStepFactory(status=ExecutionStepStatus.COMPLETED)
    result = ExecutionRepository.step_exists_active(
        execution_id=step.execution_id,
        config_step_id=step.config_step_id,
    )
    assert result is True


@pytest.mark.django_db
def test_step_exists_active_true_for_waiting():
    """True si un step WAITING existe avec ce config_step_id."""
    step = ExecutionStepFactory(status=ExecutionStepStatus.WAITING)
    result = ExecutionRepository.step_exists_active(
        execution_id=step.execution_id,
        config_step_id=step.config_step_id,
    )
    assert result is True


@pytest.mark.django_db
def test_step_exists_active_false_for_failed():
    """False si le step est en statut FAILED (non actif)."""
    step = ExecutionStepFactory(status=ExecutionStepStatus.FAILED)
    result = ExecutionRepository.step_exists_active(
        execution_id=step.execution_id,
        config_step_id=step.config_step_id,
    )
    assert result is False


@pytest.mark.django_db
def test_touch_heartbeat_updates_updated_at():
    """updated_at est modifié après touch_heartbeat (uniquement si status=RUNNING)."""
    from django.utils import timezone

    from executions.models import ExecutionStatus

    execution = ExecutionFactory(status=ExecutionStatus.RUNNING)
    initial = execution.updated_at
    before = timezone.now()
    ExecutionRepository.touch_heartbeat(execution.id)
    execution.refresh_from_db()
    assert execution.updated_at is not None
    assert execution.updated_at >= before
    if initial is not None:
        assert execution.updated_at >= initial


@pytest.mark.django_db
def test_touch_heartbeat_no_update_when_not_running():
    """touch_heartbeat ne modifie pas updated_at si status != RUNNING."""
    from executions.models import ExecutionStatus

    execution = ExecutionFactory(status=ExecutionStatus.SUBMITTED)
    initial = execution.updated_at
    ExecutionRepository.touch_heartbeat(execution.id)
    execution.refresh_from_db()
    assert execution.updated_at == initial
