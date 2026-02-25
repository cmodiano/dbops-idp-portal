"""
Package executions/tasks — Celery tasks for workflow execution.

Ce package regroupe les tâches Celery par responsabilité :
- retry    : retry asynchrone des étapes de workflow
- gates    : évaluation périodique des conditions WAITING
- polling  : surveillance des jobs sur les plateformes externes

Les helpers internes et dépendances sont ré-exportés ici pour que les patches
de tests utilisant @patch("executions.tasks.X") continuent de fonctionner.
"""
import structlog

from core.middleware import get_correlation_id
from core.services import AuditService

# Re-export logger at package level for test patchability (@patch("executions.tasks.logger"))
logger = structlog.get_logger("executions.tasks")

from executions.tasks.retry import retry_workflow_step  # noqa: E402
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
    poll_aap_job_status,
    poll_tower_job_status,
    poll_azure_devops_run_status,
    poll_github_actions_run_status,
    poll_terraform_cloud_run_status,
    MAX_POLLING_RETRIES,
    _mark_execution_polling_exhausted,
    _broadcast_execution_update,
    _update_execution_from_poll,
)

__all__ = [
    # Public tasks
    "retry_workflow_step",
    "evaluate_waiting_gates",
    "poll_platform_job_status",
    "poll_aap_job_status",
    "poll_tower_job_status",
    "poll_azure_devops_run_status",
    "poll_github_actions_run_status",
    "poll_terraform_cloud_run_status",
    # Constants
    "MAX_POLLING_RETRIES",
    # Story 42.1: Celery Beat task for scheduled executions
    "process_pending_scheduled_executions",
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
]
