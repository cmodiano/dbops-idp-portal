"""Tests pour executions.app.orchestrator — Story 85.3, 88.1."""
from unittest.mock import MagicMock, patch

from executions.models import ExecutionStatus


def test_import_from_app_orchestrator():
    """Vérifier que l'import depuis app.orchestrator fonctionne."""
    from executions.app.orchestrator import (
        process_runnable_steps,
        _finalize_execution_if_done,
        _enqueue_next_steps,
        _build_runtime_for_step,
    )
    assert process_runnable_steps is not None
    assert _finalize_execution_if_done is not None
    assert _enqueue_next_steps is not None
    assert _build_runtime_for_step is not None


def test_process_runnable_steps_empty_queue():
    """process_runnable_steps retourne processed=0 si la queue est vide."""
    from executions.app.orchestrator import process_runnable_steps
    mock_depth = {"pending": 0, "running": 0, "expired_leases": 0}
    with patch("executions.app.orchestrator.get_runnable_queue_depth", return_value=mock_depth), \
         patch("executions.app.orchestrator.WorkQueue.claim", return_value=[]):
        result = process_runnable_steps()
    assert result["dispatched"] == 0
    assert "worker_id" in result
    assert result["runnable_queue_depth"] == 0
    assert result["runnable_expired_leases"] == 0


# ---------------------------------------------------------------------------
# Story 88.1 — BUG-BE-01: Variable scope hors transaction.atomic()
# ---------------------------------------------------------------------------


class TestForceFinalizeCASZeroRows:
    """BUG-BE-01: Quand le CAS filter ne matche aucune ligne, pas de broadcast/audit."""

    def test_force_finalize_cas_zero_rows_no_broadcast(self):
        """_force_finalize_execution ne broadcast pas quand updated==0 (race perdue)."""
        from executions.app.orchestrator import _force_finalize_execution

        execution = MagicMock()
        execution.status = ExecutionStatus.RUNNING
        execution.id = 42

        mock_qs = MagicMock()
        mock_qs.update.return_value = 0  # CAS matched zero rows

        with patch("executions.app.orchestrator.Execution.objects.filter", return_value=mock_qs), \
             patch("executions.app.orchestrator.logger") as mock_logger:
            _force_finalize_execution(execution, ExecutionStatus.FAILED, "timeout")

        # updated == 0 → no broadcast, no audit, no log
        mock_logger.info.assert_not_called()

    def test_force_finalize_cas_success_broadcasts(self):
        """_force_finalize_execution broadcasts quand updated>0."""
        from executions.app.orchestrator import _force_finalize_execution

        execution = MagicMock()
        execution.status = ExecutionStatus.RUNNING
        execution.id = 42

        mock_qs = MagicMock()
        mock_qs.update.return_value = 1  # CAS matched

        with patch("executions.app.orchestrator.Execution.objects.filter", return_value=mock_qs), \
             patch("executions.app.orchestrator.logger") as mock_logger, \
             patch("executions.container_workflow_runtime._broadcast_terminal"), \
             patch("core.services.AuditService.create_entry"):
            _force_finalize_execution(execution, ExecutionStatus.FAILED)

        mock_logger.info.assert_called_once_with(
            "execution_force_finalized",
            execution_id=42,
            status=ExecutionStatus.FAILED,
        )


class TestFinalizeIfDoneCASZeroRows:
    """BUG-BE-01: Quand le CAS filter ne matche aucune ligne dans _finalize_execution_if_done."""

    def test_finalize_if_done_cas_zero_rows_no_broadcast(self):
        """_finalize_execution_if_done ne broadcast pas quand CAS updated==0."""
        from executions.app.orchestrator import _finalize_execution_if_done

        execution = MagicMock()
        execution.id = 42
        execution.status = ExecutionStatus.RUNNING

        # Mock ExecutionStep.objects.filter().exists() pour has_active_steps=False, has_waiting=False, has_failed=False
        step_filter_mock = MagicMock()
        step_filter_mock.exists.return_value = False

        # Mock Execution.objects.filter().exclude().update() → 0 (race perdue)
        exec_filter_mock = MagicMock()
        exec_exclude_mock = MagicMock()
        exec_filter_mock.exclude.return_value = exec_exclude_mock
        exec_exclude_mock.update.return_value = 0

        with patch("executions.app.orchestrator.ExecutionStep.objects.filter", return_value=step_filter_mock), \
             patch("executions.app.orchestrator.Execution.objects.filter", return_value=exec_filter_mock), \
             patch("executions.app.orchestrator.assert_execution_transition"), \
             patch("executions.app.orchestrator.logger") as mock_logger:
            _finalize_execution_if_done(execution, ExecutionStatus.COMPLETED)

        # updated == 0 → no "worker_execution_finalized" log
        for call in mock_logger.info.call_args_list:
            assert call[0][0] != "worker_execution_finalized"


