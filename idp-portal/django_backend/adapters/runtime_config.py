"""
Story 82.2: build_platform_runtime_config — extraction centralisée des kwargs runtime.

Remplace les blocs platform_kwargs dupliqués dans :
- integrations/tasks.py:_resolve_and_check_adapter
- executions/tasks/trigger.py
- executions/views/execution_views.py (2 occurrences)
"""
from __future__ import annotations

from platforms.registry import platform_registry


def build_platform_runtime_config(integration) -> dict:
    """Extrait les kwargs runtime plateforme depuis integration.get_config().

    Résout d'abord l'alias éventuel (ex: 'azuredevops' → 'azure_devops'),
    puis charge la PlatformDefinition correspondante. Si le type n'est pas
    enregistré dans le PlatformRegistry (service, vault, etc.), retourne {}.

    Args:
        integration: Instance Integration avec attributs .type et .get_config().
            get_config() peut retourner None ou {} si aucune config.

    Returns:
        dict des kwargs à passer à get_platform_adapter(**platform_kwargs).
        Clés requises incluses si présentes dans get_config().
        Clés optionnelles incluses avec leur valeur par défaut si absentes.
        {} si le type n'est pas géré par PlatformRegistry.

    Raises:
        ValueError: Si un kwargs requis est absent ou vide dans get_config().
    """
    resolved_type = platform_registry.resolve_alias(integration.type)
    if not platform_registry.is_registered(resolved_type):
        return {}  # service, vault, inventory, etc.

    definition = platform_registry.get(resolved_type)
    config = integration.get_config() if hasattr(integration, "get_config") else {}
    config = config or {}

    kwargs: dict = {}

    # Kwargs requis — ValueError si absent ou vide
    for key in definition.runtime_kwargs_required:
        value = config.get(key)
        if not value:
            raise ValueError(
                f"{resolved_type} platform requires '{key}' parameter in integration config"
            )
        kwargs[key] = value

    # Kwargs optionnels — valeur par défaut si absent de la config
    for key, default in definition.runtime_kwargs_optional.items():
        if key in config:
            kwargs[key] = config[key]
        else:
            kwargs[key] = default

    return kwargs
