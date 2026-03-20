"""
Shim de rétrocompatibilité — Story 85.2.
Le module actif est executions.infra.outbox.
"""
from executions.infra.outbox import (  # noqa: F401
    APPROVAL_GRANTED,
    APPROVAL_REJECTED,
    STEP_BROADCAST,
    EXECUTION_NOTIFICATION,
    APPROVAL_NOTIFICATION,
    OutboxService,
)

__all__ = [
    "APPROVAL_GRANTED",
    "APPROVAL_REJECTED",
    "STEP_BROADCAST",
    "EXECUTION_NOTIFICATION",
    "APPROVAL_NOTIFICATION",
    "OutboxService",
]
