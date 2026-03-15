"""
Story 83.3: WorkflowStepDefinition — source de vérité pour chaque type de step workflow.

Ce module ne doit importer aucun module Django (models, settings, etc.) —
il doit être importable avant le chargement de l'ORM Django.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class WorkflowStepDefinition:
    """Définition centralisée d'un type de step workflow.

    Attributes:
        code: Code canonique du step type (ex: 'platform', 'service_call', 'gate').
        label: Label d'affichage FR (ex: 'Exécuter').
        category: Catégorie sémantique (ex: 'execution', 'integration', 'control').
        constraints: Contraintes métier (ex: {'requires_integration': True}).
        config_schema: Schéma JSON de configuration du step (vide {} à ce stade).
    """

    code: str
    label: str
    category: str
    constraints: dict = field(default_factory=dict)
    config_schema: dict = field(default_factory=dict)


class WorkflowStepDefinitionRegistry:
    """Registre singleton des définitions de types de steps workflow."""

    def __init__(self) -> None:
        self._registry: dict[str, WorkflowStepDefinition] = {}

    def register(self, definition: WorkflowStepDefinition) -> None:
        """Enregistre une WorkflowStepDefinition.

        Un ré-enregistrement du même code remplace la définition existante.
        """
        self._registry[definition.code] = definition

    def get(self, code: str) -> WorkflowStepDefinition:
        """Retourne la définition d'un step type par code.

        Raises:
            KeyError: Si code n'est pas enregistré.
        """
        return self._registry[code]

    def list_types(self) -> list[str]:
        """Retourne les codes dans l'ordre d'insertion."""
        return list(self._registry)

    def is_registered(self, code: str) -> bool:
        """True si code est enregistré."""
        return code in self._registry


workflow_step_registry = WorkflowStepDefinitionRegistry()

# ─────────────────────────────────────────────────────────────────────────────
# Enregistrement des 3 types de steps — anciennement dans _STEP_TYPES_STATIC
# Source: extensibility-remaining-work-state-of-the-art.md § A.4
# ─────────────────────────────────────────────────────────────────────────────

workflow_step_registry.register(WorkflowStepDefinition(
    code='platform',
    label='Exécuter',
    category='execution',
    constraints={'requires_integration': True},
))

workflow_step_registry.register(WorkflowStepDefinition(
    code='service_call',
    label='Service',
    category='integration',
    constraints={'requires_service_integration': True},
))

workflow_step_registry.register(WorkflowStepDefinition(
    code='gate',
    label='Attendre',
    category='control',
    constraints={},
))
