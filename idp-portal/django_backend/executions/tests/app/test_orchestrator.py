"""Tests pour executions.app.orchestrator — Story 85.3."""
from unittest.mock import patch


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
    assert result["processed"] == 0
    assert "worker_id" in result
    assert result["runnable_queue_depth"] == 0
    assert result["runnable_expired_leases"] == 0
