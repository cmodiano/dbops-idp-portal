"""
Core views for health check and system status.
Story M.8 - Task 6: Enhanced health check for observability.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

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


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request: Any) -> Response:
    """
    Health check endpoint for monitoring and load balancer.

    Checks:
    - Oracle database connection
    - Vault service reachability (optional)
    - ServiceNow service reachability (optional)

    Returns:
        Response format:
        {
            "data": {
                "status": "healthy" | "degraded",
                "timestamp": "2026-02-05T14:30:05.123Z",
                "oracle": "connected" | "disconnected",
                "vault": "reachable" | "unreachable",
                "servicenow": "reachable" | "unreachable"
            }
        }
        Status code: 200 if healthy, 503 if degraded
    """
    correlation_id = get_correlation_id()
    health_data = {
        "status": "healthy",
        "timestamp": ensure_utc_isoformat(datetime.now(timezone.utc)),
    }

    # Test database connection
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM DUAL")
            health_data["oracle"] = "connected"
    except Exception as e:
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

    # Test Vault connection (optional - only if configured)
    vault_addr = getattr(settings, 'VAULT_ADDR', None)
    if vault_addr and vault_addr != 'http://localhost:8200':
        try:
            response = requests.get(
                f"{vault_addr}/v1/sys/health",
                timeout=HEALTH_CHECK_TIMEOUT
            )
            if response.status_code == 200:
                health_data["vault"] = "reachable"
            else:
                raise ConnectionError(f"Vault returned {response.status_code}")
        except Exception as e:
            # Story 17.6: Justified broad catch - Health check must handle any connectivity issue
            logger.warning(
                "health_check_failed",
                service="vault",
                error=str(e),
                error_type=type(e).__name__,
                correlation_id=correlation_id,
                exc_info=True,
            )
            health_data["vault"] = "unreachable"
            health_data["status"] = "degraded"
    else:
        # Vault not configured - mark as reachable to not fail health check
        health_data["vault"] = "reachable"

    # Test ServiceNow connection (optional - only if configured)
    servicenow_url = getattr(settings, 'SERVICENOW_INSTANCE_URL', None)
    if servicenow_url and 'instance.service-now.com' not in servicenow_url:
        try:
            response = requests.get(
                f"{servicenow_url}/api/now/table/sys_metadata",
                headers={"Accept": "application/json"},
                timeout=HEALTH_CHECK_TIMEOUT
            )
            if response.status_code in (200, 401):
                # 401 means ServiceNow is reachable but requires auth (expected)
                health_data["servicenow"] = "reachable"
            else:
                raise ConnectionError(f"ServiceNow returned {response.status_code}")
        except Exception as e:
            # Story 17.6: Justified broad catch - Health check must handle any connectivity issue
            logger.warning(
                "health_check_failed",
                service="servicenow",
                error=str(e),
                error_type=type(e).__name__,
                correlation_id=correlation_id,
                exc_info=True,
            )
            health_data["servicenow"] = "unreachable"
            health_data["status"] = "degraded"
    else:
        # ServiceNow not configured - mark as reachable to not fail health check
        health_data["servicenow"] = "reachable"

    # Format response with envelope
    response_data = {"data": health_data}

    http_status = (
        status.HTTP_200_OK
        if health_data["status"] == "healthy"
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )

    return Response(response_data, status=http_status)
