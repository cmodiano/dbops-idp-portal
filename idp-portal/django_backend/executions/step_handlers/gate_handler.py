"""
GateHandler — stub pour story 57.7

Handler pour les steps de type gate.
Implémentation réelle prévue en story 57.7.
"""

from executions.models import Execution


class GateHandler:
    """Handler pour les steps de type gate (implémenté en story 57.7)."""

    def execute(
        self,
        step_config: dict,
        resolved_params: dict,
        execution: Execution,
        step: dict,
        correlation_id: str | None,
    ) -> dict:
        return {
            "status": "skipped",
            "outputs": {},
            "message": "Gate steps are no-op in this runtime (story 57.7)",
        }
