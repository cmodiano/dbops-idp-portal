"""
DTOs (Data Transfer Objects) pour le module executions.
Story 54.9 (MAINT-BE-4): Réduction de la signature de create_execution().
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from catalog.models import Action
from idp_auth.models import User


@dataclass
class ExecutionRequest:
    """Encapsule tous les paramètres de création d'une exécution.

    Champs obligatoires (sans défaut) :
        user        — utilisateur déclenchant l'exécution
        action      — action du catalogue à exécuter
        environment — environnement cible (str de l'env config)

    Champs optionnels (défaut None) :
        parameters                     — dict de paramètres d'exécution
        parent_execution_id            — ID de l'exécution parent (remédiation)
        correlation_id                 — ID de corrélation pour le tracing
        source                         — 'api' | 'ui' | 'celery_beat' (Story 13.5)
        ip_address                     — IP client pour audit (Story 13.5)
        targets                        — liste de noms de cibles pour audit (Story 13.5)
        delegated_referenced_action_ids — IDs des actions déléguées (Story 4.11)
        validated_targets              — cibles validées depuis l'inventaire (Story 25.1)
    """
    user: User
    action: Action
    environment: str
    parameters: dict[str, Any] | None = None
    parent_execution_id: int | None = None
    correlation_id: str | None = None
    source: str | None = None
    ip_address: str | None = None
    targets: list[str] | None = None
    delegated_referenced_action_ids: list[int] | None = None
    validated_targets: list[dict[str, Any]] | None = None

    def __repr__(self) -> str:
        """Redact sensitive fields from repr to prevent data leaks in tracebacks."""
        return (
            f"ExecutionRequest("
            f"user={self.user!r}, "
            f"action={self.action!r}, "
            f"environment={self.environment!r}, "
            f"parameters=<redacted>, "
            f"parent_execution_id={self.parent_execution_id!r}, "
            f"correlation_id={self.correlation_id!r}, "
            f"source={self.source!r}, "
            f"ip_address=<redacted>, "
            f"targets={self.targets!r}, "
            f"delegated_referenced_action_ids={self.delegated_referenced_action_ids!r}, "
            f"validated_targets=<redacted>"
            f")"
        )