# ---------------------------------------------------------------------------
# Story 88.1 — ERR-BE-01: except Exception: logger.debug() (was pass)
# ---------------------------------------------------------------------------


class TestForceFinalizeBestEffortLogging:
    """ERR-BE-01: Best-effort blocks log exceptions via logger.debug instead of silencing."""

    def test_broadcast_failure_logged_as_debug(self):
        """_force_finalize_execution logs broadcast errors at debug level."""
        from executions.app.orchestrator import _force_finalize_execution

        execution = MagicMock()
        execution.status = ExecutionStatus.RUNNING
        execution.id = 42
        execution.correlation_id = "corr-123"

        mock_qs = MagicMock()
        mock_qs.update.return_value = 1

        with patch("executions.app.orchestrator.Execution.objects.filter", return_value=mock_qs), \
             patch("executions.app.orchestrator.logger") as mock_logger, \
             patch("executions.container_workflow_runtime._broadcast_terminal", side_effect=RuntimeError("ws down")), \
             patch("core.services.AuditService.create_entry"):
            _force_finalize_execution(execution, ExecutionStatus.FAILED)

        mock_logger.debug.assert_any_call(
            "broadcast_terminal_best_effort_failed",
            execution_id=42,
            correlation_id="corr-123",
            exc_info=True,
        )

    def test_audit_failure_logged_as_warning(self):
        """_force_finalize_execution logs audit errors at warning level (compliance-critical)."""
        from executions.app.orchestrator import _force_finalize_execution

        execution = MagicMock()
        execution.status = ExecutionStatus.RUNNING
        execution.id = 42
        execution.correlation_id = "corr-456"

        mock_qs = MagicMock()
        mock_qs.update.return_value = 1

        with patch("executions.app.orchestrator.Execution.objects.filter", return_value=mock_qs), \
             patch("executions.app.orchestrator.logger") as mock_logger, \
             patch("executions.container_workflow_runtime._broadcast_terminal"), \
             patch("core.services.AuditService.create_entry", side_effect=RuntimeError("db down")):
            _force_finalize_execution(execution, ExecutionStatus.FAILED)

        mock_logger.warning.assert_any_call(
            "audit_trail_best_effort_failed",
            execution_id=42,
            correlation_id="corr-456",
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# Story 88.3 — BUG-BE-03: _finalize_execution_if_done logs audit failures at warning
# ---------------------------------------------------------------------------


class TestFinalizeIfDoneAuditLogging:
    """BUG-BE-03: _finalize_execution_if_done logs audit trail failures at warning level."""

    def test_audit_failure_logged_as_warning_in_finalize_if_done(self):
        """_finalize_execution_if_done logs audit errors at warning level (compliance-critical)."""
        from executions.app.orchestrator import _finalize_execution_if_done

        execution = MagicMock()
        execution.id = 43
        execution.status = ExecutionStatus.RUNNING
        execution.correlation_id = "corr-789"

        step_filter_mock = MagicMock()
        step_filter_mock.exists.return_value = False

        exec_filter_mock = MagicMock()
        exec_exclude_mock = MagicMock()
        exec_filter_mock.exclude.return_value = exec_exclude_mock
        exec_exclude_mock.update.return_value = 1  # CAS matched

        with patch("executions.app.orchestrator.ExecutionStep.objects.filter", return_value=step_filter_mock), \
             patch("executions.app.orchestrator.Execution.objects.filter", return_value=exec_filter_mock), \
             patch("executions.app.orchestrator.assert_execution_transition"), \
             patch("executions.app.orchestrator.logger") as mock_logger, \
             patch("executions.container_workflow_runtime._broadcast_terminal"), \
             patch("core.services.AuditService.create_entry", side_effect=RuntimeError("db down")):
            _finalize_execution_if_done(execution, ExecutionStatus.COMPLETED)

        mock_logger.warning.assert_any_call(
            "audit_trail_best_effort_failed",
            execution_id=43,
            correlation_id="corr-789",
            exc_info=True,
        )
