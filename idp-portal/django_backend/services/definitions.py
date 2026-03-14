"""
Story 82.3: ServiceDefinition — source de vérité pour chaque service.

Ce module ne doit importer aucun module Django (models, settings, etc.) —
il doit être importable avant le chargement de l'ORM Django.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType


@dataclass(frozen=True)
class ServiceDefinition:
    """Définition centralisée d'un service consommé par le portail.

    Attributes:
        code: Code canonique du service (ex: 'servicenow').
        display_name: Nom d'affichage (ex: 'ServiceNow').
        requires_integration: True si le service nécessite un record Integration en BD.
            False = credential_free (ex: notification).
        operations: Opérations autorisées pour service_call (liste positive).
            frozenset() = service sans opérations service_call (health check uniquement).
        supports_health_check: True si le service implémente IHealthCheckable
            via le path service_registry.
        operation_labels: Labels FR des opérations (code → label). Utilisé par l'API
            capabilities pour exposer des labels localisés. Story 82.7.
            Immuable via MappingProxyType (cohérence avec operations → frozenset).
    """

    code: str
    display_name: str
    requires_integration: bool
    operations: frozenset[str]
    supports_health_check: bool
    operation_labels: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.operations, frozenset):  # pragma: no branch
            # Enforce immutability: convert set/list/tuple to frozenset
            object.__setattr__(self, "operations", frozenset(self.operations))  # type: ignore[unreachable]
        # Enforce immutability of operation_labels (dict is mutable; MappingProxyType is not).
        if not isinstance(self.operation_labels, MappingProxyType):
            object.__setattr__(self, "operation_labels", MappingProxyType(self.operation_labels))

    def get_operation_label(self, operation_code: str) -> str:
        """Retourne le label FR d'une opération, fallback = code."""
        return self.operation_labels.get(operation_code, operation_code)


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


# Singleton module-level — même pattern que platforms/registry.py
service_definition_registry = ServiceDefinitionRegistry()
