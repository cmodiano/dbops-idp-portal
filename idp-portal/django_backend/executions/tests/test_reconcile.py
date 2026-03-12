"""
Tests unitaires pour la logique de réconciliation crash-recovery — Story 76.1

Tests:
- AC1: Container workflow avec étapes COMPLETED → résultat 'reattached', pas de FAILED
- AC2: Container workflow avec prochaine vague vide (toutes étapes terminées) → COMPLETED
- AC3a: Container workflow sans étapes COMPLETED → fallback FAILED
- AC3b: Exécution non-workflow (pas de step_ids) → comportement actuel FAILED préservé
- AC4 additionnel: Exception pendant la reprise → fallback FAILED + log d'erreur
- AC3c: _is_container_workflow — cas limites (action sans execution_steps, liste vide, step_id valides)
"""

import pytest
from unittest.mock import patch, MagicMock

from executions.tasks.reconcile import (
    _is_container_workflow,
    _reconcile_execution,
    _resume_container_workflow,
)
from tests.factories import ExecutionFactory, ExecutionStepFactory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

STEP_ID_A = "step-id-aaa"
STEP_ID_B = "step-id-bbb"

CONTAINER_STEPS = [
    {"step_id": STEP_ID_A, "name": "step_a", "type": "platform"},
    {"step_id": STEP_ID_B, "name": "step_b", "type": "platform"},
]


def _make_execution(execution_steps=None, status="RUNNING"):
    """Create an Execution whose action.execution_steps is set to execution_steps."""
    execution = ExecutionFactory(status=status)
    if execution_steps is not None:
        execution.action.execution_steps = execution_steps
        execution.action.save(update_fields=["execution_steps"])
    return execution


# ---------------------------------------------------------------------------
# _is_container_workflow — Task 3
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestIsContainerWorkflow:
    """Task 3 — Détection container workflow."""

    def test_action_with_valid_step_ids_returns_true(self):
        execution = _make_execution(execution_steps=CONTAINER_STEPS)
        assert _is_container_workflow(execution) is True

    def test_action_without_execution_steps_returns_false(self):
        execution = _make_execution(execution_steps=None)
        # Force None at the attribute level
        execution.action.execution_steps = None
        assert _is_container_workflow(execution) is False

    def test_action_with_empty_execution_steps_returns_false(self):
        execution = _make_execution(execution_steps=[])
        execution.action.execution_steps = []
        assert _is_container_workflow(execution) is False

    def test_action_with_steps_without_step_id_returns_false(self):
        steps = [{"name": "step_a", "type": "platform"}]  # no step_id
        execution = _make_execution(execution_steps=steps)
        execution.action.execution_steps = steps
        assert _is_container_workflow(execution) is False

    def test_attribute_error_returns_false(self):
        """Execution without 'action' attribute → False."""
        mock_exec = MagicMock(spec=[])  # no attributes
        assert _is_container_workflow(mock_exec) is False


# ---------------------------------------------------------------------------
# _reconcile_execution — Tasks 1 & 2 & 4
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestReconcileExecution:
    """Task 4 — Tests unitaires _reconcile_execution."""

    # ------------------------------------------------------------------
    # AC4.1: Container workflow avec étapes COMPLETED → 'reattached'
    # ------------------------------------------------------------------

    def test_container_workflow_with_completed_steps_returns_reattached(self):
        """AC1 + AC4.1: Container workflow + COMPLETED steps → reattached, pas de FAILED."""
        execution = _make_execution(execution_steps=CONTAINER_STEPS)

        ExecutionStepFactory(
            execution=execution,
            status="COMPLETED",
            config_step_id=STEP_ID_A,
            step_order=1,
        )

        with patch(
            "executions.tasks.reconcile._resume_container_workflow",
            return_value="reattached",
        ) as mock_resume, patch(
            "executions.tasks.reconcile._mark_execution_failed"
        ) as mock_fail:
            result = _reconcile_execution(execution)

        assert result == "reattached"
        mock_resume.assert_called_once_with(execution, correlation_id="")
        mock_fail.assert_not_called()

    # ------------------------------------------------------------------
    # AC4.2: Container workflow sans aucune étape COMPLETED → fallback FAILED
    # ------------------------------------------------------------------

    def test_container_workflow_no_completed_steps_falls_back_to_failed(self):
        """AC3 + AC4.2: Container workflow mais aucune étape COMPLETED → FAILED."""
        execution = _make_execution(execution_steps=CONTAINER_STEPS)

        with patch(
            "executions.tasks.reconcile._resume_container_workflow",
            side_effect=ValueError("No COMPLETED steps found — cannot resume container workflow"),
        ) as mock_resume, patch(
            "executions.tasks.reconcile._mark_execution_failed"
        ) as mock_fail:
            result = _reconcile_execution(execution)

        assert result == "failed"
        mock_resume.assert_called_once()
        mock_fail.assert_called_once()

    # ------------------------------------------------------------------
    # AC4.3: Exécution non-workflow → comportement actuel FAILED préservé
    # ------------------------------------------------------------------

    def test_non_container_workflow_execution_falls_back_to_failed(self):
        """AC3 + AC4.3: Pas un container workflow → pas de tentative de reprise → FAILED."""
        # execution_steps without step_id → not a container workflow
        execution = _make_execution(
            execution_steps=[{"name": "step_a", "type": "vault"}]
        )
        execution.action.execution_steps = [{"name": "step_a", "type": "vault"}]

        with patch(
            "executions.tasks.reconcile._resume_container_workflow"
        ) as mock_resume, patch(
            "executions.tasks.reconcile._mark_execution_failed"
        ) as mock_fail:
            result = _reconcile_execution(execution)

        assert result == "failed"
        mock_resume.assert_not_called()
        mock_fail.assert_called_once()

    # ------------------------------------------------------------------
    # AC4.4: Container workflow, prochaine vague vide → COMPLETED
    # ------------------------------------------------------------------

    def test_container_workflow_resume_propagates_reattached(self):
        """AC4.4 (wrapper): Quand _resume_container_workflow retourne 'reattached',
        _reconcile_execution propage ce résultat sans appeler _mark_execution_failed.
        Note: la vérification que execution.status → COMPLETED est dans TestResumeContainerWorkflow."""
        execution = _make_execution(execution_steps=CONTAINER_STEPS)

        ExecutionStepFactory(
            execution=execution,
            status="COMPLETED",
            config_step_id=STEP_ID_A,
            step_order=1,
        )
        ExecutionStepFactory(
            execution=execution,
            status="COMPLETED",
            config_step_id=STEP_ID_B,
            step_order=2,
        )

        with patch(
            "executions.tasks.reconcile._resume_container_workflow",
            return_value="reattached",
        ) as mock_resume, patch(
            "executions.tasks.reconcile._mark_execution_failed"
        ) as mock_fail:
            result = _reconcile_execution(execution)

        assert result == "reattached"
        mock_resume.assert_called_once()
        mock_fail.assert_not_called()

    # ------------------------------------------------------------------
    # AC4.5: Exception pendant la reprise → fallback FAILED + log d'erreur
    # ------------------------------------------------------------------

    def test_exception_during_resume_falls_back_to_failed_and_logs(self):
        """AC3 + AC4.5: Exception inattendue pendant _resume → FAILED + log."""
        execution = _make_execution(execution_steps=CONTAINER_STEPS)

        with patch(
            "executions.tasks.reconcile._resume_container_workflow",
            side_effect=RuntimeError("Unexpected error"),
        ) as mock_resume, patch(
            "executions.tasks.reconcile._mark_execution_failed"
        ) as mock_fail, patch(
            "executions.tasks.reconcile.logger"
        ) as mock_logger:
            result = _reconcile_execution(execution)

        assert result == "failed"
        mock_resume.assert_called_once()
        mock_fail.assert_called_once()
        mock_logger.error.assert_called_once()
        error_call_kwargs = mock_logger.error.call_args
        assert "reconcile_container_workflow_resume_failed" in error_call_kwargs[0]


