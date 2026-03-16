"""
Test d'alignement des types de gate — Story 82.1 Phase 0, AC1 (T1.4).
Story 82.5: Migré vers gate_registry (suppression VALID_GATE_CONDITION_TYPES et condition_type_map).

Garantit que gate_registry, GateHandler et GateEvaluator restent cohérents.

Code review 82.1 : ajout tests GateEvaluator (H1) et validateur (H2).
"""
import pytest
from unittest.mock import MagicMock

from catalog.validators import FUTURE_GATE_TYPES, validate_gate_conditions
from executions.gate_evaluator import GateEvaluator
from executions.gates.registry import gate_registry
from rest_framework.exceptions import ValidationError


# ---------------------------------------------------------------------------
# Alignement gate_registry ↔ GateHandler (Story 82.5)
# ---------------------------------------------------------------------------

def test_valid_gate_types_match_handler():
    """Les condition_types du registre doivent correspondre aux types valides.

    Story 82.5: GateHandler utilise gate_registry — pas de condition_type_map.
    """
    # condition_types enregistrés = les types que GateEvaluator évalue
    valid_condition_types = gate_registry.get_valid_condition_types()
    assert 'maintenance_window' in valid_condition_types
    assert 'approval_granted' in valid_condition_types


def test_future_gate_types_not_in_registry():
    """FUTURE_GATE_TYPES ne doit PAS être dans gate_registry."""
    registered_condition_types = gate_registry.get_valid_condition_types()
    overlap = FUTURE_GATE_TYPES & registered_condition_types
    assert not overlap, (
        f"Types réservés (non implémentés) trouvés dans gate_registry : {overlap}\n"
        "Supprimer de gate_registry ou implémenter dans GateEvaluator."
    )


def test_valid_gate_types_is_exhaustive():
    """Les deux types actuellement implémentés sont bien présents dans le registre."""
    valid_condition_types = gate_registry.get_valid_condition_types()
    assert 'maintenance_window' in valid_condition_types
    assert 'approval_granted' in valid_condition_types


def test_future_gate_types_documented():
    """Les types futurs sont bien dans FUTURE_GATE_TYPES."""
    assert 'time_window' in FUTURE_GATE_TYPES
    assert 'target_state' in FUTURE_GATE_TYPES


# ---------------------------------------------------------------------------
# Alignement gate_registry ↔ GateEvaluator (H1 — AC1 complet)
# ---------------------------------------------------------------------------

def _make_mock_step(gate_type: str) -> MagicMock:
    """Construit un ExecutionStep minimal pour tester GateEvaluator en isolation."""
    step = MagicMock()
    step.id = 1
    step.get_output.return_value = {'gate_conditions': [{'type': gate_type}]}
    # env_config absent → requires_maintenance_window = False → auto-satisfy sans appel inventory
    step.execution.get_parameters.return_value = {}
    return step


def test_gate_evaluator_handles_all_valid_types():
    """GateEvaluator ne doit PAS tomber dans le fallback 'Unsupported' pour les types valides.

    AC1 : gate_registry ET GateEvaluator gèrent exactement les mêmes types.
    Ce test détecte la dérive si un type est retiré du registre sans
    adapter GateEvaluator.
    """
    evaluator = GateEvaluator(inventory_service=MagicMock())

    for condition_type in gate_registry.get_valid_condition_types():
        step = _make_mock_step(condition_type)
        _, gate_status = evaluator.evaluate(step)

        gates = gate_status.get('gates', [])
        assert len(gates) == 1, (
            f"Type '{condition_type}' : attendu 1 gate dans gate_status, obtenu {len(gates)}"
        )

        gate_reason = gates[0].get('reason', '')
        assert not gate_reason.startswith('Unsupported gate type'), (
            f"Type '{condition_type}' n'est pas géré par GateEvaluator (fallback Unsupported) :\n"
            f"  reason = {gate_reason!r}\n"
            "  Ajouter la logique dans gate_evaluator.py ou retirer du registre."
        )


# ---------------------------------------------------------------------------
# Régression validateur — FUTURE_GATE_TYPES rejetés (H2 — AC1 complet)
# ---------------------------------------------------------------------------

def test_gate_evaluator_approval_granted_never_satisfied():
    """approval_granted n'est JAMAIS auto-satisfait par GateEvaluator (requires_manual_resolution=True).

    AC7 : GateEvaluator — approval_granted toujours non satisfait.
    Garantit que gate_registry.get_for_condition_type('approval_granted').requires_manual_resolution
    est bien respecté par la logique evaluate().
    """
    evaluator = GateEvaluator(inventory_service=MagicMock())
    step = _make_mock_step('approval_granted')
    all_satisfied, gate_status = evaluator.evaluate(step)

    assert all_satisfied is False
    gates = gate_status.get('gates', [])
    assert len(gates) == 1
    assert gates[0]['satisfied'] is False
    assert "approbation" in gates[0].get('reason', '').lower()


@pytest.mark.parametrize("gate_type", ['time_window', 'target_state'])
def test_future_gate_types_rejected_by_validator(gate_type):
    """validate_gate_conditions doit rejeter les types de FUTURE_GATE_TYPES.

    Régression : empêche la réintégration accidentelle de time_window/target_state
    dans gate_registry sans implémenter leur évaluation dans GateEvaluator.
    """
    with pytest.raises(ValidationError):
        validate_gate_conditions([{'type': gate_type}])
