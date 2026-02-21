"""
Tests d'injection de dépendances pour GateEvaluator — Story 33.4 (DIP)

Vérifient :
- L'injection directe d'un InventoryService mock (AC3)
- Le fallback sur InventoryService() par défaut (AC4 — rétrocompatibilité)
"""
from unittest.mock import MagicMock

import pytest


def test_gate_evaluator_uses_injected_service():
    """AC3 : GateEvaluator accepte un InventoryService injecté."""
    mock_svc = MagicMock()
    from executions.gate_evaluator import GateEvaluator
    evaluator = GateEvaluator(inventory_service=mock_svc)
    assert evaluator.inventory_service is mock_svc


def test_gate_evaluator_default_service():
    """AC4 : Sans injection, GateEvaluator instancie InventoryService par défaut."""
    from inventory.services import InventoryService
    from executions.gate_evaluator import GateEvaluator
    evaluator = GateEvaluator()
    assert isinstance(evaluator.inventory_service, InventoryService)
