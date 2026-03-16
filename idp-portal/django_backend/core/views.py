"""
Core views for health check and system status.
Story M.8 - Task 6: Enhanced health check for observability.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed
from datetime import datetime, timezone
from typing import Any, Callable

import requests
import structlog

from django.conf import settings
from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from core.middleware import get_correlation_id
from core.utils import ensure_utc_isoformat

logger = structlog.get_logger(__name__)

# Timeout for external service health checks (in seconds)
HEALTH_CHECK_TIMEOUT = getattr(settings, 'HEALTH_CHECK_TIMEOUT', 5)

# Story 86.8: Global deadline for concurrent external health checks (seconds)
HEALTH_CHECK_GLOBAL_TIMEOUT = getattr(settings, 'HEALTH_CHECK_GLOBAL_TIMEOUT', 10)


def _check_vault(correlation_id: str | None = None) -> str:
    """Check Vault reachability. Returns 'reachable' or 'unreachable'."""
    vault_addr = getattr(settings, 'VAULT_ADDR', None)
    try:
        response = requests.get(
            f"{vault_addr}/v1/sys/health",
            timeout=HEALTH_CHECK_TIMEOUT
        )
        if response.status_code == 200:
            return "reachable"
        raise ConnectionError(f"Vault returned {response.status_code}")
    except Exception as exc:  # noqa: BLE001 — graceful-degradation: health check reports degraded status on any Vault error
        logger.warning(
            "health_check_failed",
            service="vault",
            error=str(exc),
            error_type=type(exc).__name__,
            correlation_id=correlation_id,
            exc_info=True,
        )
        return "unreachable"


def _check_servicenow(correlation_id: str | None = None) -> str:
    """Check ServiceNow reachability. Returns 'reachable' or 'unreachable'."""
    servicenow_url = getattr(settings, 'SERVICENOW_INSTANCE_URL', None)
    try:
        response = requests.get(
            f"{servicenow_url}/api/now/table/sys_metadata",
            headers={"Accept": "application/json"},
            timeout=HEALTH_CHECK_TIMEOUT
        )
        if response.status_code in (200, 401):
            # 401 means ServiceNow is reachable but requires auth (expected)
            return "reachable"
        raise ConnectionError(f"ServiceNow returned {response.status_code}")
    except Exception as exc:  # noqa: BLE001 — graceful-degradation: health check reports degraded status on any ServiceNow error
        logger.warning(
            "health_check_failed",
            service="servicenow",
            error=str(exc),
            error_type=type(exc).__name__,
            correlation_id=correlation_id,
            exc_info=True,
        )
        return "unreachable"


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request: Any) -> Response:
    """
    Health check endpoint for monitoring and load balancer.

    Checks:
    - Oracle database connection
    - Vault service reachability (optional, concurrent)
    - ServiceNow service reachability (optional, concurrent)

    Returns:
        Response format:
        {
            "data": {
                "status": "healthy" | "degraded",
                "timestamp": "2026-02-05T14:30:05.123Z",
                "oracle": "connected" | "disconnected",
                "db_pool_status": {
                    "conn_max_age": 600,
                    "conn_health_checks": true,
                    "connection_usable": true
                },
                "vault": "reachable" | "unreachable" | "timeout",
                "servicenow": "reachable" | "unreachable" | "timeout"
            }
        }
        Status code: 200 if healthy, 503 if degraded
    """
    correlation_id = get_correlation_id()
    health_data: dict[str, Any] = {
        "status": "healthy",
        "timestamp": ensure_utc_isoformat(datetime.now(timezone.utc)),
    }

    # Test database connection + pool status (Story 32.1)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM DUAL")
            health_data["oracle"] = "connected"

        # Story 32.1 Task 4: DB pool status info
        db_settings = settings.DATABASES.get('default', {})
        health_data["db_pool_status"] = {
            "conn_max_age": db_settings.get('CONN_MAX_AGE', 0),
            "conn_health_checks": db_settings.get('CONN_HEALTH_CHECKS', False),
            "connection_usable": connection.is_usable(),
        }
    except Exception as e:  # noqa: BLE001 — graceful-degradation: health check reports degraded status on any DB error
        # Story 17.6: Justified broad catch - DB connection can raise various exceptions
        logger.error(
            "health_check_failed",
            service="oracle",
            error=str(e),
            error_type=type(e).__name__,
            correlation_id=correlation_id,
            exc_info=True,
        )
        health_data["oracle"] = "disconnected"
        health_data["status"] = "degraded"
        health_data["db_pool_status"] = {
            "conn_max_age": settings.DATABASES.get('default', {}).get('CONN_MAX_AGE', 0),
            "conn_health_checks": settings.DATABASES.get('default', {}).get('CONN_HEALTH_CHECKS', False),
            "connection_usable": False,
        }

    # Story 86.8: Build concurrent external checks (Vault + ServiceNow)
    vault_addr = getattr(settings, 'VAULT_ADDR', None)
    servicenow_url = getattr(settings, 'SERVICENOW_INSTANCE_URL', None)

    checks: dict[str, Callable[[], str]] = {}

    if vault_addr and vault_addr != 'http://localhost:8200':
        checks["vault"] = lambda: _check_vault(correlation_id)
    else:
        # Vault not configured - mark as reachable to not fail health check
        health_data["vault"] = "reachable"

    if servicenow_url and 'instance.service-now.com' not in servicenow_url:
        checks["servicenow"] = lambda: _check_servicenow(correlation_id)
    else:
        # ServiceNow not configured - mark as reachable to not fail health check
        health_data["servicenow"] = "reachable"

    # Execute external checks concurrently with global deadline
    if checks:
        future_to_name: dict[Future[str], str] = {}
        executor = ThreadPoolExecutor(max_workers=len(checks))
        try:
            for name, fn in checks.items():
                future_to_name[executor.submit(fn)] = name
            try:
                for future in as_completed(future_to_name, timeout=HEALTH_CHECK_GLOBAL_TIMEOUT):
                    name = future_to_name[future]
                    try:
                        health_data[name] = future.result()
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "health_check_failed",
                            service=name,
                            error=str(exc),
                            error_type=type(exc).__name__,
                            correlation_id=correlation_id,
                            exc_info=True,
                        )
                        health_data[name] = "unreachable"
                        health_data["status"] = "degraded"
            except FuturesTimeoutError:
                # Deadline global dépassé — marquer les checks non terminés comme "timeout"
                # shutdown(wait=False) ci-dessous permet de répondre sans attendre les threads bloqués
                for future, name in future_to_name.items():
                    if name not in health_data:
                        logger.warning(
                            "health_check_timeout",
                            service=name,
                            deadline_seconds=HEALTH_CHECK_GLOBAL_TIMEOUT,
                            correlation_id=correlation_id,
                        )
                        health_data[name] = "timeout"
                        health_data["status"] = "degraded"
        finally:
            # wait=False : ne pas bloquer sur les threads encore en cours après le deadline global
            executor.shutdown(wait=False)

    # Mark degraded if any external service is unreachable
    for key in ("vault", "servicenow"):
        if health_data.get(key) == "unreachable":
            health_data["status"] = "degraded"

    # Format response with envelope
    response_data = {"data": health_data}

    http_status = (
        status.HTTP_200_OK
        if health_data["status"] == "healthy"
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )

    return Response(response_data, status=http_status)
