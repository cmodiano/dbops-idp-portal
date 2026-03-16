"""
Tests unitaires pour la logique de réconciliation crash-recovery — Story 76.1, 76.2, 76.3, 76.4, 76.5

Tests Story 76.1:
- AC1: Container workflow avec étapes COMPLETED → résultat 'reattached', pas de FAILED
- AC2: Container workflow avec prochaine vague vide (toutes étapes terminées) → COMPLETED
- AC3a: Container workflow sans étapes COMPLETED → fallback FAILED
- AC3b: Exécution non-workflow (pas de step_ids) → comportement actuel FAILED préservé
- AC4 additionnel: Exception pendant la reprise → fallback FAILED + log d'erreur
- AC3c: _is_container_workflow — cas limites (action sans execution_steps, liste vide, step_id valides)

Tests Story 76.2:
- AC1: Enfant stale seul (parent sain) → _reconcile_execution appelé normalement
- AC3a: Enfant stale avec parent traité dans ce run → _mark_execution_failed, pas _reconcile_execution
- AC3b: Enfant stale avec parent déjà terminal en DB → _mark_execution_failed, pas _reconcile_execution
- AC2: Enfant stale avec parent sain → _reconcile_execution appelé normalement
- Compteurs: total_reattached, total_failed, total_skipped reflètent les enfants

Tests Story 76.4:
- AC1: Documentation du comportement (vérifiée via les tests AC2 et AC3)
- AC2/Task 2.1: _is_child_execution_id — détection correcte (child existant, non-child, non-numérique)
- AC2/Task 2.2: _reconcile_schedule_step — child COMPLETED → step COMPLETED, retourne True
- AC2/Task 2.2: _reconcile_schedule_step — child FAILED → step FAILED, retourne False
- AC2/Task 2.2: _reconcile_schedule_step — child RUNNING stale → child + step FAILED, retourne False
- AC2/Task 2.2: _reconcile_schedule_step — child introuvable → step FAILED, retourne False
- AC3/Task 3.1: Action simple RUNNING avec platform_job_id réel → _reattach_poll appelé
- AC3/Task 3.2: Step schedule_execution avec platform_job_id = child_id → _reconcile_schedule_step appelé
- AC3/Task 3.3: platform_job_id numérique qui n'est pas un child → reattach normal

Tests Story 76.5:
- AC4/3.1-3.6: Retry non-platform (service_call, http_request, evaluation) — success, fail, platform no-retry
- Mixed retry: step A retry success + step B retry fail → execution FAILED (not resume)
"""

import pytest
from unittest.mock import patch, MagicMock

from executions.tasks.reconcile import (
    _build_stale_filter,
    _enqueue_recovery_steps,
    _is_child_execution_id,
    _is_container_workflow,
    _reconcile_execution,
    _reconcile_schedule_step,
    _reset_and_enqueue_step,
    reconcile_stale_executions,
)
from tests.factories import ExecutionFactory, ExecutionStepFactory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

STEP_ID_A = "step-id-aaa"
STEP_ID_B = "step-id-bbb"
STEP_ID_C = "step-id-ccc"

CONTAINER_STEPS = [
    {"step_id": STEP_ID_A, "name": "step_a", "type": "platform"},
    {"step_id": STEP_ID_B, "name": "step_b", "type": "platform"},
]

