"""
platforms — registre centralisé des définitions de plateformes.

Story 82.2: PlatformDefinition et PlatformRegistry constituent la source
de vérité pour health checks, validation, résolution runtime et métadonnées.
"""
from platforms.registry import platform_registry

__all__ = ["platform_registry"]
