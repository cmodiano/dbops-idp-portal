"""Notification service for DBA alerts (Story 9.3, AC3).

Handles:
- Notifying DBA when auto-remediation fails
- In-app notifications (future: email integration)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from app.models.execution import ExecutionResponse

logger = structlog.get_logger()


async def notify_dba_remediation_failed(
    parent_exec: "ExecutionResponse",
    child_exec: "ExecutionResponse",
) -> None:
    """Notify DBA when auto-remediation fails (Story 9.3, AC3).

    In MVP: logs the notification event (email integration to be added post-MVP).
    The DBA will see the failure via:
    - WebSocket event pushed to parent execution timeline (handled in execution_service.py:1020-1028)
    - StructuredErrorCard with manual remediation suggestions (always shown for FAILED executions)
    - Dashboard executions list showing failed remediation

    IMPORTANT: The WebSocket notification is sent from ExecutionService._handle_child_execution_completed(),
    not from this function. This ensures the notification reaches the frontend even if ws_manager is None.

    Args:
        parent_exec: The original failed execution
        child_exec: The failed remediation execution
    """
    env_str = (
        parent_exec.environment.value
        if hasattr(parent_exec.environment, "value")
        else str(parent_exec.environment)
    )

    logger.warning(
        "dba_notification_sent",
        reason="auto_remediation_failed",
        parent_execution_id=parent_exec.id,
        parent_action_name=parent_exec.action_name,
        child_execution_id=child_exec.id,
        child_action_name=child_exec.action_name,
        environment=env_str,
    )

    # Future: Send email to DBA on-call for the environment
    # Future: Create in-app notification badge in top nav
    # For now, the WebSocket event + StructuredErrorCard provides visibility