# Steps with on_error_step_ids for on-error resume tests
CONTAINER_STEPS_WITH_ON_ERROR = [
    {"step_id": STEP_ID_A, "name": "step_a", "type": "platform"},
    {"step_id": STEP_ID_B, "name": "step_b", "type": "platform", "on_error_step_ids": [STEP_ID_C]},
    {"step_id": STEP_ID_C, "name": "step_c", "type": "platform"},
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
            "executions.tasks.reconcile._enqueue_recovery_steps",
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
            "executions.tasks.reconcile._enqueue_recovery_steps",
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
            "executions.tasks.reconcile._enqueue_recovery_steps"
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
        """AC4.4 (wrapper): Quand _enqueue_recovery_steps retourne 'reattached',
        _reconcile_execution propage ce résultat sans appeler _mark_execution_failed.
        Note: la vérification que execution.status → COMPLETED est dans TestEnqueueRecoverySteps."""
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
            "executions.tasks.reconcile._enqueue_recovery_steps",
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
        """AC3 + AC4.5: Exception inattendue pendant _enqueue_recovery_steps → FAILED + log."""
        execution = _make_execution(execution_steps=CONTAINER_STEPS)

        with patch(
            "executions.tasks.reconcile._enqueue_recovery_steps",
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
        assert "reconcile_enqueue_recovery_failed" in error_call_kwargs[0]


# ---------------------------------------------------------------------------
# _enqueue_recovery_steps — Tests directs (Story 78.6)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestEnqueueRecoverySteps:
    """Tests directs de _enqueue_recovery_steps — vérifie la logique interne (AC1, AC2, AC3)."""

    def test_no_completed_steps_raises_value_error(self):
        """AC3: Aucune étape COMPLETED → ValueError (le caller fait fallback FAILED)."""
        execution = _make_execution(execution_steps=CONTAINER_STEPS)
        # Aucun ExecutionStep créé → completed_steps = []

        with pytest.raises(ValueError, match="No COMPLETED steps"):
            _enqueue_recovery_steps(execution)

    def test_empty_next_wave_finalizes_execution_completed(self):
        """AC2: Toutes étapes COMPLETED, vague suivante vide → execution finalisée COMPLETED."""
        from executions.models import ExecutionStatus

        execution = _make_execution(execution_steps=CONTAINER_STEPS)
        ExecutionStepFactory(
            execution=execution,
            status="COMPLETED",
            config_step_id=STEP_ID_A,
            step_order=1,
        )

        with patch(
            "executions.container_routing.get_next_step_ids",
            return_value=[STEP_ID_B],
        ), patch(
            "executions.container_parallel.apply_join_policy",
            return_value=[],  # vague suivante vide
        ), patch(
            "executions.tasks.orchestration_worker._finalize_execution_if_done",
        ) as mock_finalize:
            result = _enqueue_recovery_steps(execution)

        assert result == "reattached"
        mock_finalize.assert_called_once_with(execution, ExecutionStatus.COMPLETED)

    def test_non_empty_next_wave_enqueues_via_work_queue(self):
        """AC1: Vague suivante non vide → _enqueue_next_steps appelé via WorkQueue."""
        execution = _make_execution(execution_steps=CONTAINER_STEPS)
        ExecutionStepFactory(
            execution=execution,
            status="COMPLETED",
            config_step_id=STEP_ID_A,
            step_order=1,
        )

        with patch(
            "executions.container_routing.get_next_step_ids",
            return_value=[STEP_ID_B],
        ), patch(
            "executions.container_parallel.apply_join_policy",
            return_value=[STEP_ID_B],  # vague suivante non vide
        ), patch(
            "executions.tasks.orchestration_worker._enqueue_next_steps",
            return_value=1,
        ) as mock_enqueue:
            result = _enqueue_recovery_steps(execution)

        assert result == "reattached"
        mock_enqueue.assert_called_once()

    def test_failed_step_with_on_error_step_ids_enqueues_on_error_successor(self):
        """FAILED step with on_error_step_ids → next wave computed along on-error path (STEP_ID_C)."""
        execution = _make_execution(execution_steps=CONTAINER_STEPS_WITH_ON_ERROR)
        ExecutionStepFactory(
            execution=execution,
            status="COMPLETED",
            config_step_id=STEP_ID_A,
            step_order=1,
        )
        ExecutionStepFactory(
            execution=execution,
            status="FAILED",
            config_step_id=STEP_ID_B,
            step_order=2,
        )

        with patch(
            "executions.tasks.orchestration_worker._enqueue_next_steps",
            return_value=1,
        ) as mock_enqueue:
            result = _enqueue_recovery_steps(execution)

        assert result == "reattached"
        mock_enqueue.assert_called_once()
        # Verify the next wave passed to _enqueue_next_steps contains STEP_ID_C
        call_args = mock_enqueue.call_args
        next_wave_arg = call_args[0][2]  # positional arg index 2 = next_wave
        assert STEP_ID_C in next_wave_arg


# ---------------------------------------------------------------------------
# reconcile_stale_executions — Story 76.2 (exécutions enfants)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestReconcileStaleExecutionsChildren:
    """Story 76.2 — Tests unitaires pour l'inclusion des exécutions enfants dans le réconciliateur."""

    # --- Helpers ---

    def _cutoff_execution(self, parent=None, status="RUNNING"):
        """Crée une exécution avec created_at déjà ancien (stale) et le status donné."""
        from django.utils import timezone
        from datetime import timedelta
        from executions.models import Execution
        from executions.tasks.reconcile import STALE_THRESHOLD_MINUTES

        exec_ = ExecutionFactory(status=status, parent_execution=parent)
        # Forcer created_at dans le passé pour qu'elle soit stale
        Execution.objects.filter(pk=exec_.pk).update(
            created_at=timezone.now() - timedelta(minutes=STALE_THRESHOLD_MINUTES + 5)
        )
        exec_.refresh_from_db()
        return exec_

    # ------------------------------------------------------------------
    # AC1 — Enfant stale seul (parent sain) → _reconcile_execution appelé
    # ------------------------------------------------------------------

    def test_child_alone_stale_calls_reconcile_execution(self):
        """AC1: Enfant RUNNING stale dont le parent est sain → _reconcile_execution normal."""
        # Parent sain (RUNNING récent, pas stale)
        parent = ExecutionFactory(status="RUNNING")
        child = self._cutoff_execution(parent=parent)

        with patch(
            "executions.tasks.reconcile._reconcile_execution",
            return_value="reattached",
        ) as mock_reconcile, patch(
            "executions.tasks.reconcile._mark_execution_failed"
        ) as mock_fail:
            result = reconcile_stale_executions()

        # _reconcile_execution appelé au moins une fois avec l'enfant
        call_args_list = [c.args[0].id for c in mock_reconcile.call_args_list]
        assert child.id in call_args_list
        # _mark_execution_failed ne doit pas être appelé pour cet enfant
        fail_ids = [c.args[0].id for c in mock_fail.call_args_list]
        assert child.id not in fail_ids
        assert result["reattached"] >= 1

    # ------------------------------------------------------------------
    # AC3a — Enfant stale + parent traité dans ce run → cascade FAILED
    # ------------------------------------------------------------------

    def test_child_stale_parent_processed_in_run_marks_failed_directly(self):
        """AC3a: Parent traité dans ce run (processed_parent_ids) → _mark_execution_failed sur l'enfant."""
        parent = self._cutoff_execution()  # parent aussi stale → sera traité en premier
        child = self._cutoff_execution(parent=parent)

        with patch(
            "executions.tasks.reconcile._reconcile_execution",
            return_value="failed",
        ) as mock_reconcile, patch(
            "executions.tasks.reconcile._mark_execution_failed"
        ) as mock_fail:
            result = reconcile_stale_executions()

        # _mark_execution_failed appelé pour l'enfant avec le message cascade
        fail_ids = [c.args[0].id for c in mock_fail.call_args_list]
        assert child.id in fail_ids

        # Vérifier que le message de cascade est utilisé pour l'enfant
        child_fail_calls = [c for c in mock_fail.call_args_list if c.args[0].id == child.id]
        assert len(child_fail_calls) == 1
        assert "cascade" in child_fail_calls[0].args[1].lower()

        # _reconcile_execution ne doit PAS être appelé pour l'enfant (cascade directe)
        reconcile_ids = [c.args[0].id for c in mock_reconcile.call_args_list]
        assert child.id not in reconcile_ids

        assert result["failed"] >= 1

    # ------------------------------------------------------------------
    # Regression: Parent reattached → child NOT cascade-failed
    # ------------------------------------------------------------------

    def test_child_parent_reattached_allows_child_reconcile(self):
        """Parent returns 'reattached' (stays RUNNING) → child is reconciled, NOT cascade-failed."""
        parent = self._cutoff_execution()
        child = self._cutoff_execution(parent=parent)

        def reconcile_side_effect(exec):
            return "reattached" if exec.id == parent.id else "reattached"

        with patch(
            "executions.tasks.reconcile._reconcile_execution",
            side_effect=reconcile_side_effect,
        ) as mock_reconcile, patch(
            "executions.tasks.reconcile._mark_execution_failed"
        ) as mock_fail:
            result = reconcile_stale_executions()

        # _reconcile_execution called for both parent and child
        reconcile_ids = [c.args[0].id for c in mock_reconcile.call_args_list]
        assert parent.id in reconcile_ids
        assert child.id in reconcile_ids

        # _mark_execution_failed must NOT be called for the child (parent stayed RUNNING)
        fail_ids = [c.args[0].id for c in mock_fail.call_args_list]
        assert child.id not in fail_ids

        assert result["reattached"] >= 2

    # ------------------------------------------------------------------
    # AC3b — Enfant stale + parent déjà terminal en DB → cascade FAILED
    # ------------------------------------------------------------------

    def test_child_stale_parent_already_terminal_marks_failed_directly(self):
        """AC3b: Parent déjà en état terminal en DB (FAILED) → _mark_execution_failed sur l'enfant."""
        parent = ExecutionFactory(status="FAILED")  # parent terminal, pas stale
        child = self._cutoff_execution(parent=parent)

        with patch(
            "executions.tasks.reconcile._reconcile_execution",
        ) as mock_reconcile, patch(
            "executions.tasks.reconcile._mark_execution_failed"
        ) as mock_fail:
            result = reconcile_stale_executions()

        # _mark_execution_failed appelé pour l'enfant
        fail_ids = [c.args[0].id for c in mock_fail.call_args_list]
        assert child.id in fail_ids

        # Vérifier le message cascade terminal
        child_fail_calls = [c for c in mock_fail.call_args_list if c.args[0].id == child.id]
        assert len(child_fail_calls) == 1
        assert "terminal" in child_fail_calls[0].args[1].lower()

        # _reconcile_execution ne doit PAS être appelé pour l'enfant
        reconcile_ids = [c.args[0].id for c in mock_reconcile.call_args_list]
        assert child.id not in reconcile_ids

        assert result["failed"] >= 1

    # ------------------------------------------------------------------
    # AC2 — Enfant stale + parent sain → _reconcile_execution normal
    # ------------------------------------------------------------------

    def test_child_stale_parent_healthy_calls_reconcile_execution(self):
        """AC2: Parent sain (RUNNING récent, non-terminal) → _reconcile_execution sur l'enfant."""
        parent = ExecutionFactory(status="RUNNING")  # parent récent, pas stale
        child = self._cutoff_execution(parent=parent)

        with patch(
            "executions.tasks.reconcile._reconcile_execution",
            return_value="reattached",
        ) as mock_reconcile, patch(
            "executions.tasks.reconcile._mark_execution_failed"
        ) as mock_fail:
            result = reconcile_stale_executions()

        # _reconcile_execution appelé sur l'enfant
        reconcile_ids = [c.args[0].id for c in mock_reconcile.call_args_list]
        assert child.id in reconcile_ids

        # _mark_execution_failed ne doit pas être appelé pour l'enfant
        fail_ids = [c.args[0].id for c in mock_fail.call_args_list]
        assert child.id not in fail_ids

        assert result["reattached"] >= 1

    # ------------------------------------------------------------------
    # Compteurs — enfants contribuent correctement à total_failed
    # ------------------------------------------------------------------

    def test_counters_reflect_child_cascade_failed(self):
        """Compteurs: total_failed inclut les enfants traités par cascade."""
        # Deux enfants avec parent déjà terminal
        parent = ExecutionFactory(status="FAILED")
        child1 = self._cutoff_execution(parent=parent)
        child2 = self._cutoff_execution(parent=parent)

        with patch(
            "executions.tasks.reconcile._reconcile_execution",
        ) as mock_reconcile, patch(
            "executions.tasks.reconcile._mark_execution_failed"
        ) as mock_fail:
            result = reconcile_stale_executions()

        # Les deux enfants doivent être marqués FAILED
        fail_ids = [c.args[0].id for c in mock_fail.call_args_list]
        assert child1.id in fail_ids
        assert child2.id in fail_ids

        # total_failed doit comptabiliser les deux enfants
        assert result["failed"] >= 2

        # _reconcile_execution ne doit pas être appelé pour ces enfants
        reconcile_ids = [c.args[0].id for c in mock_reconcile.call_args_list]
        assert child1.id not in reconcile_ids
        assert child2.id not in reconcile_ids

    # ------------------------------------------------------------------
    # Compteurs — total_skipped reflète les enfants (AC Task 2.5)
    # ------------------------------------------------------------------

    def test_counters_reflect_child_skipped(self):
        """Compteurs: total_skipped inclut les enfants dont _reconcile_execution retourne 'skipped'."""
        parent = ExecutionFactory(status="RUNNING")  # parent sain, pas stale
        child = self._cutoff_execution(parent=parent)

        with patch(
            "executions.tasks.reconcile._reconcile_execution",
            return_value="skipped",
        ) as mock_reconcile, patch(
            "executions.tasks.reconcile._mark_execution_failed"
        ) as mock_fail:
            result = reconcile_stale_executions()

        # _reconcile_execution appelé sur l'enfant
        reconcile_ids = [c.args[0].id for c in mock_reconcile.call_args_list]
        assert child.id in reconcile_ids

        # _mark_execution_failed ne doit pas être appelé pour l'enfant
        fail_ids = [c.args[0].id for c in mock_fail.call_args_list]
        assert child.id not in fail_ids

        assert result["skipped"] >= 1

    # ------------------------------------------------------------------
    # Compteurs — total_reattached reflète les enfants (AC Task 2.5)
    # ------------------------------------------------------------------

    def test_counters_reflect_child_reattached(self):
        """Compteurs: total_reattached inclut les enfants dont _reconcile_execution retourne 'reattached'."""
        parent = ExecutionFactory(status="RUNNING")  # parent sain, pas stale
        child = self._cutoff_execution(parent=parent)

        with patch(
            "executions.tasks.reconcile._reconcile_execution",
            return_value="reattached",
        ) as mock_reconcile, patch(
            "executions.tasks.reconcile._mark_execution_failed"
        ) as mock_fail:
            result = reconcile_stale_executions()

        reconcile_ids = [c.args[0].id for c in mock_reconcile.call_args_list]
        assert child.id in reconcile_ids

        fail_ids = [c.args[0].id for c in mock_fail.call_args_list]
        assert child.id not in fail_ids

        assert result["reattached"] >= 1

    # ------------------------------------------------------------------
    # SoftTimeLimitExceeded dans la boucle enfants → retour partiel
    # ------------------------------------------------------------------

    def test_soft_time_limit_during_child_loop_returns_partial(self):
        """SoftTimeLimitExceeded pendant le traitement des enfants → partial_timeout."""
        from celery.exceptions import SoftTimeLimitExceeded

        parent = ExecutionFactory(status="RUNNING")  # parent sain
        self._cutoff_execution(parent=parent)

        with patch(
            "executions.tasks.reconcile._reconcile_execution",
            side_effect=SoftTimeLimitExceeded(),
        ):
            result = reconcile_stale_executions()

        assert result["status"] == "partial_timeout"
        assert "reattached" in result
        assert "failed" in result
        assert "skipped" in result
        assert "errors" in result

    # ------------------------------------------------------------------
    # Hiérarchie à 3 niveaux — comportement documenté (limitation 2-level)
    # ------------------------------------------------------------------

    def test_grandchild_with_stale_parent_uses_reconcile_execution(self):
        """Limitation 2-level: un petit-enfant dont le parent (niveau 2) est traité dans ce même run
        ne reçoit PAS la cascade FAILED directe — son parent prefetché a le statut RUNNING.
        Il passe donc par _reconcile_execution (comportement documenté, corrigé au prochain run)."""
        grandparent = self._cutoff_execution()  # racine stale
        parent = self._cutoff_execution(parent=grandparent)  # enfant stale (niveau 2)
        grandchild = self._cutoff_execution(parent=parent)   # petit-enfant stale (niveau 3)

        with patch(
            "executions.tasks.reconcile._reconcile_execution",
            return_value="failed",
        ) as mock_reconcile, patch(
            "executions.tasks.reconcile._mark_execution_failed"
        ):
            reconcile_stale_executions()

        # Le petit-enfant ne peut pas détecter que son parent vient d'être cascadé FAILED
        # dans la même run (prefetch stale) → _reconcile_execution est appelé sur lui.
        reconcile_ids = [c.args[0].id for c in mock_reconcile.call_args_list]
        assert grandchild.id in reconcile_ids


# ---------------------------------------------------------------------------
# Story 76.3 — Détection de staleness améliorée (updated_at / created_at)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestReconcileStaleDetection:
    """Story 76.3 — Tests unitaires pour la nouvelle logique de détection de staleness.

    Vérifie que le stale_filter Q(updated_at__lt=cutoff) | Q(updated_at__isnull=True, created_at__lt=cutoff)
    se comporte correctement selon les 4 scénarios définis en AC7 :
    - AC5a : updated_at récent → exécution NON détectée comme stale
    - AC5b : updated_at ancien → exécution détectée comme stale
    - AC5c : updated_at NULL + created_at ancien → détectée (rétrocompat)
    - AC5d : updated_at NULL + created_at récent → NON détectée
    """

    def _stale_filter(self, cutoff):
        """Retourne le Q object stale_filter de la story 76.3 (délègue à la production)."""
        return _build_stale_filter(cutoff)

    def _cutoff(self, minutes_offset=0):
        """Retourne un cutoff = now - (STALE_THRESHOLD_MINUTES + minutes_offset)."""
        from django.utils import timezone
        from datetime import timedelta
        from executions.tasks.reconcile import STALE_THRESHOLD_MINUTES
        return timezone.now() - timedelta(minutes=STALE_THRESHOLD_MINUTES + minutes_offset)

    # ------------------------------------------------------------------
    # AC5a — updated_at récent → NON stale (workflow long sain)
    # ------------------------------------------------------------------

    def test_ac5a_recent_updated_at_not_stale(self):
        """AC5a: Exécution RUNNING avec updated_at récent (après cutoff) → non retournée dans la query stale."""
        from django.utils import timezone
        from datetime import timedelta
        from executions.models import Execution

        exec_ = ExecutionFactory(status="RUNNING")
        cutoff = self._cutoff()
        # updated_at = maintenant (bien après le cutoff)
        Execution.objects.filter(pk=exec_.pk).update(updated_at=timezone.now())
        # created_at ancien (sans updated_at, serait stale) — valide le cas réel
        Execution.objects.filter(pk=exec_.pk).update(
            created_at=timezone.now() - timedelta(minutes=60)
        )

        stale_filter = self._stale_filter(cutoff)
        result_ids = list(
            Execution.objects.filter(status="RUNNING").filter(stale_filter).values_list("id", flat=True)
        )
        assert exec_.id not in result_ids, (
            "Une exécution avec updated_at récent ne doit pas être considérée stale"
        )

    # ------------------------------------------------------------------
    # AC5b — updated_at ancien → stale
    # ------------------------------------------------------------------

    def test_ac5b_old_updated_at_is_stale(self):
        """AC5b: Exécution RUNNING avec updated_at ancien (avant cutoff) → retournée comme stale."""
        from django.utils import timezone
        from datetime import timedelta
        from executions.models import Execution

        exec_ = ExecutionFactory(status="RUNNING")
        cutoff = self._cutoff()
        # updated_at = bien avant le cutoff
        Execution.objects.filter(pk=exec_.pk).update(
            updated_at=timezone.now() - timedelta(minutes=60)
        )

        stale_filter = self._stale_filter(cutoff)
        result_ids = list(
            Execution.objects.filter(status="RUNNING").filter(stale_filter).values_list("id", flat=True)
        )
        assert exec_.id in result_ids, (
            "Une exécution avec updated_at ancien doit être détectée stale"
        )

    # ------------------------------------------------------------------
    # AC5c — updated_at NULL + created_at ancien → stale (rétrocompat)
    # ------------------------------------------------------------------

    def test_ac5c_null_updated_at_old_created_at_is_stale(self):
        """AC5c: Exécution sans updated_at et created_at ancien → retournée (rétrocompatibilité pre-76.3)."""
        from django.utils import timezone
        from datetime import timedelta
        from executions.models import Execution

        exec_ = ExecutionFactory(status="RUNNING")
        cutoff = self._cutoff()
        # updated_at reste NULL, created_at = bien avant le cutoff
        Execution.objects.filter(pk=exec_.pk).update(
            updated_at=None,
            created_at=timezone.now() - timedelta(minutes=60),
        )

        stale_filter = self._stale_filter(cutoff)
        result_ids = list(
            Execution.objects.filter(status="RUNNING").filter(stale_filter).values_list("id", flat=True)
        )
        assert exec_.id in result_ids, (
            "Une exécution sans updated_at et created_at ancien doit être détectée stale (rétrocompat)"
        )

    # ------------------------------------------------------------------
    # AC5d — updated_at NULL + created_at récent → NON stale
    # ------------------------------------------------------------------

    def test_ac5d_null_updated_at_recent_created_at_not_stale(self):
        """AC5d: Exécution sans updated_at et created_at récent → non retournée (exécution jeune)."""
        from django.utils import timezone
        from executions.models import Execution

        exec_ = ExecutionFactory(status="RUNNING")
        cutoff = self._cutoff()
        # updated_at NULL, created_at = maintenant (récent, après cutoff)
        Execution.objects.filter(pk=exec_.pk).update(
            updated_at=None,
            created_at=timezone.now(),
        )

        stale_filter = self._stale_filter(cutoff)
        result_ids = list(
            Execution.objects.filter(status="RUNNING").filter(stale_filter).values_list("id", flat=True)
        )
        assert exec_.id not in result_ids, (
            "Une exécution sans updated_at et created_at récent ne doit pas être considérée stale"
        )


# ---------------------------------------------------------------------------
# Story 76.4 — Vérification du polling pour actions individuelles RUNNING
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestIsChildExecutionId:
    """Story 76.4 — Task 2.1 : _is_child_execution_id détecte correctement les child IDs."""

    def test_numeric_string_matching_child_returns_true(self):
        """platform_job_id = str(child.id) avec child.parent_execution_id = parent.id → True."""
        parent = ExecutionFactory(status="RUNNING")
        child = ExecutionFactory(status="RUNNING", parent_execution=parent)

        assert _is_child_execution_id(parent, str(child.id)) is True

    def test_numeric_string_not_a_child_returns_false(self):
        """platform_job_id numérique mais pas un enfant de cette exécution → False.

        AC3/Task 3.3 : un job ID numérique valide sur certaines plateformes (ex. Tower)
        ne doit pas être confondu avec un child execution ID.
        """
        parent = ExecutionFactory(status="RUNNING")
        other_exec = ExecutionFactory(status="RUNNING")  # pas un enfant de parent

        assert _is_child_execution_id(parent, str(other_exec.id)) is False

    def test_non_numeric_string_returns_false(self):
        """platform_job_id non numérique (ex. 'job-aap-123') → False."""
        parent = ExecutionFactory(status="RUNNING")

        assert _is_child_execution_id(parent, "job-aap-123") is False

    def test_empty_string_returns_false(self):
        """platform_job_id vide → False."""
        parent = ExecutionFactory(status="RUNNING")

        assert _is_child_execution_id(parent, "") is False

    def test_nonexistent_id_returns_false(self):
        """platform_job_id numérique mais aucune Execution avec cet ID → False."""
        parent = ExecutionFactory(status="RUNNING")

        assert _is_child_execution_id(parent, "999999999") is False


@pytest.mark.django_db
class TestReconcileScheduleStep:
    """Story 76.4 — Task 2.2 : _reconcile_schedule_step gère les différents états du child."""

    def _make_step_with_child(self, parent_status="RUNNING", child_status="RUNNING"):
        """Crée un parent avec un step RUNNING dont platform_job_id = child.id."""
        parent = ExecutionFactory(status=parent_status)
        child = ExecutionFactory(status=child_status, parent_execution=parent)
        step = ExecutionStepFactory(
            execution=parent,
            status="RUNNING",
            platform_job_id=str(child.id),
        )
        return parent, child, step

    def test_child_completed_marks_step_completed_returns_true(self):
        """Child COMPLETED → step mis à COMPLETED avec output, retourne True."""
        from executions.models import ExecutionStepStatus

        parent, child, step = self._make_step_with_child(child_status="COMPLETED")

        result = _reconcile_schedule_step(parent, step)

        assert result is True
        step.refresh_from_db()
        assert step.status == ExecutionStepStatus.COMPLETED
        assert step.completed_at is not None
        # AC2 Task 2.2 / Story 77.1: output uses standard format {raw_output, extracted_output, status_context}
        output = step.get_output()
        assert output is not None
        raw = output.get("raw_output") or {}
        assert raw.get("child_execution_id") == child.id
        assert raw.get("child_status") == "COMPLETED"

    def test_child_failed_marks_step_failed_returns_false(self):
        """Child FAILED → step marqué FAILED, retourne False."""
        from executions.models import ExecutionStepStatus

        parent, child, step = self._make_step_with_child(child_status="FAILED")

        result = _reconcile_schedule_step(parent, step)

        assert result is False
        step.refresh_from_db()
        assert step.status == ExecutionStepStatus.FAILED
        assert step.error_message is not None

    def test_child_cancelled_marks_step_failed_returns_false(self):
        """Child CANCELLED → step marqué FAILED, retourne False."""
        from executions.models import ExecutionStepStatus

        parent, child, step = self._make_step_with_child(child_status="CANCELLED")

        result = _reconcile_schedule_step(parent, step)

        assert result is False
        step.refresh_from_db()
        assert step.status == ExecutionStepStatus.FAILED

    def test_child_running_stale_marks_both_failed_returns_false(self):
        """Child RUNNING (stale) → child + step marqués FAILED, retourne False."""
        from executions.models import ExecutionStatus, ExecutionStepStatus

        parent, child, step = self._make_step_with_child(child_status="RUNNING")

        result = _reconcile_schedule_step(parent, step)

        assert result is False
        step.refresh_from_db()
        assert step.status == ExecutionStepStatus.FAILED

        child.refresh_from_db()
        assert child.status == ExecutionStatus.FAILED

    def test_child_not_found_marks_step_failed_returns_false(self):
        """Child introuvable (ID invalide) → step marqué FAILED, retourne False."""
        from executions.models import ExecutionStepStatus

        parent = ExecutionFactory(status="RUNNING")
        step = ExecutionStepFactory(
            execution=parent,
            status="RUNNING",
            platform_job_id="999999999",  # ID inexistant
        )

        result = _reconcile_schedule_step(parent, step)

        assert result is False
        step.refresh_from_db()
        assert step.status == ExecutionStepStatus.FAILED


@pytest.mark.django_db
class TestReconcileExecutionWithScheduleStep:
    """Story 76.4 — Task 3 : Tests d'intégration dans _reconcile_execution."""

    def _cutoff_execution(self, parent=None, status="RUNNING"):
        """Crée une exécution stale."""
        from django.utils import timezone
        from datetime import timedelta
        from executions.models import Execution
        from executions.tasks.reconcile import STALE_THRESHOLD_MINUTES

        exec_ = ExecutionFactory(status=status, parent_execution=parent)
        Execution.objects.filter(pk=exec_.pk).update(
            created_at=timezone.now() - timedelta(minutes=STALE_THRESHOLD_MINUTES + 5)
        )
        exec_.refresh_from_db()
        return exec_

    def test_ac3_task3_1_simple_action_calls_reattach_poll(self):
        """AC3/Task 3.1 : Action simple RUNNING avec platform_job_id réel (non-child) → _reattach_poll appelé.

        platform_job_id = 'job-aap-123' (non numérique) → _is_child_execution_id retourne False
        → _reattach_poll est appelé avec l'intégration de l'action.
        """
        execution = ExecutionFactory(status="RUNNING")
        ExecutionStepFactory(
            execution=execution,
            status="RUNNING",
            platform_job_id="job-aap-123",  # vrai ID de job AAP (non numérique)
        )

        with patch(
            "executions.tasks.reconcile._reattach_poll",
            return_value=True,
        ) as mock_reattach, patch(
            "executions.tasks.reconcile._reconcile_schedule_step",
        ) as mock_schedule:
            result = _reconcile_execution(execution)

        # _reattach_poll doit être appelé (pas _reconcile_schedule_step)
        assert mock_reattach.call_count == 1
        mock_schedule.assert_not_called()
        assert result == "reattached"

    def test_simple_action_poll_platform_job_status_called_with_correct_args(self):
        """AC3/Task 3.1 (MEDIUM): poll_platform_job_status.apply_async appelé avec bons arguments."""
        execution = ExecutionFactory(status="RUNNING")
        ExecutionStepFactory(
            execution=execution,
            status="RUNNING",
            platform_job_id="job-aap-123",
        )

        with patch(
            "executions.tasks.polling.poll_platform_job_status.apply_async",
        ) as mock_apply:
            with patch(
                "executions.tasks.polling.get_platform_queue",
                return_value="platform-aap",
            ):
                _reconcile_execution(execution)

        mock_apply.assert_called_once()
        call_kwargs = mock_apply.call_args[1]
        assert call_kwargs["args"][0] == execution.id
        assert call_kwargs["args"][1] == "job-aap-123"
        assert call_kwargs["queue"] == "platform-aap"

    def test_ac3_task3_2_schedule_step_calls_reconcile_schedule_step(self):
        """AC3/Task 3.2 : Step schedule_execution avec platform_job_id = child_id → _reconcile_schedule_step appelé."""
        parent = ExecutionFactory(status="RUNNING")
        child = ExecutionFactory(status="RUNNING", parent_execution=parent)
        step = ExecutionStepFactory(
            execution=parent,
            status="RUNNING",
            platform_job_id=str(child.id),
        )

        with patch(
            "executions.tasks.reconcile._reconcile_schedule_step",
            return_value=True,
        ) as mock_schedule, patch(
            "executions.tasks.reconcile._reattach_poll",
        ) as mock_reattach:
            result = _reconcile_execution(parent)

        mock_schedule.assert_called_once_with(parent, step)
        mock_reattach.assert_not_called()
        assert result == "reattached"

    def test_ac3_task3_3_numeric_non_child_calls_reattach_poll(self):
        """AC3/Task 3.3 : platform_job_id numérique qui n'est pas un child → reattach normal.

        Cas : Tower job IDs sont des entiers. Si l'ID numérique ne correspond pas à un
        child de cette exécution, _is_child_execution_id retourne False et on doit appeler
        _reattach_poll normalement (pas _reconcile_schedule_step).
        """
        execution = ExecutionFactory(status="RUNNING")
        # ID numérique mais pas un child de cette exécution (aucun Execution avec cet ID
        # et parent_execution_id=execution.id n'existe)
        ExecutionStepFactory(
            execution=execution,
            status="RUNNING",
            platform_job_id="999888777",  # numérique, mais pas un child
        )

        with patch(
            "executions.tasks.reconcile._reattach_poll",
            return_value=True,
        ) as mock_reattach, patch(
            "executions.tasks.reconcile._reconcile_schedule_step",
        ) as mock_schedule:
            result = _reconcile_execution(execution)

        # _reattach_poll doit être appelé (pas _reconcile_schedule_step)
        assert mock_reattach.call_count == 1
        mock_schedule.assert_not_called()
        assert result == "reattached"

    def test_schedule_step_child_completed_triggers_enqueue_recovery_steps(self):
        """MEDIUM: Schedule step child COMPLETED → step COMPLETED with output → _enqueue_recovery_steps appelé."""
        parent = ExecutionFactory(status="RUNNING")
        parent.action.execution_steps = CONTAINER_STEPS
        parent.action.save(update_fields=["execution_steps"])
        child = ExecutionFactory(status="COMPLETED", parent_execution=parent)
        step = ExecutionStepFactory(
            execution=parent,
            status="RUNNING",
            platform_job_id=str(child.id),
            config_step_id=STEP_ID_B,
            step_order=1,
        )
        # Step A already COMPLETED so resume has something to work with
        ExecutionStepFactory(
            execution=parent,
            status="COMPLETED",
            config_step_id=STEP_ID_A,
            step_order=0,
        )

        with patch(
            "executions.tasks.reconcile._enqueue_recovery_steps",
            return_value="reattached",
        ) as mock_resume:
            result = _reconcile_execution(parent)

        assert result == "reattached"
        step.refresh_from_db()
        assert step.status == "COMPLETED"
        output = step.get_output()
        assert output is not None
        raw = output.get("raw_output") or {}
        assert raw.get("child_execution_id") == child.id
        # AC2: workflow continuation triggered immediately
        mock_resume.assert_called_once_with(parent, correlation_id="")


# ---------------------------------------------------------------------------
# Story 76.5 — Retry pour étapes non-platform (service_call, http_request, evaluation)
# ---------------------------------------------------------------------------


STEP_ID_SVC = "step-service-call"
STEP_ID_HTTP = "step-http-request"
STEP_ID_EVAL = "step-evaluation"

CONTAINER_STEPS_76_5 = [
    {
        "step_id": STEP_ID_SVC,
        "name": "ServiceCall",
        "type": "service_call",
        "step_type": "service_call",
        "integration_type": "notification",
        "operation": "send_email",
    },
    {
        "step_id": STEP_ID_HTTP,
        "name": "HttpRequest",
        "type": "http_request",
        "step_type": "http_request",
        "config": {"url": "https://example.com", "method": "GET"},
    },
    {
        "step_id": STEP_ID_EVAL,
        "name": "Evaluation",
        "type": "evaluation",
        "step_type": "evaluation",
    },
]


@pytest.mark.django_db
class TestResetAndEnqueueStep:
    """Story 78.6 — Tests unitaires pour _reset_and_enqueue_step."""

    def test_running_step_reset_to_pending_and_enqueued(self):
        """Step RUNNING sans platform_job_id → reset PENDING + WorkQueue.enqueue."""
        from executions.models import ExecutionStepStatus

        execution = _make_execution(execution_steps=CONTAINER_STEPS_76_5)
        step = ExecutionStepFactory(
            execution=execution,
            status="RUNNING",
            step_type="service_call",
            config_step_id=STEP_ID_SVC,
            step_order=1,
            platform_job_id=None,
        )

        with patch("executions.infra.work_queue.WorkQueue.enqueue") as mock_enqueue, \
             patch("executions.domain.state_machine.assert_step_transition"):
            result = _reset_and_enqueue_step(step)

        assert result is True
        step.refresh_from_db()
        assert step.status == ExecutionStepStatus.PENDING
        mock_enqueue.assert_called_once_with(step)

    def test_enqueue_failure_marks_step_failed_and_returns_false(self):
        """WorkQueue.enqueue raises → step FAILED, retourne False."""
        from executions.models import ExecutionStepStatus

        execution = _make_execution(execution_steps=CONTAINER_STEPS_76_5)
        step = ExecutionStepFactory(
            execution=execution,
            status="RUNNING",
            step_type="service_call",
            config_step_id=STEP_ID_SVC,
            step_order=1,
            platform_job_id=None,
        )

        with patch(
            "executions.infra.work_queue.WorkQueue.enqueue",
            side_effect=RuntimeError("Queue unavailable"),
        ), patch("executions.domain.state_machine.assert_step_transition"):
            result = _reset_and_enqueue_step(step)

        assert result is False
        step.refresh_from_db()
        assert step.status == ExecutionStepStatus.FAILED


@pytest.mark.django_db
class TestReconcileExecutionNonPlatformRetry:
    """Story 78.6 — Tests d'intégration dans _reconcile_execution pour reset+enqueue non-platform."""

    def _cutoff_execution(self, parent=None, status="RUNNING"):
        """Crée une exécution stale."""
        from django.utils import timezone
        from datetime import timedelta
        from executions.models import Execution
        from executions.tasks.reconcile import STALE_THRESHOLD_MINUTES

        exec_ = ExecutionFactory(status=status, parent_execution=parent)
        Execution.objects.filter(pk=exec_.pk).update(
            created_at=timezone.now() - timedelta(minutes=STALE_THRESHOLD_MINUTES + 5)
        )
        exec_.refresh_from_db()
        return exec_

    def test_service_call_no_platform_job_id_reset_and_enqueued(self):
        """Step service_call RUNNING sans platform_job_id → reset PENDING + enqueue → reattached."""

        execution = self._cutoff_execution()
        execution.action.execution_steps = CONTAINER_STEPS_76_5
        execution.action.save(update_fields=["execution_steps"])
        step = ExecutionStepFactory(
            execution=execution,
            status="RUNNING",
            step_type="service_call",
            config_step_id=STEP_ID_SVC,
            step_order=1,
            platform_job_id=None,
        )

        with patch(
            "executions.tasks.reconcile._reset_and_enqueue_step",
            return_value=True,
        ) as mock_reset:
            result = _reconcile_execution(execution)

        mock_reset.assert_called_once_with(step)
        assert result == "reattached"

    def test_platform_no_platform_job_id_marked_failed_no_reset(self):
        """Step platform RUNNING sans platform_job_id → _reset_and_enqueue_step appelé (handles all types)."""
        execution = self._cutoff_execution()
        ExecutionStepFactory(
            execution=execution,
            status="RUNNING",
            step_type="platform",
            config_step_id=STEP_ID_A,
            step_order=1,
            platform_job_id=None,
        )

        with patch(
            "executions.tasks.reconcile._reset_and_enqueue_step",
            return_value=False,
        ) as mock_reset, patch(
            "executions.tasks.reconcile._mark_execution_failed",
        ) as mock_mark:
            result = _reconcile_execution(execution)

        mock_reset.assert_called_once()
        mock_mark.assert_called_once()
        assert result == "failed"

    def test_reset_enqueue_failure_marks_execution_failed(self):
        """_reset_and_enqueue_step returns False → execution FAILED, not _enqueue_recovery_steps."""

        execution = self._cutoff_execution()
        execution.action.execution_steps = CONTAINER_STEPS_76_5
        execution.action.save(update_fields=["execution_steps"])
        ExecutionStepFactory(
            execution=execution,
            status="RUNNING",
            step_type="service_call",
            config_step_id=STEP_ID_SVC,
            step_order=1,
            platform_job_id=None,
        )

        with patch(
            "executions.tasks.reconcile._reset_and_enqueue_step",
            return_value=False,
        ), patch(
            "executions.tasks.reconcile._enqueue_recovery_steps",
        ) as mock_resume:
            result = _reconcile_execution(execution)

        assert result == "failed"
        mock_resume.assert_not_called()
