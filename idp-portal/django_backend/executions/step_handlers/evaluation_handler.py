"""
EvaluationHandler — stub pour story 57.6

Handler pour les steps de type evaluation.
Implémentation réelle prévue en story 57.6.
"""

from executions.models import Execution


class EvaluationHandler:
    """Handler pour les steps de type evaluation (implémenté en story 57.6)."""

    def execute(
        self,
        step_config: dict,
        resolved_params: dict,
        execution: Execution,
        step: dict,
        correlation_id: str | None,
    ) -> dict:
        raise NotImplementedError(
            "EvaluationHandler.execute() not yet implemented — see story 57.6"
        )
