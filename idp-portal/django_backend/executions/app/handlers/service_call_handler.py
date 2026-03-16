"""
ServiceCallHandler — Story 85.4 — Relocalisation vers app/handlers/.

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
from services.definitions import service_definition_registry

from executions.models import Execution

logger = structlog.get_logger(__name__)
# Opérations autorisées et détection credential-free dérivées de service_definition_registry.
# Story 82.3: _ALLOWED_OPERATIONS et _CREDENTIAL_FREE_TYPES supprimés.
# Source de vérité : services/definitions.py (service_definition_registry)
# Story 82.9: serviceCallConstants.ts supprimé — le frontend lit désormais les opérations via l'API /capabilities/.


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
        # Story 82.3: délègue à service_definition_registry (source de vérité).
        try:
            _allowed = service_definition_registry.get_allowed_operations(integration_type)
        except ValueError:
            raise  # propager tel quel — message déjà formaté dans get_allowed_operations()
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
        # Story 82.3: credential-free dérivé de service_definition_registry.
        if service_definition_registry.is_credential_free(integration_type):
            # Types sans record Integration en base (ex: notification) — instanciation directe
            service = get_service_client(integration_type)
        else:
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
            if integration_type == "notification" and operation == "notify_execution_event":
                # Injection des objets contextuels (non mappables depuis input_mapping).
                # SÉCURITÉ : filtrer resolved_params pour empêcher le surécrasement des clés
                # contextuelles (execution, action, correlation_id) via input_mapping utilisateur.
                _protected_keys = frozenset({"execution", "action", "correlation_id"})
                _user_params = {k: v for k, v in resolved_params.items() if k not in _protected_keys}
                result = method(
                    execution=execution,
                    action=execution.action,
                    correlation_id=correlation_id,
                    **_user_params,
                )
            else:
                # Note: send_email et send_teams capturent toutes les exceptions en interne
                # (best-effort). En cas d'échec, la méthode retourne None et le step sera
                # marqué comme réussi. Les erreurs sont visibles uniquement dans les logs.
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
