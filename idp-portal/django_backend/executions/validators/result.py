"""Résultat structuré du pipeline de validation d'exécution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from catalog.models import Action


@dataclass
class ExecutionValidationResult:
    """Résultat retourné par ExecutionValidationPipeline.validate().

    Contient tous les champs validés nécessaires pour construire un ExecutionRequest.
    """
    action: Action
    action_id: int | str
    environment: str
    correlation_id: str | None
    requires_target: bool
    page_me: bool
    target_names: list[str] | None = None
    parameters: dict[str, Any] | None = None
    workflow_step_parameters: dict[str, Any] | None = None
    parent_execution_id: int | None = None
    validated_targets: list[dict[str, Any]] | None = None
    env_config: dict[str, Any] | None = None
    delegated_referenced_action_ids: list[int] | None = None