# ---------------------------------------------------------------------------
# _resume_container_workflow — Tests directs (H2 fix)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestResumeContainerWorkflow:
    """Tests directs de _resume_container_workflow — vérifie la logique interne (AC1, AC2, AC3)."""

    def test_no_completed_steps_raises_value_error(self):
        """AC3: Aucune étape COMPLETED → ValueError (le caller fait fallback FAILED)."""
        execution = _make_execution(execution_steps=CONTAINER_STEPS)
        # Aucun ExecutionStep créé → completed_steps = []

        with patch("executions.container_workflow_runtime.ContainerWorkflowRuntime"):
            with pytest.raises(ValueError, match="No COMPLETED steps"):
                _resume_container_workflow(execution)

    def test_empty_next_wave_marks_execution_completed(self):
        """AC2: Toutes étapes COMPLETED, vague suivante vide → execution.status = COMPLETED."""
        from executions.models import ExecutionStatus

        execution = _make_execution(execution_steps=CONTAINER_STEPS)
        ExecutionStepFactory(
            execution=execution,
            status="COMPLETED",
            config_step_id=STEP_ID_A,
            step_order=1,
        )

        mock_rt = MagicMock()
        mock_rt._step_outputs = {}
        mock_rt._step_lookup_by_id = {
            STEP_ID_A: CONTAINER_STEPS[0],
            STEP_ID_B: CONTAINER_STEPS[1],
        }

        with patch(
            "executions.container_workflow_runtime.ContainerWorkflowRuntime",
            return_value=mock_rt,
        ), patch(
            "executions.container_routing.get_next_step_ids",
            return_value=[STEP_ID_B],
        ), patch(
            "executions.container_parallel.apply_join_policy",
            return_value=[],  # vague suivante vide
        ), patch(
            "executions.output_extractor.OutputExtractor",
            return_value=MagicMock(extract=lambda raw, mapping: raw),
        ):
            result = _resume_container_workflow(execution)

        assert result == "reattached"
        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.COMPLETED
        assert execution.completed_at is not None

    def test_non_empty_next_wave_calls_execute_workflow_steps(self):
        """AC1: Vague suivante non vide → _execute_workflow_steps appelé, _initial_wave défini."""
        execution = _make_execution(execution_steps=CONTAINER_STEPS)
        ExecutionStepFactory(
            execution=execution,
            status="COMPLETED",
            config_step_id=STEP_ID_A,
            step_order=1,
        )

        mock_rt = MagicMock()
        mock_rt._step_outputs = {}
        mock_rt._step_lookup_by_id = {
            STEP_ID_A: CONTAINER_STEPS[0],
            STEP_ID_B: CONTAINER_STEPS[1],
        }

        with patch(
            "executions.container_workflow_runtime.ContainerWorkflowRuntime",
            return_value=mock_rt,
        ), patch(
            "executions.container_routing.get_next_step_ids",
            return_value=[STEP_ID_B],
        ), patch(
            "executions.container_parallel.apply_join_policy",
            return_value=[STEP_ID_B],  # vague suivante non vide
        ), patch(
            "executions.output_extractor.OutputExtractor",
            return_value=MagicMock(extract=lambda raw, mapping: raw),
        ):
            result = _resume_container_workflow(execution)

        assert result == "reattached"
        mock_rt._execute_workflow_steps.assert_called_once()
        assert mock_rt._initial_wave == [STEP_ID_B]
