"""
executions/exceptions.py — Exceptions spécifiques au module executions.
"""


class WorkflowLegacyDisabledError(RuntimeError):
    """Raised when legacy workflow runtime is invoked but disabled via feature flag.

    All workflows must have step_id fields to use the queue-based dispatch
    (RUNNABLE_STEPS). Enable WORKFLOW_LEGACY_RUNTIME_ENABLED for emergency rollback.
    """

    def __init__(self) -> None:
        super().__init__(
            "Le runtime legacy est désactivé. Tous les workflows doivent avoir "
            "des step_id pour utiliser le dispatch queue-based."
        )
