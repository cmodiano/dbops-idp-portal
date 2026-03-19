"""
Story 83.3: WorkflowStepDefinition — source de vérité pour chaque type de step workflow.

Ce module ne doit importer aucun module Django (models, settings, etc.) —
il doit être importable avant le chargement de l'ORM Django.
"""
from __future__ import annotations

from collections.abc import Callable
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
        variants_builder: Callable retournant les variants du step type (ex: gates).
            compare=False, hash=False : évite les erreurs de hashabilité sur les callables.
    """

    code: str
    label: str
    category: str
    constraints: dict = field(default_factory=dict)
    config_schema: dict = field(default_factory=dict)
    variants_builder: Callable[[], list[dict]] | None = field(
        default=None, compare=False, hash=False
    )


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
    constraints={
        'requires_integration': True,
        'required_fields': [{'field': 'action_id', 'message': 'Action requise pour un step de type Exécuter'}],
    },
))

workflow_step_registry.register(WorkflowStepDefinition(
    code='service_call',
    label='Service',
    category='integration',
    constraints={
        'requires_service_integration': True,
        'required_fields': [
            {'field': 'integration_type', 'message': "Type d'intégration requis"},
            {'field': 'operation', 'message': 'Opération requise'},
        ],
    },
))

def _build_gate_variants() -> list[dict]:
    """Retourne les variants du step gate depuis gate_registry.

    Import lazy : gate_registry requiert Django initialisé (ORM via strategies.py).
    Ce module doit rester importable avant l'ORM — l'import est donc différé à l'appel.
    """
    from executions.gates.registry import gate_registry  # noqa: PLC0415
    return [
        {
            'code': gate_type,
            'label': gdefn.display_name,
            'config_schema': gdefn.config_schema,
        }
        for gate_type in gate_registry.list_types()
        for gdefn in [gate_registry.get(gate_type)]
    ]


workflow_step_registry.register(WorkflowStepDefinition(
    code='gate',
    label='Attendre',
    category='control',
    constraints={
        'required_fields': [{'field': 'gate_type', 'message': 'Type de gate requis'}],
    },
    variants_builder=_build_gate_variants,
))

# ─────────────────────────────────────────────────────────────────────────────
# Types ajoutés par Story 84.1 — alignement capabilities ↔ runtime (AC4, R2)
# Ces types étaient exécutables mais non déclarés → absents de l'API capabilities
# ─────────────────────────────────────────────────────────────────────────────

workflow_step_registry.register(WorkflowStepDefinition(
    code='http_request',
    label='Requête HTTP',
    category='integration',
    constraints={
        'requires_allowed_host': True,
        'required_fields': [
            {'field': 'url', 'message': 'URL requise'},
            {'field': 'method', 'message': 'Méthode HTTP requise'},
        ],
    },
))

workflow_step_registry.register(WorkflowStepDefinition(
    code='evaluation',
    label='Évaluation',
    category='control',
    constraints={
        'required_fields': [{'field': 'policy_id', 'message': 'Politique de règles métier requise'}],
    },
))

# ─────────────────────────────────────────────────────────────────────────────
# Story 84.3 — schedule_execution : step de planification d'exécution différée
# ─────────────────────────────────────────────────────────────────────────────

workflow_step_registry.register(WorkflowStepDefinition(
    code='schedule_execution',
    label='Planifier',
    category='scheduling',
    constraints={
        'required_fields': [{'field': 'action_id', 'message': 'Action cible requise pour le step de planification'}],
    },
    config_schema={
        'input_mapping_fields': [
            {
                'key': 'schedule_name',
                'label': 'Nom de la cédule',
                'type': 'string',
                'required': False,
                'supports_template': True,
                'description': 'Nom descriptif pour la planification (supporte les références {{ steps.X.Y }})',
            },
            {
                'key': 'scheduled_date',
                'label': 'Date planifiée',
                'type': 'date',
                'required': False,
                'supports_template': True,
                'description': 'Date de planification (YYYY-MM-DD ou référence à un step précédent)',
            },
            {
                'key': 'scheduled_time',
                'label': 'Heure planifiée',
                'type': 'time',
                'required': False,
                'supports_template': True,
                'description': 'Heure de planification (HH:MM)',
            },
            {
                'key': 'duration_minutes',
                'label': 'Durée (minutes)',
                'type': 'integer',
                'required': False,
                'supports_template': True,
                'description': 'Durée estimée en minutes',
            },
        ],
        'schedule_sources': ['parameter', 'fixed_offset', 'input_mapping'],
    },
))
