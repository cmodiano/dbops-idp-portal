"""
Package executions/tasks — Celery tasks for workflow execution.

Ce package regroupe les tâches Celery par responsabilité :
- gates    : évaluation périodique des conditions WAITING
- polling  : surveillance des jobs sur les plateformes externes
- trigger  : déclenchement asynchrone des jobs sur les plateformes externes (Story 47.2)

Les helpers internes et dépendances sont ré-exportés ici pour que les patches
de tests utilisant @patch("executions.tasks.X") continuent de fonctionner.
"""
import structlog

from core.middleware import get_correlation_id
from core.services import AuditService

# Re-export logger at package level for test patchability (@patch("executions.tasks.logger"))
logger = structlog.get_logger("executions.tasks")

from executions.tasks.gates import (  # noqa: E402
    evaluate_waiting_gates,
    _handle_gate_timeout,
    _transition_step_to_running,
    _update_waiting_context,
)
from executions.tasks.scheduled import (  # noqa: E402
    process_pending_scheduled_executions,
    _update_recurring_scheduled_execution,
)
from executions.tasks.polling import (  # noqa: E402
    poll_platform_job_status,
    MAX_POLLING_RETRIES,
    _mark_execution_polling_exhausted,
    _broadcast_execution_update,
    _update_execution_from_poll,
    _forward_platform_logs_to_splunk,
)
from executions.tasks.trigger import trigger_platform_job  # noqa: E402
from executions.tasks.cleanup import purge_old_platform_logs, purge_old_workflow_events  # noqa: E402
from executions.tasks.reconcile import reconcile_stale_executions, process_pending_workflow_commands  # noqa: E402
from executions.tasks.outbox_dispatcher import process_outbox_entries  # noqa: E402
from executions.tasks.orchestration_worker import process_runnable_steps, execute_single_runnable_step  # noqa: E402

__all__ = [
    # Public tasks
    "evaluate_waiting_gates",
    "poll_platform_job_status",
    "trigger_platform_job",
    "reconcile_stale_executions",
    # Constants
    "MAX_POLLING_RETRIES",
    # Story 42.1: Celery Beat task for scheduled executions
    "process_pending_scheduled_executions",
    # Story 78.5: WorkQueue consumer
    "process_runnable_steps",
    "execute_single_runnable_step",
    # Internal helpers re-exported for test patchability
    "logger",
    "get_correlation_id",
    "AuditService",
    "_handle_gate_timeout",
    "_transition_step_to_running",
    "_update_waiting_context",
    "_update_recurring_scheduled_execution",
    "_mark_execution_polling_exhausted",
    "_broadcast_execution_update",
    "_update_execution_from_poll",
    "_forward_platform_logs_to_splunk",
    # Cleanup tasks
    "purge_old_platform_logs",
    "purge_old_workflow_events",
    # Story 78.7: Outbox dispatcher
    "process_outbox_entries",
    # Story 78.5: WorkflowCommand processor
    "process_pending_workflow_commands",
]
