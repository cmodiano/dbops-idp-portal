"""
Story 82.3: ServiceDefinition — source de vérité pour chaque service.
Story 83.4: ServiceOperationDefinition + migration de ServiceDefinition.

Ce module ne doit importer aucun module Django (models, settings, etc.) —
il doit être importable avant le chargement de l'ORM Django.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ServiceOperationDefinition:
    """Définition d'une opération de service, avec ses schémas et hints UI.

    Attributes:
        code: Code canonique de l'opération (ex: 'create_change').
        label: Label d'affichage FR (ex: 'Créer un change').
        input_schema: Schéma JSON (draft-07) des paramètres d'entrée. {} = aucune contrainte.
        output_schema: Schéma JSON de la réponse. {} = aucune contrainte.
        ui_hints: Hints pour le rendu frontend (ex: {'widget': 'textarea'}). {} = par défaut.
    """

    code: str
    label: str
    # Note: frozen=True protège la référence mais pas le contenu du dict.
    # Ces champs doivent être traités comme immuables — ne pas les muter après construction.
    input_schema: dict = field(default_factory=dict)
    output_schema: dict = field(default_factory=dict)
    ui_hints: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ServiceDefinition:
    """Définition centralisée d'un service consommé par le portail.

    Attributes:
        code: Code canonique du service (ex: 'servicenow').
        display_name: Nom d'affichage (ex: 'ServiceNow').
        requires_integration: True si le service nécessite un record Integration en BD.
            False = credential_free (ex: notification).
        operation_defs: Définitions des opérations autorisées pour service_call.
            Chaque définition porte le code, le label FR et les schémas JSON.
            tuple() = service sans opérations service_call (health check uniquement).
        supports_health_check: True si le service implémente IHealthCheckable
            via le path service_registry.
    """

    code: str
    display_name: str
    requires_integration: bool
    operation_defs: tuple[ServiceOperationDefinition, ...] = field(default_factory=tuple)
    supports_health_check: bool = False

    @property
    def operations(self) -> frozenset[str]:
        """Codes des opérations autorisées — dérivé de operation_defs."""
        return frozenset(op.code for op in self.operation_defs)

    @property
    def supports_service_call(self) -> bool:
        """True si le service expose des opérations service_call — dérivé de operation_defs."""
        return bool(self.operation_defs)

    def get_operation_label(self, operation_code: str) -> str:
        """Retourne le label FR d'une opération, fallback = code."""
        for op in self.operation_defs:
            if op.code == operation_code:
                return op.label
        return operation_code


class ServiceDefinitionRegistry:
    """Registre singleton des définitions de services.

    Fournit une source de vérité unique pour l'allowlist d'opérations,
    la détection credential-free et le routing health check.
    """

    def __init__(self) -> None:
        self._registry: dict[str, ServiceDefinition] = {}

    def register(self, definition: ServiceDefinition) -> None:
        """Enregistre une définition de service.

        Args:
            definition: ServiceDefinition à enregistrer.
        """
        self._registry[definition.code] = definition

    def get(self, code: str) -> ServiceDefinition:
        """Retourne la définition d'un service.

        Args:
            code: Code canonique du service.

        Raises:
            KeyError: Si le code n'est pas enregistré.
        """
        return self._registry[code]

    def list_types(self) -> list[str]:
        """Retourne la liste des codes de services enregistrés (ordre d'insertion)."""
        return list(self._registry)

    def is_registered(self, code: str) -> bool:
        """True si le code est enregistré dans le registre."""
        return code in self._registry

    def get_allowed_operations(self, code: str) -> frozenset[str]:
        """Retourne les opérations autorisées pour un service.

        Args:
            code: Code canonique du service.

        Raises:
            ValueError: Si le code n'est pas enregistré (comportement identique
                à _ALLOWED_OPERATIONS manquant dans service_call_handler).
        """
        try:
            return self._registry[code].operations
        except KeyError:
            raise ValueError(
                f"Unknown integration_type: '{code}'. "
                f"Allowed types: {sorted(self._registry)}"
            )

    def is_credential_free(self, code: str) -> bool:
        """True si le service ne nécessite pas de record Integration en BD.

        Args:
            code: Code canonique du service.

        Returns:
            True si requires_integration=False. False si inconnu (défaut sûr).
        """
        try:
            return not self._registry[code].requires_integration
        except KeyError:
            return False  # type inconnu → non credential_free par défaut

    def get_operation_def(self, service_code: str, operation_code: str) -> ServiceOperationDefinition:
        """Retourne la définition d'une opération de service.

        Args:
            service_code: Code canonique du service.
            operation_code: Code canonique de l'opération.

        Raises:
            KeyError: Si le service ou l'opération n'est pas enregistré.
        """
        try:
            defn = self._registry[service_code]
        except KeyError:
            raise KeyError(
                f"Service '{service_code}' not found in registry. "
                f"Available: {sorted(self._registry)}"
            )
        for op in defn.operation_defs:
            if op.code == operation_code:
                return op
        raise KeyError(
            f"Operation '{operation_code}' not found in service '{service_code}'. "
            f"Available: {[op.code for op in defn.operation_defs]}"
        )


# Singleton module-level — même pattern que platforms/registry.py
service_definition_registry = ServiceDefinitionRegistry()
