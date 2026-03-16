"""
Story 82.2: PlatformRegistry — registre singleton des définitions de plateformes.

Ce module ne doit importer aucun module Django (models, settings, etc.) —
il doit être importable avant le chargement de l'ORM Django.
"""
from __future__ import annotations

from platforms.definitions import PlatformDefinition


class PlatformRegistry:
    """Registre des définitions de plateformes.

    Les enregistrements ont lieu au niveau module (single-threaded, import time).
    L'enregistrement dynamique en contexte multi-thread n'est pas supporté.

    Usage:
        platform_registry.register(PlatformDefinition(...))
        defn = platform_registry.get("aap")           # raises KeyError si absent
        code = platform_registry.resolve_alias("terraform")  # → 'terraform_cloud'
        if platform_registry.is_registered("aap"):
            ...
    """

    def __init__(self) -> None:
        self._registry: dict[str, PlatformDefinition] = {}  # code → definition
        self._aliases: dict[str, str] = {}  # alias → canonical code
        self._action_platform_codes: dict[str, PlatformDefinition] = {}  # action_platform_code → definition

    def register(self, definition: PlatformDefinition) -> None:
        """Enregistre une PlatformDefinition.

        Les aliases sont indexés automatiquement.
        Un ré-enregistrement du même code remplace la définition existante.

        Args:
            definition: Instance PlatformDefinition à enregistrer.
        """
        self._registry[definition.code] = definition
        for alias in definition.aliases:
            self._aliases[alias] = definition.code
        # Index reverse action_platform_code → definition (Story 84-7)
        self._action_platform_codes[definition.action_platform_code] = definition

    def get(self, code: str) -> PlatformDefinition:
        """Retourne la PlatformDefinition pour un code canonique.

        Args:
            code: Code canonique de la plateforme.

        Returns:
            PlatformDefinition correspondante.

        Raises:
            KeyError: Si le code n'est pas enregistré (les aliases ne sont
                pas des codes canoniques — utiliser resolve_alias() d'abord).
        """
        return self._registry[code]

    def is_registered(self, code: str) -> bool:
        """Vérifie si un code canonique est enregistré.

        Note: retourne False pour les aliases — utiliser resolve_alias() d'abord
        si nécessaire.

        Args:
            code: Code canonique à vérifier.

        Returns:
            True si le code canonique est enregistré, False sinon.
        """
        return code in self._registry

    def resolve_alias(self, code: str) -> str:
        """Retourne le code canonique pour un code ou alias.

        Si 'code' est un alias connu, retourne le code canonique.
        Sinon retourne 'code' inchangé (comportement identique à dict.get(k, k)).

        Args:
            code: Code ou alias à résoudre.

        Returns:
            Code canonique si alias connu, sinon 'code' inchangé.
        """
        return self._aliases.get(code, code)

    def get_by_action_platform_code(self, code: str) -> PlatformDefinition:
        """Retourne la PlatformDefinition pour un code ActionPlatform (valeur BD).

        Permet la conversion reverse : 'AAP' → PlatformDefinition(code='aap', ...)

        Args:
            code: Valeur telle que stockée dans Action.platform (ex: 'AAP', 'Azure DevOps')

        Returns:
            PlatformDefinition correspondante.

        Raises:
            KeyError: Si le code n'est pas reconnu.
        """
        return self._action_platform_codes[code]

    def list_types(self) -> list[str]:
        """Retourne la liste des codes canoniques enregistrés.

        Returns:
            Liste des codes dans l'ordre d'insertion.
        """
        return list(self._registry.keys())


platform_registry = PlatformRegistry()

# ─────────────────────────────────────────────
# Enregistrement des 5 plateformes existantes
# Source: docs/reference/platform-canonical-codes.md
# ─────────────────────────────────────────────

platform_registry.register(PlatformDefinition(
    code="aap",
    display_name="Ansible Automation Platform",
    aliases=frozenset(),
    icon="aap",
    connector_type="aap",
    action_platform_code="AAP",
    supports_health_check=True,
    runtime_kwargs_required=(),
    runtime_kwargs_optional={"ca_bundle_path": None},
    action_config_schema={
        "type": "object",
        "properties": {
            "resource_type": {
                "type": "string",
                "enum": ["job_template", "workflow_job"],
                "title": "Type de ressource",
                "description": "Type de template AAP à appeler",
            },
            "template_id": {
                "type": "integer",
                "title": "ID du template",
                "description": "Identifiant du job template ou workflow job template dans AAP",
                "minimum": 1,
            },
        },
        "required": ["template_id"],
    },
))

platform_registry.register(PlatformDefinition(
    code="tower",
    display_name="Ansible Tower",
    aliases=frozenset(),
    icon="aap",
    connector_type="aap",
    action_platform_code="Tower",
    supports_health_check=True,
    runtime_kwargs_required=(),
    runtime_kwargs_optional={"ssl_verify": False, "ca_bundle_path": None},
    action_config_schema={
        "type": "object",
        "properties": {
            "resource_type": {
                "type": "string",
                "enum": ["job_template", "workflow_job"],
                "title": "Type de ressource",
                "description": "Type de template Tower à appeler",
            },
            "template_id": {
                "type": "integer",
                "title": "ID du template",
                "description": "Identifiant du job template ou workflow job template dans Tower",
                "minimum": 1,
            },
        },
        "required": ["template_id"],
    },
))

platform_registry.register(PlatformDefinition(
    code="azure_devops",
    display_name="Azure DevOps",
    # Alias conservé pour rétrocompatibilité avec d'anciennes valeurs 'azuredevops' (sans underscore)
    # potentiellement stockées en BD (integration.type). Consommé par tous les flux qui appellent
    # resolve_alias(integration.type) : trigger.py:113, integrations/tasks.py:81+256,
    # adapters/runtime_config.py:34, integrations/views.py:449, executions/views:395.
    aliases=frozenset({"azuredevops"}),
    icon="azuredevops",
    connector_type="azuredevops",
    action_platform_code="Azure DevOps",
    supports_health_check=True,
    runtime_kwargs_required=(),
    runtime_kwargs_optional={},
))

platform_registry.register(PlatformDefinition(
    code="github_actions",
    display_name="GitHub Actions",
    aliases=frozenset(),
    icon="github_actions",
    connector_type="github_actions",
    action_platform_code="GitHub Actions",
    supports_health_check=True,
    runtime_kwargs_required=("owner", "repo"),
    runtime_kwargs_optional={},
))

platform_registry.register(PlatformDefinition(
    code="terraform_cloud",
    display_name="Terraform Cloud",
    # Alias 'terraform' consommé par trigger.py / integrations/tasks.py pour des données BD historiques.
    # Note: _validate_action_config_schema utilise désormais get_by_action_platform_code('Terraform')
    # directement (Story 84-7) — cet alias n'est plus utilisé dans ce flux.
    aliases=frozenset({"terraform"}),
    icon="terraform",
    connector_type="terraform",
    action_platform_code="Terraform",
    supports_health_check=True,
    runtime_kwargs_required=("organization",),
    runtime_kwargs_optional={},
))
