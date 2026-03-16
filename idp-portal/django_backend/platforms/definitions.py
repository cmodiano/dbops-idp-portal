"""
Story 82.2: PlatformDefinition — source de vérité pour chaque plateforme.
Story 83.4: Enrichissement avec runtime_config_schema et health_check_policy.

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
        action_config_schema: Schéma JSON (jsonschema draft-07) décrivant la structure
            attendue de action_config pour les actions de cette plateforme.
            `{}` signifie aucune contrainte (comportement actuel pour toutes les plateformes).
            Exposé via GET /api/v1/capabilities/integrations/ (Story 82.8, AC2).
        runtime_config_schema: Schéma JSON (jsonschema draft-07) décrivant les clés attendues
            dans integration.get_config(). Purement DESCRIPTIF — pas de validation automatique.
            Validation effective : runtime_kwargs_required / runtime_kwargs_optional.
            Exposé via GET /api/v1/capabilities/integrations/ (Story 83-5, 84-8).
        health_check_policy: Politique descriptive du health check (clés : timeout_seconds,
            health_check_endpoint, description). Purement DESCRIPTIF — documente le comportement
            de IHealthCheckable.health_check(). Comportement effectif : constantes *_DEFAULT_TIMEOUT
            et endpoint appelé par health_check(). Exposé via capabilities (Story 83-5, 84-8).
    """

    code: str
    display_name: str
    aliases: frozenset[str]
    icon: str
    connector_type: str
    action_platform_code: str
    """Valeur stockée dans la colonne Action.platform (contrainte CHECK Oracle).

    Représentation lisible BD héritée (ex: 'AAP', 'Azure DevOps') ≠ code canonique (ex: 'aap', 'azure_devops').
    Conversion inverse : platform_registry.get_by_action_platform_code(code).
    Ne pas utiliser directement comme code métier — utiliser PlatformDefinition.code.
    """
    supports_health_check: bool
    runtime_kwargs_required: tuple[str, ...] = field(default_factory=tuple)
    runtime_kwargs_optional: dict[str, object] = field(default_factory=dict)
    action_config_schema: dict = field(default_factory=dict)
    runtime_config_schema: dict = field(default_factory=dict)
    """Schéma JSON draft-07 décrivant les clés attendues dans integration.get_config()
    pour cette plateforme.

    Rôle : purement DESCRIPTIF. Expose la structure de config requise aux consommateurs
    (frontend, admin, documentation). N'est PAS validé automatiquement à l'exécution.

    Validation effective : assurée par runtime_kwargs_required / runtime_kwargs_optional
    dans build_platform_runtime_config() (adapters/runtime_config.py).

    Exposition : GET /api/v1/capabilities/integrations/ → platforms[*].runtime_config_schema
    """
    health_check_policy: dict = field(default_factory=dict)
    """Politique descriptive du health check pour cette plateforme.

    Rôle : purement DESCRIPTIF. Documente comment le health check est implémenté dans
    IHealthCheckable.health_check() de l'adapter correspondant. N'est PAS appliqué
    automatiquement à l'exécution.

    Comportement effectif : défini par les constantes *_DEFAULT_TIMEOUT dans l'adapter
    et l'endpoint appelé par health_check().

    Clés attendues : timeout_seconds (int), health_check_endpoint (str), description (str).

    Exposition : GET /api/v1/capabilities/integrations/ → platforms[*].health_check_policy
    """
