"""
ServiceCallHandler — stub pour story 57.4

Handler pour les steps de type service_call.
Implémentation réelle prévue en story 57.4.
"""


class ServiceCallHandler:
    """Handler pour les steps de type service_call (implémenté en story 57.4)."""

    def execute(
        self,
        step_config: dict,
        resolved_params: dict,
        execution,
        step: dict,
        correlation_id: str,
    ) -> dict:
        raise NotImplementedError(
            "ServiceCallHandler.execute() not yet implemented — see story 57.4"
        )
