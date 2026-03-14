"""
Story 82.2: PlatformDefinition — source de vérité pour chaque plateforme.

Ce module ne doit importer aucun module Django (models, settings, etc.) —
il doit être importable avant le chargement de l'ORM Django.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PlatformDefinition:
    """Définition centralisée d'une plateforme d'exécution.

    Attributes:
        code: Code canonique de la plateforme (ex: 'azure_devops').
        display_name: Nom d'affichage (ex: 'Azure DevOps').
        aliases: Codes alternatifs acceptés (ex: frozenset({'azuredevops'})).
        icon: Identifiant icône frontend (ex: 'azuredevops').
        connector_type: Type connecteur ServiceNow/ITSM (ex: 'azuredevops').
        action_platform_code: Code BD ActionPlatform (ex: 'Azure DevOps').
        supports_health_check: True si la plateforme implémente IHealthCheckable.
        runtime_kwargs_required: Clés obligatoires dans integration.get_config().
            Une ValueError est levée si l'une d'elles est absente ou vide.
        runtime_kwargs_optional: Clés optionnelles avec leur valeur par défaut.
            Si la clé est absente de get_config(), la valeur par défaut est utilisée.
    """

    code: str
    display_name: str
    aliases: frozenset[str]
    icon: str
    connector_type: str
    action_platform_code: str
    supports_health_check: bool
    runtime_kwargs_required: tuple[str, ...] = field(default_factory=tuple)
    runtime_kwargs_optional: dict[str, object] = field(default_factory=dict)
