"""
GitHub Actions webhook endpoint for real-time workflow run monitoring.

Story 27.4 (AC4, AC5): Receive workflow_run events from GitHub, validate
HMAC SHA-256 signature, update execution status, and broadcast via WebSocket.
"""
from __future__ import annotations

import hashlib
import hmac
import json

import structlog
from django.conf import settings
from django.db import DatabaseError, OperationalError
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.request import Request
from rest_framework.response import Response

from adapters.github_actions_adapter import (
    GITHUB_ACTIONS_TERMINAL_CONCLUSIONS,
    _map_github_actions_status,
)
from core.middleware import get_correlation_id
from executions.models import ExecutionStatus, ExecutionStep

logger = structlog.get_logger(__name__)

# Mapping GitHub webhook action → whether we should process status updates
WEBHOOK_PROCESSABLE_ACTIONS = {"requested", "in_progress", "completed"}


def _verify_github_signature(payload_body: bytes, signature_header: str, secret: str) -> bool:
    """Verify GitHub webhook HMAC SHA-256 signature.

    Args:
        payload_body: Raw request body bytes.
        signature_header: Value of X-Hub-Signature-256 header.
        secret: Webhook secret shared with GitHub.

    Returns:
        True if signature is valid, False otherwise.
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected_signature = (
        "sha256="
        + hmac.new(
            secret.encode("utf-8"),
            payload_body,
            hashlib.sha256,
        ).hexdigest()
    )

    return hmac.compare_digest(expected_signature, signature_header)


@api_view(["POST"])
@authentication_classes([])  # No auth — secured by HMAC signature
@permission_classes([])
def github_webhook_workflow_run(request: Request) -> Response:
    """Handle GitHub Actions workflow_run webhook events.

    Endpoint: POST /api/v1/webhooks/github/workflow_run

    Validates HMAC SHA-256 signature, extracts workflow_run status,
    updates the matching execution, and broadcasts via WebSocket.

    Returns:
        200 OK on success, 400/401/404 on error.
    """
    correlation_id = get_correlation_id()

    # Step 1: Validate HMAC signature
    webhook_secret = getattr(settings, "GITHUB_WEBHOOK_SECRET", "")
    if not webhook_secret:
        logger.error(
            "github_webhook_no_secret_configured",
            correlation_id=correlation_id,
        )
        return Response(
            {"error": "Webhook secret not configured"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    signature_header = request.META.get("HTTP_X_HUB_SIGNATURE_256", "")
    raw_body = request.body

    if not _verify_github_signature(raw_body, signature_header, webhook_secret):
        logger.warning(
            "github_webhook_signature_invalid",
            correlation_id=correlation_id,
        )
        return Response(
            {"error": "Invalid signature"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    # Step 2: Parse payload
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        logger.warning(
            "github_webhook_invalid_json",
            correlation_id=correlation_id,
        )
        return Response(
            {"error": "Invalid JSON payload"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Step 3: Validate event structure
    action = payload.get("action", "")
    workflow_run = payload.get("workflow_run")

    if not workflow_run:
        logger.warning(
            "github_webhook_missing_workflow_run",
            action=action,
            correlation_id=correlation_id,
        )
        return Response(
            {"error": "Missing workflow_run in payload"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if action not in WEBHOOK_PROCESSABLE_ACTIONS:
        logger.info(
            "github_webhook_action_ignored",
            action=action,
            correlation_id=correlation_id,
        )
        return Response({"status": "ignored"}, status=status.HTTP_200_OK)

    # Step 4: Extract run information
    run_id = str(workflow_run.get("id", ""))
    gh_status = workflow_run.get("status", "queued")
    gh_conclusion = workflow_run.get("conclusion")

    if not run_id:
        logger.warning(
            "github_webhook_missing_run_id",
            correlation_id=correlation_id,
        )
        return Response(
            {"error": "Missing run ID"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    idp_status = _map_github_actions_status(gh_status, gh_conclusion)
    is_terminal = (
        gh_status == "completed"
        and gh_conclusion in GITHUB_ACTIONS_TERMINAL_CONCLUSIONS
    )

    logger.info(
        "github_webhook_received",
        action=action,
        run_id=run_id,
        github_status=gh_status,
        github_conclusion=gh_conclusion,
        idp_status=idp_status,
        is_terminal=is_terminal,
        correlation_id=correlation_id,
    )

    # Step 5: Find matching execution via ExecutionStep.platform_job_id
    try:
        step = ExecutionStep.objects.filter(
            platform_job_id=run_id,
        ).select_related("execution").first()
        execution = step.execution if step else None
    except (DatabaseError, OperationalError) as e:
        logger.error(
            "github_webhook_db_error",
            run_id=run_id,
            error=str(e),
            error_type=type(e).__name__,
            correlation_id=correlation_id,
        )
        return Response(
            {"error": "Database error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if not execution:
        logger.info(
            "github_webhook_execution_not_found",
            run_id=run_id,
            correlation_id=correlation_id,
        )
        return Response({"status": "no_matching_execution"}, status=status.HTTP_200_OK)

    # Step 6: Update execution status if not already terminal
    terminal_statuses = {
        ExecutionStatus.COMPLETED,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
    }
    if execution.status not in terminal_statuses and idp_status != execution.status:
        try:
            from core.di import get_execution_service  # noqa: PLC0415
            svc = get_execution_service()
            svc.update_status(execution.id, idp_status, str(execution.user_id))
        except ValueError as ve:
            logger.warning(
                "github_webhook_status_transition_invalid",
                execution_id=execution.id,
                current=execution.status,
                target=idp_status,
                error=str(ve),
                correlation_id=correlation_id,
            )

    # Step 7: Broadcast via WebSocket
    _broadcast_webhook_update(
        execution_id=execution.id,
        idp_status=idp_status,
        gh_status=gh_status,
        gh_conclusion=gh_conclusion,
        is_terminal=is_terminal,
        correlation_id=correlation_id,
    )

    logger.info(
        "github_webhook_processed",
        execution_id=execution.id,
        run_id=run_id,
        idp_status=idp_status,
        correlation_id=correlation_id,
    )

    return Response({"status": "ok"}, status=status.HTTP_200_OK)


def _broadcast_webhook_update(
    execution_id: int,
    idp_status: str,
    gh_status: str,
    gh_conclusion: str | None,
    is_terminal: bool,
    correlation_id: str | None = None,
) -> None:
    """Broadcast webhook status update to execution's WebSocket group."""
    try:
        from channels.layers import get_channel_layer  # type: ignore[import-untyped]
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()
        if channel_layer is None:
            logger.warning(
                "github_webhook_broadcast_no_channel_layer",
                execution_id=execution_id,
                correlation_id=correlation_id,
            )
            return

        group_name = f"execution_{execution_id}"

        # Send status update
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "status_update",
                "data": {
                    "execution_id": execution_id,
                    "status": idp_status,
                    "github_actions_status": gh_status,
                    "github_actions_conclusion": gh_conclusion,
                },
            },
        )

        # Send terminal event
        if is_terminal:
            event_type = (
                "execution_complete" if idp_status == "COMPLETED"
                else "execution_failed"
            )
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": event_type,
                    "data": {
                        "execution_id": execution_id,
                        "status": idp_status,
                        "github_actions_conclusion": gh_conclusion,
                    },
                },
            )

        logger.info(
            "github_webhook_broadcast_success",
            execution_id=execution_id,
            correlation_id=correlation_id,
        )
    except ImportError:
        logger.error(
            "github_webhook_broadcast_channels_not_installed",
            execution_id=execution_id,
            correlation_id=correlation_id,
        )
    except Exception as e:  # noqa: BLE001 — broad catch justified: webhook must return 200 even if broadcast fails (resilience)
        logger.error(
            "github_webhook_broadcast_error",
            execution_id=execution_id,
            error=str(e),
            error_type=type(e).__name__,
            correlation_id=correlation_id,
        )
