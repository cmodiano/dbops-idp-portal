"""
ServiceCallHandler — implémentation réelle (story 57.4).

Handler pour les steps de type service_call (ADR-007 §4b).
Résout l'intégration, instancie le service via ServiceRegistry,
et appelle l'opération demandée avec les paramètres résolus.

Note : step_config et step reçoivent le même dict (design documenté en 57.3 LOW).
Utiliser step_config pour toutes les opérations.
"""
from __future__ import annotations

import structlog

from adapters.utils import build_auth_headers
from integrations.services import IntegrationService
from services import get_service_client

from executions.models import Execution

logger = structlog.get_logger(__name__)

# Opérations autorisées par service (liste positive = défense en profondeur).
# Les méthodes _* sont toujours bloquées même si absentes de ce dict.
_ALLOWED_OPERATIONS: dict[str, frozenset[str]] = {
    "servicenow": frozenset({
        "create_change", "update_change", "close_change",
        "get_change_status", "cancel_change",
    }),
    "vault": frozenset({
        "get_secret",
    }),
    "jira": frozenset({
        "create_issue", "update_issue", "get_issue",
    }),
}


class ServiceCallHandler:
    """Handler pour les steps de type service_call (ADR-007 §4b).

    Résout l'intégration, instancie le service via ServiceRegistry,
    et appelle l'opération demandée avec les paramètres résolus.
    """

    def execute(
        self,
        step_config: dict,
        resolved_params: dict,
        execution: Execution,
        step: dict,
        correlation_id: str | None,
    ) -> dict:
        """
        Exécute un appel synchrone à un service intégré.

        Args:
            step_config: Définition du step (integration_type, operation, integration_id, ...)
            resolved_params: Paramètres résolus via input_mapping (StepTemplateResolver)
            execution: Instance Execution en cours
            step: Même dict que step_config (alias pour _execute_handler_step)
            correlation_id: ID de corrélation pour les logs

        Returns:
            dict: Résultat brut de l'appel service (pour output_mapping)

        Raises:
            ValueError: Si integration_type inconnu, opération privée ou inexistante
            ServiceUnavailableError: Si le service est indisponible
        """
        from core.exceptions import ServiceUnavailableError

        integration_type = step_config.get("integration_type")
        operation = step_config.get("operation")

        if not integration_type:
            raise ValueError("service_call step requires 'integration_type'")
        if not operation:
            raise ValueError("service_call step requires 'operation'")
        if not isinstance(integration_type, str):
            raise ValueError(
                f"integration_type must be a string, got {type(integration_type).__name__}"
            )
        if not isinstance(operation, str):
            raise ValueError(
                f"operation must be a string, got {type(operation).__name__}"
            )

        # Sécurité : bloquer les méthodes privées
        if operation.startswith("_"):
            raise ValueError(
                f"Operation '{operation}' is not allowed: private methods cannot be called"
            )

        # Sécurité : vérification par liste positive (défense en profondeur, deny-by-default)
        _allowed = _ALLOWED_OPERATIONS.get(integration_type)
        if _allowed is None:
            raise ValueError(
                f"Unknown integration_type: '{integration_type}'. "
                f"Allowed types: {sorted(_ALLOWED_OPERATIONS)}"
            )
        if operation not in _allowed:
            raise ValueError(
                f"Operation '{operation}' is not in the allowed list for '{integration_type}'. "
                f"Allowed: {sorted(_allowed)}"
            )

        logger.info(
            "service_call_handler_start",
            integration_type=integration_type,
            operation=operation,
            execution_id=execution.id,
            correlation_id=correlation_id,
        )

        # Résolution de l'intégration
        integration_service = IntegrationService()
        integration_id = step_config.get("integration_id")
        integration = None

        if integration_id:
            integration = integration_service.get_by_id(integration_id)
            if not integration or integration.type != integration_type:
                logger.warning(
                    "service_call_integration_id_mismatch",
                    integration_id=integration_id,
                    expected_type=integration_type,
                )
                integration = None

        if not integration:
            # Fallback : première intégration active du bon type
            integration = integration_service.get_by_type(integration_type)

        if not integration:
            raise ServiceUnavailableError(
                code="SERVICE_INTEGRATION_MISSING",
                message=(
                    f"No integration of type '{integration_type}' found. "
                    "Configure an integration in Admin > Intégrations."
                ),
                details={"integration_type": integration_type, "execution_id": execution.id},
            )

        # Instanciation du service via ServiceRegistry
        auth_headers = build_auth_headers(integration, correlation_id)
        service = get_service_client(
            integration_type,
            base_url=integration.base_url,
            auth_headers=auth_headers,
        )

        # Validation de l'opération : exiger une méthode callable publique
        method = getattr(service, operation, None)
        if not callable(method):
            public_callables = [
                m for m in dir(service)
                if not m.startswith('_') and callable(getattr(service, m, None))
            ]
            raise ValueError(
                f"Operation '{operation}' does not exist or is not callable on service '{integration_type}'. "
                f"Available: {public_callables if public_callables else 'none'}"
            )

        # Appel de l'opération
        try:
            result = method(**resolved_params)
        except Exception:  # noqa: BLE001
            logger.error(
                "service_call_handler_error",
                integration_type=integration_type,
                operation=operation,
                execution_id=execution.id,
                correlation_id=correlation_id,
                exc_info=True,
            )
            raise

        # Normaliser en dict si le service retourne une valeur scalaire (backward compat)
        if not isinstance(result, dict):
            result = {"result": result}

        logger.info(
            "service_call_handler_success",
            integration_type=integration_type,
            operation=operation,
            execution_id=execution.id,
            correlation_id=correlation_id,
        )

        return result
