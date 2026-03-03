"""
GateHandler — stub pour story 57.7

Handler pour les steps de type gate.
Implémentation réelle prévue en story 57.7.
"""


class GateHandler:
    """Handler pour les steps de type gate (implémenté en story 57.7)."""

    def execute(
        self,
        step_config: dict,
        resolved_params: dict,
        execution,
        step: dict,
        correlation_id: str,
    ) -> dict:
        raise NotImplementedError(
            "GateHandler.execute() not yet implemented — see story 57.7"
        )
