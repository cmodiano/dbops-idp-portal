"""Construction de la réponse HTTP après création d'exécution."""
from __future__ import annotations

from typing import Any

from rest_framework.response import Response

from core.utils import ensure_utc_isoformat
from executions.models import ExecutionStatus


class ExecutionResponseBuilder:
    """Construit la réponse HTTP après création de l'exécution."""

    @staticmethod
    def build(execution: Any, action: Any) -> Response:
        """
        Build the HTTP response for a created execution.

        Returns:
            DRF Response with status 201 containing execution data.
        """
        response_data = {
            "execution_id": execution.id,
            "status": execution.status,
            "created_at": ensure_utc_isoformat(execution.created_at),
        }

        if execution.status == ExecutionStatus.INTEGRATION_ERROR:
            response_data["error_message"] = execution.error_message

        return Response({"data": response_data}, status=201)
