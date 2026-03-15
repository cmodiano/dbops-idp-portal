"""
Story 82.5: GateDefinition — source de vérité pour chaque type de gate.
Story 83.2: GateEvaluationContext + GateEvaluationStrategy Protocol.

Ce module ne doit importer aucun module Django (models, settings, etc.) —
il doit être importable avant le chargement de l'ORM Django.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class GateEvaluationContext:
    """Contexte passé à une GateEvaluationStrategy lors de l'évaluation.

    Attributes:
        step: Instance ExecutionStep en cours d'évaluation.
        condition: dict gate_condition (avec 'type' et paramètres éventuels).
        inventory_service: Service d'inventaire injecté (typé Any pour éviter
            l'import circulaire avec inventory.services).
        requires_maintenance_window: True si l'environnement cible requiert
            une fenêtre de maintenance.
    """

    step: Any
    condition: dict
    inventory_service: Any
    requires_maintenance_window: bool


@runtime_checkable
class GateEvaluationStrategy(Protocol):
    """Protocol définissant une stratégie d'évaluation d'un gate auto-évalué.

    Toute classe implémentant cette méthode est compatible (duck typing).
    """

    def evaluate(self, ctx: GateEvaluationContext) -> tuple[bool, dict]: ...


@dataclass(frozen=True)
class GateDefinition:
    """Définition centralisée d'un type de gate workflow.

    Attributes:
        gate_type: Code utilisé dans step_config (ex: 'maintenance_window', 'approval').
            C'est la valeur que l'utilisateur configure dans le workflow.
        condition_type: Code écrit dans gate_conditions[].type par GateHandler.
            C'est la valeur que GateEvaluator lit à l'exécution.
            Exemples : gate_type='approval' → condition_type='approval_granted'.
        display_name: Nom d'affichage frontend (ex: 'Fenêtre de maintenance').
        category: Catégorie sémantique ('maintenance', 'approval', ...).
        config_schema: Schéma JSON de configuration du gate (dict).
            Vide ({}) à ce stade — évolutif par story future.
        supports_timeout: True si timeout_hours est supporté pour ce gate.
        requires_manual_resolution: True si le gate ne peut être satisfait
            qu'en dehors du poll GateEvaluator (ex: endpoint /approve/).
            False = auto-évaluation par GateEvaluator.
        evaluation_strategy: Stratégie d'évaluation auto (Story 83.2).
            None pour les gates manuels ou non encore implémentés.
    """

    gate_type: str
    condition_type: str
    display_name: str
    category: str
    # Note: frozen=True protège la référence mais pas le contenu du dict.
    # config_schema doit être traité comme immuable — ne pas le muter après construction.
    config_schema: dict = field(default_factory=dict)
    supports_timeout: bool = False
    requires_manual_resolution: bool = False
    # compare=False, hash=False : évite TypeError si l'instance de stratégie n'est pas hashable.
    evaluation_strategy: GateEvaluationStrategy | None = field(
        default=None, compare=False, hash=False
    )


class GateDefinitionRegistry:
    """Registre singleton des définitions de gates.

    Indexé par gate_type (ce que l'utilisateur configure).
    Fournit aussi un index inverse condition_type → GateDefinition.
    """

    def __init__(self) -> None:
        self._by_gate_type: dict[str, GateDefinition] = {}
        self._by_condition_type: dict[str, GateDefinition] = {}

    def register(self, definition: GateDefinition) -> None:
        """Enregistre une GateDefinition.

        Un ré-enregistrement du même gate_type remplace la définition existante.
        """
        self._by_gate_type[definition.gate_type] = definition
        self._by_condition_type[definition.condition_type] = definition

    def get(self, gate_type: str) -> GateDefinition:
        """Retourne la définition d'un gate par gate_type.

        Raises:
            KeyError: Si gate_type n'est pas enregistré.
        """
        return self._by_gate_type[gate_type]

    def get_for_condition_type(self, condition_type: str) -> GateDefinition:
        """Retourne la définition d'un gate par condition_type (interne runtime).

        Utilisé par GateEvaluator pour valider et déléguer.

        Raises:
            KeyError: Si condition_type n'est pas enregistré.
        """
        return self._by_condition_type[condition_type]

    def is_registered(self, gate_type: str) -> bool:
        """True si gate_type est enregistré."""
        return gate_type in self._by_gate_type

    def list_types(self) -> list[str]:
        """Retourne les gate_types dans l'ordre d'insertion."""
        return list(self._by_gate_type)

    def get_valid_condition_types(self) -> frozenset[str]:
        """Retourne l'ensemble des condition_types valides.

        Remplace VALID_GATE_CONDITION_TYPES dans catalog/validators.py.
        """
        return frozenset(self._by_condition_type)
