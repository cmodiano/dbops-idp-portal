"""
HttpRequestHandler — stub pour story 57.5

Handler pour les steps de type http_request.
Implémentation réelle prévue en story 57.5.
"""

from executions.models import Execution


class HttpRequestHandler:
    """Handler pour les steps de type http_request (implémenté en story 57.5)."""

    def execute(
        self,
        step_config: dict,
        resolved_params: dict,
        execution: Execution,
        step: dict,
        correlation_id: str | None,
    ) -> dict:
        raise NotImplementedError(
            "HttpRequestHandler.execute() not yet implemented — see story 57.5"
        )
