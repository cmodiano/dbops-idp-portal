"""
Test d'alignement des types de gate — Story 82.1 Phase 0, AC1 (T1.4).

Garantit que VALID_GATE_CONDITION_TYPES, GateHandler.condition_type_map
et GateEvaluator match statement restent cohérents.

Code review 82.1 : ajout tests GateEvaluator (H1) et validateur (H2).
"""
import pytest
from unittest.mock import MagicMock

from catalog.validators import VALID_GATE_CONDITION_TYPES, FUTURE_GATE_TYPES, validate_gate_conditions
from executions.gate_evaluator import GateEvaluator
from executions.step_handlers.gate_handler import GateHandler
from rest_framework.exceptions import ValidationError


# ---------------------------------------------------------------------------
# Alignement VALID_GATE_CONDITION_TYPES ↔ GateHandler
# ---------------------------------------------------------------------------

def test_valid_gate_types_match_handler():
    """Tous les types valides doivent être gérés par le GateHandler (accès classe)."""
    # Accès direct à l'attribut de classe — pas besoin d'instancier GateHandler.
    handler_output_types = set(GateHandler.condition_type_map.values())
    valid_set = set(VALID_GATE_CONDITION_TYPES)

    assert valid_set == handler_output_types, (
        f"Dérive détectée :\n"
        f"  Types valides non gérés par le handler : {valid_set - handler_output_types}\n"
        f"  Types gérés par le handler non déclarés valides : {handler_output_types - valid_set}"
    )


def test_future_gate_types_not_in_valid():
    """FUTURE_GATE_TYPES ne doit PAS être dans VALID_GATE_CONDITION_TYPES."""
    overlap = FUTURE_GATE_TYPES & set(VALID_GATE_CONDITION_TYPES)
    assert not overlap, (
        f"Types réservés (non implémentés) trouvés dans VALID_GATE_CONDITION_TYPES : {overlap}\n"
        "Supprimer de VALID_GATE_CONDITION_TYPES ou implémenter dans GateEvaluator."
    )


def test_valid_gate_types_is_exhaustive():
    """Les deux types actuellement implémentés sont bien présents."""
    assert 'maintenance_window' in VALID_GATE_CONDITION_TYPES
    assert 'approval_granted' in VALID_GATE_CONDITION_TYPES


def test_future_gate_types_documented():
    """Les types futurs sont bien dans FUTURE_GATE_TYPES."""
    assert 'time_window' in FUTURE_GATE_TYPES
    assert 'target_state' in FUTURE_GATE_TYPES


# ---------------------------------------------------------------------------
# Alignement VALID_GATE_CONDITION_TYPES ↔ GateEvaluator (H1 — AC1 complet)
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
    """GateEvaluator ne doit PAS tomber dans le fallback case _ pour les types valides.

    AC1 : GateHandler ET GateEvaluator gèrent exactement les mêmes types.
    Ce test détecte la dérive si un type est retiré du match statement sans
    être retiré de VALID_GATE_CONDITION_TYPES.
    """
    evaluator = GateEvaluator(inventory_service=MagicMock())

    for gate_type in VALID_GATE_CONDITION_TYPES:
        step = _make_mock_step(gate_type)
        _, gate_status = evaluator.evaluate(step)

        gates = gate_status.get('gates', [])
        assert len(gates) == 1, (
            f"Type '{gate_type}' : attendu 1 gate dans gate_status, obtenu {len(gates)}"
        )

        gate_reason = gates[0].get('reason', '')
        assert not gate_reason.startswith('Unsupported gate type'), (
            f"Type '{gate_type}' n'est pas géré par GateEvaluator (fallback case _) :\n"
            f"  reason = {gate_reason!r}\n"
            "  Ajouter un case dans gate_evaluator.py ou retirer de VALID_GATE_CONDITION_TYPES."
        )


# ---------------------------------------------------------------------------
# Régression validateur — FUTURE_GATE_TYPES rejetés (H2 — AC1 complet)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("gate_type", ['time_window', 'target_state'])
def test_future_gate_types_rejected_by_validator(gate_type):
    """validate_gate_conditions doit rejeter les types de FUTURE_GATE_TYPES.

    Régression : empêche la réintégration accidentelle de time_window/target_state
    dans VALID_GATE_CONDITION_TYPES sans implémenter leur évaluation dans GateEvaluator.
    """
    with pytest.raises(ValidationError):
        validate_gate_conditions([{'type': gate_type}])
